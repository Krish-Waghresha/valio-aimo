import json
import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from datetime import date

from .agent import PurchasingAgent
from .interpreter import interpret
from .auth import csrf_token
from .common import Problem, digest, identity, public, stamp
from .planner import DemoSource, Planner, _packs
from .sourcing import decide, reliability_map, shortlist
from .service import Gateway


JOB_INPUT = {
    "type": "object", "additionalProperties": False,
    "required": ["brief", "servings", "deliveryDate", "maxGrossMinor", "dietaryConfirmed", "dietaryRequirements",
                 "excludedAllergens", "pantry", "preference", "autoCommit"],
    "properties": {
        "brief": {"type": "string", "minLength": 1, "maxLength": 2000},
        "servings": {"type": "integer", "minimum": 1, "maximum": 10000},
        "deliveryDate": {"type": "string", "format": "date"},
        "maxGrossMinor": {"type": "integer", "minimum": 1, "maximum": 1000000000000},
        "dietaryConfirmed": {"type": "boolean", "const": True},
        "dietaryRequirements": {"$ref": "#/components/schemas/Constraints/properties/dietaryRequirements"},
        "excludedAllergens": {"$ref": "#/components/schemas/Constraints/properties/excludedAllergens"},
        "pantry": {"type": "object", "maxProperties": 30, "propertyNames": {"pattern": "^[A-Za-z0-9_-]{1,64}$"},
                   "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1000000}},
        "preference": {"enum": ["balanced", "price", "reliability", "sustainability"]},
        "scenario": {"enum": ["normal", "shortage", "late"]}, "autoCommit": {"type": "boolean"},
        "items": {"type": "array", "maxItems": 10, "items": {"type": "object", "additionalProperties": False,
                  "required": ["query", "quantity", "unit"], "properties": {
                      "query": {"type": "string", "minLength": 1, "maxLength": 120},
                      "quantity": {"type": "string", "pattern": "^[0-9]{1,6}(\\.[0-9]{1,3})?$"},
                      "unit": {"enum": ["l", "kg"]}, "evidence": {"type": "string", "maxLength": 200}}}},
    },
}


class Workspace:
    def __init__(self, gateway):
        self.gateway, self.store = gateway, gateway.store
        self.planner = Planner(gateway.catalog, Path("data/valio") if gateway.catalog.mode == "live" else None)
        self.agent = PurchasingAgent(self.planner)
        self.reliability = reliability_map("data/valio") if gateway.catalog.mode == "live" else {}
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="purchasing")
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT data,customer FROM documents WHERE kind='job'").fetchall()
            for row in rows:
                job = json.loads(row["data"])
                if job["state"] in ("planning", "checking") and not job.get("exceptions"):
                    self.fail_in_transaction(connection, job, "Server restarted during processing. Inspect the audit record and create a revised request.")

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)

    def human(self, credential, scope=None):
        with self.store.transaction() as connection:
            principal, session = self.gateway.auth.current(connection, credential, "session")
            if scope and scope not in principal["scopes"]:
                raise Problem(403, "FORBIDDEN")
            return principal, session

    def session(self, credential):
        with self.store.transaction() as connection:
            principal, session = self.gateway.auth.current(connection, credential, "session")
            csrf = csrf_token(session["id"])
            session["csrfHash"] = digest(csrf)
            self.store.put(connection, "credential", session, principal["customerId"])
            policy = self.store.get(connection, "policy", principal["customerId"])
        return {"principalId": principal["id"], "scopes": principal["scopes"], "csrfToken": csrf,
                "mode": self.gateway.catalog.mode, "agentMode": self.agent.mode, "today": self.gateway.day(),
                "recipes": self.planner.recipes(), "policy": {key: policy[key] for key in ("autonomousLimitMinor", "orderLimitMinor")}}

    def interpret(self, credential, text):
        principal, _ = self.human(credential, "requests:create")
        with self.store.transaction() as connection:
            policy = self.store.get(connection, "policy", principal["customerId"])
        return interpret(text, date.fromisoformat(self.gateway.day()), policy)

    def logout(self, credential):
        with self.store.transaction() as connection:
            principal, session = self.gateway.auth.current(connection, credential, "session")
            session["revoked"] = True
            self.store.put(connection, "credential", session, principal["customerId"])
        return {"loggedOut": True}

    def authorized_job(self, credential, job_id, scope=None):
        principal, _ = self.human(credential, scope)
        with self.store.transaction() as connection:
            job = self.store.get(connection, "job", job_id, principal["customerId"])
            if not job:
                raise Problem(404, "NOT_FOUND")
            request = self.store.get(connection, "request", job["requestId"], principal["customerId"])
            self.gateway.auth.access(connection, principal, request)
        return job

    def list_jobs(self, credential):
        principal, _ = self.human(credential)
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT data FROM documents WHERE kind='job' AND customer=? ORDER BY rowid DESC LIMIT 200", (principal["customerId"],)).fetchall()
        result = []
        for row in rows:
            try:
                result.append(self.get_job(credential, json.loads(row["data"])["id"]))
            except Problem as error:
                if error.status != 404:
                    raise
        return result

    def get_job(self, credential, job_id):
        job = self.authorized_job(credential, job_id)
        if job.get("basket") and job["state"] not in ("planning", "checking", "failed", "needs_clarification"):
            result = self.gateway.read(credential, "getBasket", {"basketId": job["basket"]["id"]}, {})["body"]
            if result["state"] == "ordered_mock":
                job["order"] = self.gateway.read(credential, "getOrder", {"orderId": result["orderId"]}, {})["body"]
                job["state"] = "ordered_mock"
            elif result["state"] in ("cancelled", "rejected"):
                job["state"] = result["state"]
            elif result["state"] == "expired":
                job["error"] = "The quote or authority expired. Recheck before approval or ordering."
            elif job["state"] in ("ready", "awaiting_approval"):
                job["state"] = result["state"]
            job["basket"] = result
        return public(job)

    def create(self, credential, data, key):
        principal, _ = self.human(credential, "requests:create")
        if not self.gateway.wire.valid(JOB_INPUT, data):
            raise Problem(422, "INVALID_INPUT", "Check the request, date, budget and dietary confirmation")
        if self.gateway.catalog.mode == "live" and data.get("scenario", "normal") != "normal":
            raise Problem(422, "INVALID_INPUT", "Scenario injection is available only in fixture mode")
        job_id = str(uuid5(NAMESPACE_URL, digest([principal["id"], principal["customerId"], key])))
        fingerprint = digest(data)
        with self.store.transaction() as connection:
            previous = self.store.get(connection, "job", job_id, principal["customerId"])
            if previous:
                if previous["_fingerprint"] != fingerprint:
                    raise Problem(409, "IDEMPOTENCY_CONFLICT")
                return public(previous)
        request_body = {"brief": data["brief"], "servings": data["servings"], "deliverySiteId": "demo-kitchen",
                        "requestedDeliveryDate": data["deliveryDate"], "maxGrossMinor": data["maxGrossMinor"],
                        "constraints": {field: data[field] for field in ("dietaryConfirmed", "dietaryRequirements", "excludedAllergens")}}
        request = self.gateway.mutate(credential, "createRequest", {}, request_body, key, None, identity())["body"]
        job = {**data, "id": job_id, "requestId": request["id"], "createdAt": stamp(self.gateway.clock()),
               "mode": self.gateway.catalog.mode, "agentMode": self.agent.mode, "scenario": data.get("scenario", "normal"),
               "state": "planning", "plan": None, "basket": None, "evaluation": None, "order": None,
               "messages": [{"message": "Request from " + principal["id"]}],
               "steps": [{"label": "Understood your request", "detail": data["brief"].split("\n")[-1][:80], "at": stamp(self.gateway.clock())}],
               "error": None, "_customer": principal["customerId"], "_fingerprint": fingerprint}
        with self.store.transaction() as connection:
            previous = self.store.get(connection, "job", job_id)
            if previous:
                if previous["_fingerprint"] != fingerprint:
                    raise Problem(409, "IDEMPOTENCY_CONFLICT")
                return public(previous)
            for actor in ("buyer-agent", "manager"):
                self.gateway.auth.grant(connection, actor, request["id"])
            self.store.put(connection, "job", job, principal["customerId"], request["id"])
        self.pool.submit(self.process, job_id)
        return public(job)

    def load(self, job_id):
        with self.store.transaction() as connection:
            return self.store.get(connection, "job", job_id)

    def update(self, job_id, message=None, step=None, **changes):
        with self.store.transaction() as connection:
            job = self.store.get(connection, "job", job_id)
            if job["state"] in ("cancelled", "ordered_mock", "rejected"):
                return job
            job.update(changes)
            if step:
                job.setdefault("steps", []).append({"label": step[0], "detail": step[1], "at": stamp(self.gateway.clock())})
            if message:
                job["messages"].append({"message": message, "at": stamp(self.gateway.clock())})
            self.store.put(connection, "job", job, job["_customer"], job["requestId"])
            return job

    def scoped(self, job):
        if job["mode"] == "fixture":
            return Gateway(self.store, self.gateway.catalog, DemoSource(self.gateway.clock, job["scenario"]), self.gateway.clock, self.gateway.auth.origin)
        return self.gateway

    def agent_credential(self, job):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT data FROM documents WHERE kind='credential' AND customer=?", (job["_customer"],)).fetchall()
            for row in rows:
                value = json.loads(row["data"])
                if value["kind"] == "agent" and value["principalId"] == "buyer-agent":
                    try:
                        self.gateway.context(connection, value["id"], "getRequest", {"requestId": job["requestId"]}, None)
                        return value["id"]
                    except Problem:
                        continue
        raise Problem(403, "FORBIDDEN", "Assigned buyer agent has no current request authority")

    def compare(self, gateway, credential, job, plan):
        proposed = {}
        for ingredient in plan["ingredients"]:
            for candidate in ingredient["candidates"]:
                packed = _packs(Decimal(ingredient["needed"]), Decimal(candidate["packAmount"]), Decimal(str(candidate["lotSize"])))
                if packed and packed[0]:
                    quantity = max(packed[0], proposed.get(candidate["productId"], {}).get("quantity", 0))
                    proposed[candidate["productId"]] = {"productId": candidate["productId"], "salesUnit": candidate["salesUnit"], "quantity": quantity}
        if len(proposed) > 50:
            raise Problem(422, "INVALID_INPUT", "Candidate shortlist exceeds 50 products; narrow the request")
        with self.store.transaction() as connection:
            context = gateway.context(connection, credential, "getRequest", {"requestId": job["requestId"]}, None)
        if not proposed:
            return plan
        proposal = {"id": identity(), "version": 1, "lines": list(proposed.values())}
        checked, _ = gateway.evaluator.evaluate(context["request"], proposal, context["policy"], 0)
        facts = {line["productId"]: line for line in checked["lines"]}
        excluded = set()
        for ingredient in plan["ingredients"]:
            for candidate in ingredient["candidates"]:
                line = facts.get(candidate["productId"])
                if not line:
                    continue
                candidate["available"] = not line["reasons"]
                candidate["reasons"] = line["reasons"]
                candidate["checkedAt"] = checked["checkedAt"]
                candidate["availableDate"] = line.get("availability", {}).get("availableDate")
                if line.get("pricing"):
                    candidate["unitNet"] = line["pricing"]["unitNet"]
                    candidate["unitGross"] = line["pricing"]["unitGross"]
                    packed = _packs(Decimal(ingredient["needed"]), Decimal(candidate["packAmount"]), Decimal(str(candidate["lotSize"])))
                    candidate["purchaseGrossMinor"] = int((Decimal(candidate["unitGross"]) * packed[0] * 100).quantize(Decimal("1"))) if packed else None
                if line["reasons"]:
                    excluded.add(candidate["productId"])
        selected = self.planner.select(plan, excluded)
        selected["agentMode"] = job["agentMode"]
        selected["explanations"] = [item for item in selected["explanations"] if item.get("code") != "PRICE_UNKNOWN"]
        selected["explanations"].append({"code": "LIVE_COMPARISON", "message": "Candidates compared using gateway prices, delivery checks, and the selected ranking preference."})
        return selected

    def process(self, job_id):
        try:
            job = self.load(job_id)
            credential, gateway = self.agent_credential(job), self.scoped(job)
            constraints = {field: job[field] for field in ("dietaryConfirmed", "dietaryRequirements", "excludedAllergens")}
            if job.get("items") and self.gateway.catalog.mode == "live":
                return self.source(job_id, job, gateway, credential, constraints)
            pantry = {key: Decimal(str(value)) for key, value in job["pantry"].items()}
            plan = self.agent.plan(job["brief"], job["servings"], constraints, pantry, job["preference"])
            notices = [item for item in plan["questions"] if item.get("code") == "BRIEF_SERVINGS_IGNORED"]
            plan["warnings"].extend(notices)
            plan["questions"] = [item for item in plan["questions"] if item not in notices]
            self.update(job_id, "Ingredient plan calculated; checking candidate products.", plan=plan, state="checking",
                        step=("Planned the recipe", f"{len(plan['ingredients'])} ingredients for {job['servings']} servings"))
            if not plan["lines"]:
                self.update(job_id, state="needs_clarification", plan=plan)
                return
            plan = self.compare(gateway, credential, job, plan)
            self.update(job_id, step=("Checked live price & stock", f"{sum(len(item['candidates']) for item in plan['ingredients'])} products, one lookup"))
            if not plan["lines"]:
                self.update(job_id, "No complete feasible basket was found. No order was attempted.", state="blocked", plan=plan)
                return
            changes_recipe = [item for item in plan["warnings"] if item.get("code") == "RECIPE_CHANGE"]
            if changes_recipe:
                plan["questions"].extend(changes_recipe)
                self.update(job_id, "A recipe-changing substitution needs a revised human request.", state="needs_clarification", plan=plan)
                return
            self.submit_basket(job_id, job, gateway, credential, plan)
        except Exception as error:
            logging.getLogger("aimo_gateway.workspace").warning("Job failed id=%s class=%s", job_id, type(error).__name__)
            with self.store.transaction() as connection:
                self.fail_in_transaction(connection, self.store.get(connection, "job", job_id),
                                         error.detail if isinstance(error, Problem) else "Planning failed safely; inspect the audit record.")

    def submit_basket(self, job_id, job, gateway, credential, plan):
        basket = gateway.mutate(credential, "createBasket", {"requestId": job["requestId"]}, {"lines": plan["lines"]}, job_id, None, identity())["body"]
        self.update(job_id, plan=plan, basket=basket, state="checking")
        evaluation = gateway.mutate(credential, "evaluateBasket", {"basketId": basket["id"]}, None, identity(), basket["version"], identity())["body"]
        state = {"allowed": "ready", "approval_required": "awaiting_approval", "blocked": "blocked"}[evaluation["outcome"]]
        self.update(job_id, step=("Checked your spending limit", {"ready": "within limit", "awaiting_approval": "needs manager approval", "blocked": "blocked"}[state]))
        message = {"ready": "Within the buyer's limit", "awaiting_approval": "Over the buyer's limit → sent to kitchen manager",
                   "blocked": "Blocked by ordering rules"}[state]
        self.update(job_id, message, evaluation=evaluation, state=state)
        if state == "ready" and job["autoCommit"]:
            self.commit_agent(job_id)

    def source(self, job_id, job, gateway, credential, constraints):
        catalog = self.gateway.catalog
        shortlists = []
        for item in job["items"]:
            family, candidates = shortlist(catalog, item["query"], item["unit"], constraints)
            shortlists.append((item, family, candidates))
        ids = list(dict.fromkeys(candidate["productId"] for _, _, candidates in shortlists for candidate in candidates))
        missing = [item["query"] for item, _, candidates in shortlists if not candidates]
        if missing:
            plan = self._source_plan(job, [], [], [{"code": "UNSUPPORTED_REQUEST", "message": "I couldn't find matching products for: " + ", ".join(missing) + ". Name the product more precisely."}])
            self.update(job_id, "No matching catalog products found.", plan=plan, state="needs_clarification")
            return
        self.update(job_id, step=("Searched the catalog", f"{len(catalog.products):,} products → {len(ids)} matches"), state="checking")
        with self.store.transaction() as connection:
            context = gateway.context(connection, credential, "getRequest", {"requestId": job["requestId"]}, None)
        proposal = {"id": identity(), "version": 1, "lines": [{"productId": product_id, "salesUnit": catalog.products[product_id]["salesUnit"], "quantity": 1} for product_id in ids]}
        checked, _ = gateway.evaluator.evaluate(context["request"], proposal, context["policy"], 0)
        facts = {line["productId"]: line for line in checked["lines"]}
        self.update(job_id, f"{len(ids)} matching products · live price & stock checked",
                    step=("Checked live price & stock", f"{len(ids)} products, one lookup"))
        lines, exceptions, actions, ingredients = [], [], [], []
        for item, family, candidates in shortlists:
            item_lines, item_exceptions, item_actions, ranked = decide(item, family, candidates, facts, self.reliability, job["preference"], job["deliveryDate"])
            for exception in item_exceptions:
                exception["item"] = item["query"]
            lines.extend(item_lines)
            exceptions.extend(item_exceptions)
            actions.extend(item_actions)
            ingredients.append(self._source_ingredient(item, candidates, facts, ranked))
        plan = self._source_plan(job, ingredients, lines, [])
        plan["explanations"] = [{"code": action["code"], "message": action["message"]} for action in actions]
        skipped = sum(1 for action in actions if action["code"] == "SKIPPED")
        self.update(job_id, step=("Compared price, stock & reliability", f"{skipped} skipped" + (f" · {len(exceptions)} needs you" if exceptions else " · best option chosen")))
        if any(item["severity"] == "blocked" for item in exceptions):
            self.update(job_id, "No orderable product found for part of the request.", plan=plan, exceptions=exceptions, state="blocked")
            return
        if exceptions:
            self.update(job_id, "Asked the buyer one question", plan=plan, exceptions=exceptions, state="needs_decision")
            return
        self.submit_basket(job_id, job, gateway, credential, plan)

    def _source_plan(self, job, ingredients, lines, questions):
        return {"title": job["brief"], "recipeId": None, "servings": job["servings"], "recipeSource": "Agent sourcing from the Valio Aimo catalog",
                "imageUrl": None, "agentMode": job["agentMode"], "questions": questions, "warnings": [], "explanations": [],
                "ingredients": ingredients, "lines": lines, "comparison": {"reliability": None, "carbonKgEstimate": None, "carbonCoverage": 0}}

    def _source_ingredient(self, item, candidates, facts, ranked):
        ranked_ids = {candidate["productId"]: candidate for candidate in ranked}
        rows = []
        for candidate in candidates:
            fact = facts.get(candidate["productId"], {})
            good = ranked_ids.get(candidate["productId"])
            rows.append({"productId": candidate["productId"], "name": candidate["name"], "salesUnit": candidate["salesUnit"],
                         "packAmount": str(candidate["packAmount"]), "labels": candidate["labels"], "imageUrl": None, "unit": "L" if item["unit"] == "l" else item["unit"],
                         "reliability": float(self.reliability[candidate["productId"]]) if candidate["productId"] in self.reliability else None,
                         "carbonKgPerKg": None, "unitGross": fact.get("pricing", {}).get("unitGross"),
                         "perUnitGross": str(good["perUnitGross"].quantize(Decimal("0.01"))) if good else None,
                         "stockAmount": str(good["stockAmount"]) if good and good["stockAmount"] is not None else None,
                         "available": good is not None, "reasons": fact.get("reasons", [])})
        return {"key": item["query"], "label": item["query"].capitalize(), "unit": item["unit"], "required": item["quantity"],
                "pantry": "0", "needed": item["quantity"], "productId": None, "quantity": None, "packAmount": None, "overage": None, "candidates": rows}

    def resolve(self, credential, job_id, data):
        principal, _ = self.human(credential, "requests:create")
        job = self.authorized_job(credential, job_id)
        if job["state"] != "needs_decision":
            raise Problem(409, "INVALID_STATE", "This order has no open decision")
        exception = next((item for item in job.get("exceptions", []) if item["id"] == data.get("exceptionId")), None)
        option = next((item for item in (exception or {}).get("options", []) if item["id"] == data.get("optionId")), None)
        if not exception or not option or exception.get("choice"):
            raise Problem(422, "INVALID_INPUT", "Choose one of the offered options")
        exception["choice"] = {"optionId": option["id"], "label": option["label"], "by": principal["id"], "at": stamp(self.gateway.clock())}
        plan = job["plan"]
        plan["lines"] = plan["lines"] + option["lines"]
        plan["explanations"].append({"code": "HUMAN_DECISION", "message": f"{principal['id'].capitalize()} chose: {option['label']}"})
        open_items = [item for item in job["exceptions"] if not item.get("choice")]
        self.update(job_id, f"{principal['id'].capitalize()} chose: {option['label']}", plan=plan, exceptions=job["exceptions"])
        if not open_items:
            self.pool.submit(self._continue, job_id)
        return public(self.load(job_id))

    def _continue(self, job_id):
        try:
            job = self.load(job_id)
            self.submit_basket(job_id, job, self.scoped(job), self.agent_credential(job), job["plan"])
        except Exception as error:
            logging.getLogger("aimo_gateway.workspace").warning("Job continuation failed id=%s class=%s", job_id, type(error).__name__)
            with self.store.transaction() as connection:
                self.fail_in_transaction(connection, self.store.get(connection, "job", job_id),
                                         error.detail if isinstance(error, Problem) else "Ordering failed safely; inspect the audit record.")

    def fail_in_transaction(self, connection, job, detail):
        if job["state"] in ("cancelled", "ordered_mock", "rejected"):
            return
        request = self.store.get(connection, "request", job["requestId"])
        if request["status"] == "ordered_mock":
            record = connection.execute("SELECT data FROM orders WHERE request_id=?", (request["id"],)).fetchone()
            job.update(state="ordered_mock", order=json.loads(record["data"]), error=None)
        else:
            if request["status"] == "active":
                request["status"] = "cancelled"
                self.store.put(connection, "request", request, job["_customer"])
                self.store.event(connection, request["id"], {"id": identity(), "type": "request.cancelled", "actorId": "workspace-system",
                    "at": stamp(self.gateway.clock()), "summary": "Cancelled after workspace processing failure", "traceId": identity(), "reasonCodes": []})
            job.update(state="failed", error=detail)
        self.store.put(connection, "job", job, job["_customer"], job["requestId"])

    def commit_agent(self, job_id):
        job = self.load(job_id)
        if job["state"] != "ready" or not job.get("evaluation"):
            raise Problem(409, "EVALUATION_REQUIRED")
        order = self.scoped(job).mutate(self.agent_credential(job), "commitOrder", {}, {"evaluationId": job["evaluation"]["id"]},
                                       str(uuid5(NAMESPACE_URL, job_id + ":commit:" + job["evaluation"]["id"])), None, identity())["body"]
        return public(self.update(job_id, "Within limit → order placed automatically", state="ordered_mock", order=order, error=None))

    def commit(self, credential, job_id):
        job = self.authorized_job(credential, job_id, "orders:commit")
        if job["state"] == "ordered_mock":
            return public(job)
        if job["state"] != "ready" or not job.get("evaluation"):
            raise Problem(409, "EVALUATION_REQUIRED")
        order = self.scoped(job).mutate(credential, "commitOrder", {}, {"evaluationId": job["evaluation"]["id"]},
                                       str(uuid5(NAMESPACE_URL, job_id + ":human-commit:" + job["evaluation"]["id"])), None, identity())["body"]
        return public(self.update(job_id, "Price & stock re-checked → order placed", state="ordered_mock", order=order, error=None))

    def decide(self, credential, job_id, data):
        job = self.authorized_job(credential, job_id, "approvals:decide")
        if job["state"] != "awaiting_approval" or not job.get("evaluation"):
            raise Problem(409, "EVALUATION_REQUIRED")
        self.scoped(job).mutate(credential, "decideEvaluation", {"evaluationId": job["evaluation"]["id"]}, data, identity(), None, identity())
        result = self.update(job_id, "Kitchen manager " + ("approved" if data["decision"] == "approve" else "rejected"), state="ready" if data["decision"] == "approve" else "rejected")
        return public(result)

    def cancel(self, credential, job_id):
        job = self.authorized_job(credential, job_id, "requests:cancel")
        self.gateway.mutate(credential, "cancelRequest", {"requestId": job["requestId"]}, None, identity(), None, identity())
        return public(self.update(job_id, state="cancelled"))

    def recheck(self, credential, job_id):
        job = self.authorized_job(credential, job_id, "baskets:evaluate")
        if job["state"] in ("failed", "cancelled", "rejected", "ordered_mock", "planning", "checking") or not job.get("basket"):
            raise Problem(409, "EVALUATION_REQUIRED")
        gateway = self.scoped(job)
        evaluation = gateway.mutate(self.agent_credential(job), "evaluateBasket", {"basketId": job["basket"]["id"]}, None,
                                    identity(), job["basket"]["version"], identity())["body"]
        state = {"allowed": "ready", "approval_required": "awaiting_approval", "blocked": "blocked"}[evaluation["outcome"]]
        return public(self.update(job_id, "Basket rechecked; prior approval does not carry over.", evaluation=evaluation, state=state, error=None))

    def events(self, credential, job_id):
        job = self.authorized_job(credential, job_id, "audit:read")
        return self.gateway.read(credential, "listRequestEvents", {"requestId": job["requestId"]}, {"afterSequence": 0, "limit": 100})["body"]["events"]

    def export(self, credential, job_id):
        return {"job": self.get_job(credential, job_id), "events": self.events(credential, job_id)}