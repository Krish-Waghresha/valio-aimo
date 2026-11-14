import json
import time
from datetime import date

from .auth import Auth
from .common import Problem, digest, identity, public, stamp
from .evaluation import Evaluator
from .store import encode
from .upstream import HELSINKI, timestamp
from .wire import Wire


HUMAN_ONLY = {"createRequest", "cancelRequest", "decideEvaluation"}


class Gateway:
    def __init__(self, store, catalog, source, clock, origin):
        if store.mode != catalog.mode or source.mode != catalog.mode:
            raise ValueError("Database, catalog and upstream mode must match")
        self.store, self.catalog, self.source, self.clock = store, catalog, source, clock
        self.auth = Auth(store, clock, origin)
        self.wire = Wire()
        self.evaluator = Evaluator(catalog, source, clock)

    def day(self):
        return self.clock().astimezone(HELSINKI).date().isoformat()

    def throttle_credential(self, credential_id):
        with self.store.transaction() as connection:
            principal, _ = self.auth.current(connection, credential_id)
        self.throttle(principal["customerId"] + ":" + principal["id"])

    def throttle(self, principal, limit=120):
        bucket = int(self.clock().timestamp()) // 60
        with self.store.transaction() as connection:
            connection.execute("DELETE FROM throttle WHERE bucket < ?", (bucket - 2,))
            row = connection.execute("SELECT count FROM throttle WHERE principal=? AND bucket=?", (principal, bucket)).fetchone()
            if row and row["count"] >= limit:
                raise Problem(429, "RATE_LIMITED")
            connection.execute("INSERT INTO throttle VALUES (?, ?, 1) ON CONFLICT(principal,bucket) DO UPDATE SET count=count+1", (principal, bucket))

    def context(self, connection, credential_id, operation, params, body):
        principal, _ = self.auth.current(connection, credential_id)
        customer = principal["customerId"]
        result = {"principal": principal}
        targets = {"requestId": "request", "basketId": "basket", "evaluationId": "evaluation", "orderId": "order"}
        resource_params = dict(params)
        if operation == "commitOrder":
            resource_params["evaluationId"] = body["evaluationId"]
        for field, kind in targets.items():
            if field in resource_params:
                resource = self.store.get(connection, kind, resource_params[field], customer)
                if resource is None:
                    raise Problem(404, "NOT_FOUND")
                result[kind] = resource
        if "evaluation" in result:
            result["basket"] = self.store.get(connection, "basket", result["evaluation"]["basketId"], customer)
        parent = next((resource["requestId"] for kind, resource in result.items() if kind in ("basket", "evaluation", "order")), None)
        if parent:
            result["request"] = self.store.get(connection, "request", parent, customer)
        if "request" in result:
            self.auth.access(connection, principal, result["request"])
        if operation in HUMAN_ONLY and principal["kind"] != "human":
            raise Problem(403, "FORBIDDEN", "An authenticated human is required")
        if not set(self.wire.operations[operation]["x-required-scopes"]).issubset(principal["scopes"]):
            raise Problem(403, "FORBIDDEN")
        policy = self.store.get(connection, "policy", customer)
        if not policy or not policy.get("active"):
            raise Problem(403, "FORBIDDEN", "Customer purchasing is disabled")
        result["policy"] = policy
        return result

    def active(self, context):
        state = context["request"]["status"]
        if state != "active":
            raise Problem(409, "REQUEST_ALREADY_ORDERED" if state == "ordered_mock" else "REQUEST_CANCELLED")

    def current_evaluation(self, context):
        self.active(context)
        evaluation, basket = context["evaluation"], context["basket"]
        if basket.get("activeEvaluationId") != evaluation["id"] or evaluation["basketVersion"] != basket["version"]:
            raise Problem(409, "EVALUATION_SUPERSEDED")
        if timestamp(evaluation["expiresAt"]) <= self.clock():
            raise Problem(410, "EVALUATION_EXPIRED")
        if evaluation["_policyDigest"] != digest(context["policy"]) or evaluation["catalogVersion"] != self.catalog.version:
            raise Problem(410, "EVALUATION_EXPIRED", "Policy or catalog changed; evaluate again")

    def ready(self, connection, context):
        self.current_evaluation(context)
        evaluation = context["evaluation"]
        if evaluation["outcome"] == "blocked":
            raise Problem(409, "POLICY_BLOCKED")
        if evaluation["outcome"] == "approval_required":
            decision = self.store.get(connection, "decision", evaluation["id"])
            if not decision or decision["decision"] != "approve":
                raise Problem(409, "APPROVAL_REQUIRED")
            approver = self.store.get(connection, "principal", decision["actorId"])
            if not approver or approver["kind"] != "human" or approver["revoked"] or timestamp(approver["expiresAt"]) <= self.clock():
                raise Problem(403, "FORBIDDEN", "Approval authority was revoked or expired")
            if "approvals:decide" not in approver["scopes"] or approver["approvalLimitMinor"] < evaluation["totals"]["grossMinor"]:
                raise Problem(403, "FORBIDDEN", "Approval authority no longer covers this order")
            try:
                self.auth.access(connection, approver, context["request"])
            except Problem:
                raise Problem(403, "FORBIDDEN", "Approver no longer has access to this request") from None

    def basket_view(self, connection, context):
        basket = public(context["basket"])
        state = "draft"
        if context["request"]["status"] == "cancelled":
            state = "cancelled"
        elif context["request"]["status"] == "ordered_mock":
            row = connection.execute("SELECT data FROM orders WHERE request_id=?", (context["request"]["id"],)).fetchone()
            order = json.loads(row["data"])
            evaluation = self.store.get(connection, "evaluation", order["evaluationId"])
            state = "ordered_mock" if evaluation["basketId"] == basket["id"] else "cancelled"
            if state == "ordered_mock":
                basket["orderId"] = order["id"]
        elif "activeEvaluationId" in basket:
            evaluation = self.store.get(connection, "evaluation", basket["activeEvaluationId"])
            state = {"allowed": "ready", "approval_required": "awaiting_approval", "blocked": "blocked"}[evaluation["outcome"]]
            decision = self.store.get(connection, "decision", evaluation["id"])
            if decision:
                state = "ready" if decision["decision"] == "approve" else "rejected"
            if state != "rejected" and (timestamp(evaluation["expiresAt"]) <= self.clock()
                                        or evaluation["_policyDigest"] != digest(context["policy"])
                                        or evaluation["catalogVersion"] != self.catalog.version):
                state = "expired"
            if state == "ready":
                try:
                    self.ready(connection, {**context, "evaluation": evaluation})
                except Problem:
                    state = "expired"
        basket["state"] = state
        return basket

    def audit(self, connection, context, event_type, trace, codes=None, **entities):
        self.store.event(connection, context["request"]["id"], {
            "id": identity(), "type": event_type, "actorId": context["principal"]["id"],
            "at": stamp(self.clock()), "summary": event_type.replace(".", " "), "traceId": trace,
            "reasonCodes": codes or [], **entities,
        })

    def read(self, credential_id, operation, params, query):
        with self.store.transaction() as connection:
            context = self.context(connection, credential_id, operation, params, None)
            if operation == "searchProducts":
                result = self.catalog.search(query["query"], query["limit"], context["policy"].get("eligibleProducts"))
            elif operation == "getBasket":
                result = self.basket_view(connection, context)
            elif operation == "listRequestEvents":
                rows = connection.execute("SELECT data FROM events WHERE request_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                                          (context["request"]["id"], query["afterSequence"], query["limit"])).fetchall()
                events = [json.loads(row["data"]) for row in rows]
                result = {"events": events, "nextAfterSequence": events[-1]["sequence"] if events else query["afterSequence"]}
            else:
                result = public(context[{"getRequest": "request", "getEvaluation": "evaluation", "getOrder": "order"}[operation]])
            self.wire.output(operation, 200, result)
            return {"status": 200, "body": result}

    def reserve(self, connection, scope, fingerprint, owner):
        row = connection.execute("SELECT * FROM idempotency WHERE scope=?", (scope,)).fetchone()
        if row:
            if row["fingerprint"] != fingerprint:
                raise Problem(409, "IDEMPOTENCY_CONFLICT")
            if row["state"] == "complete":
                return json.loads(row["response"])
            if row["state"] == "pending" and row["lease"] > self.clock().timestamp():
                raise Problem(409, "REQUEST_IN_PROGRESS")
            connection.execute("UPDATE idempotency SET state='pending', owner=?, lease=? WHERE scope=?",
                               (owner, self.clock().timestamp() + 120, scope))
        else:
            connection.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?, 'pending', NULL)",
                               (scope, fingerprint, owner, self.clock().timestamp() + 120))
        return None

    def lock_basket(self, connection, basket_id, owner):
        row = connection.execute("SELECT * FROM locks WHERE resource=?", (basket_id,)).fetchone()
        if row and row["lease"] > self.clock().timestamp():
            raise Problem(409, "REQUEST_IN_PROGRESS")
        connection.execute("INSERT INTO locks VALUES (?, ?, ?) ON CONFLICT(resource) DO UPDATE SET owner=excluded.owner, lease=excluded.lease",
                           (basket_id, owner, self.clock().timestamp() + 120))

    def mutate(self, credential_id, operation, params, body, key, version, trace):
        self.wire.input(operation, body)
        if operation in ("createBasket", "replaceBasket"):
            body = {**body, "lines": sorted(body["lines"], key=lambda line: line["productId"])}
        owner = identity()
        with self.store.transaction() as connection:
            context = self.context(connection, credential_id, operation, params, body)
            scope = digest([context["principal"]["customerId"], context["principal"]["id"], operation, params, key])
            replay = self.reserve(connection, scope, digest([body, version]), owner)
            if replay:
                return replay
        try:
            fresh = None
            if operation in ("evaluateBasket", "commitOrder"):
                snapshot, spent = self.snapshot(credential_id, operation, params, body, version, owner, trace)
                context = snapshot
                fresh = self.evaluator.evaluate(snapshot["request"], snapshot["basket"], snapshot["policy"], spent)
            with self.store.transaction() as connection:
                context = self.context(connection, credential_id, operation, params, body)
                claim = connection.execute("SELECT owner,state FROM idempotency WHERE scope=?", (scope,)).fetchone()
                if claim["owner"] != owner or claim["state"] != "pending":
                    raise Problem(409, "REQUEST_IN_PROGRESS")
                if fresh:
                    lock = connection.execute("SELECT owner FROM locks WHERE resource=?", (context["basket"]["id"],)).fetchone()
                    if not lock or lock["owner"] != owner:
                        raise Problem(409, "REQUEST_IN_PROGRESS")
                    if snapshot["basket"]["version"] != context["basket"]["version"]:
                        raise Problem(412, "VERSION_CONFLICT")
                    if digest(snapshot["policy"]) != digest(context["policy"]) or fresh[0]["catalogVersion"] != self.catalog.version:
                        raise Problem(409, "EVALUATION_REQUIRED")
                status, result = self.apply(connection, context, operation, body, version, fresh, trace)
                self.wire.output(operation, status, result)
                response = {"status": status, "body": result}
                connection.execute("UPDATE idempotency SET state='complete',response=? WHERE scope=? AND owner=?", (encode(response), scope, owner))
                connection.execute("DELETE FROM locks WHERE owner=?", (owner,))
                return response
        except BaseException as error:
            with self.store.transaction() as connection:
                connection.execute("UPDATE idempotency SET state='failed' WHERE scope=? AND owner=? AND state='pending'", (scope, owner))
                connection.execute("DELETE FROM locks WHERE owner=?", (owner,))
                if operation == "commitOrder" and "request" in context:
                    self.audit(connection, context, "order.refused", trace, [error.code if isinstance(error, Problem) else "INTERNAL_ERROR"])
            raise

    def snapshot(self, credential_id, operation, params, body, version, owner, trace):
        deadline = time.monotonic() + 30
        while True:
            try:
                with self.store.transaction() as connection:
                    context = self.context(connection, credential_id, operation, params, body)
                    self.active(context)
                    self.lock_basket(connection, context["basket"]["id"], owner)
                    if operation == "commitOrder":
                        self.ready(connection, context)
                        self.audit(connection, context, "order.attempted", trace, evaluationId=context["evaluation"]["id"])
                    else:
                        self.check_version(context, version)
                        if context["basket"].get("_rejectedHash") == digest(context["basket"]["lines"]):
                            raise Problem(409, "DECISION_ALREADY_RECORDED", "Revise the rejected basket first")
                    spent = self.store.spent(connection, context["principal"]["customerId"], self.day())
                    return context, spent
            except Problem as error:
                if error.code != "REQUEST_IN_PROGRESS" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.025)

    def check_version(self, context, version):
        if version is None:
            raise Problem(428, "PRECONDITION_REQUIRED")
        if context["basket"]["version"] != version:
            raise Problem(412, "VERSION_CONFLICT")

    def apply(self, connection, context, operation, body, version, fresh, trace):
        principal, policy = context["principal"], context["policy"]
        customer = principal["customerId"]
        if operation == "createRequest":
            if body["deliverySiteId"] not in policy["sites"] or date.fromisoformat(body["requestedDeliveryDate"]) < date.fromisoformat(self.day()):
                raise Problem(422, "INVALID_INPUT", "Invalid delivery site or past delivery date")
            request = {"id": identity(), "customerId": customer, "createdBy": principal["id"],
                       "createdAt": stamp(self.clock()), "status": "active", "intent": body}
            self.store.put(connection, "request", request, customer)
            self.auth.grant(connection, principal["id"], request["id"])
            context["request"] = request
            self.audit(connection, context, "request.created", trace)
            return 201, request
        if operation == "cancelRequest":
            if context["request"]["status"] == "ordered_mock":
                raise Problem(409, "REQUEST_ALREADY_ORDERED")
            context["request"]["status"] = "cancelled"
            self.store.put(connection, "request", context["request"], customer)
            self.audit(connection, context, "request.cancelled", trace)
            return 200, context["request"]
        self.active(context)
        if operation in ("createBasket", "replaceBasket"):
            lines = sorted(body["lines"], key=lambda line: line["productId"])
            if len({line["productId"] for line in lines}) != len(lines):
                raise Problem(422, "INVALID_INPUT", "Product IDs must be unique")
            if operation == "replaceBasket":
                self.check_version(context, version)
                basket = context["basket"]
                if basket["lines"] == lines:
                    return 200, self.basket_view(connection, context)
                basket = {"id": basket["id"], "requestId": basket["requestId"], "version": basket["version"] + 1, "lines": lines}
            else:
                basket = {"id": identity(), "requestId": context["request"]["id"], "version": 1, "lines": lines}
            self.store.put(connection, "basket", basket, customer, basket["requestId"])
            context["basket"] = basket
            self.audit(connection, context, "basket.created" if operation == "createBasket" else "basket.replaced", trace, basketId=basket["id"])
            return (201 if operation == "createBasket" else 200), self.basket_view(connection, context)
        if operation == "evaluateBasket":
            self.check_version(context, version)
            evaluation, evidence = fresh
            if timestamp(evaluation["expiresAt"]) <= self.clock() and evaluation["outcome"] != "blocked":
                raise Problem(410, "EVALUATION_EXPIRED")
            evaluation["_policyDigest"] = digest(policy)
            self.store.put(connection, "evaluation", evaluation, customer, context["request"]["id"])
            self.store.put(connection, "evidence", evidence, customer, context["request"]["id"])
            context["basket"]["activeEvaluationId"] = evaluation["id"]
            self.store.put(connection, "basket", context["basket"], customer, context["request"]["id"])
            self.audit(connection, context, "basket.evaluated", trace, [item["code"] for item in evaluation["reasons"]], basketId=context["basket"]["id"], evaluationId=evaluation["id"])
            return 201, public(evaluation)
        if operation == "decideEvaluation":
            self.current_evaluation(context)
            evaluation = context["evaluation"]
            if self.store.get(connection, "decision", evaluation["id"]):
                raise Problem(409, "DECISION_ALREADY_RECORDED")
            if evaluation["outcome"] != "approval_required":
                raise Problem(409, "POLICY_BLOCKED", "Only eligible evaluations requiring approval can receive a decision")
            if principal["approvalLimitMinor"] < evaluation["totals"]["grossMinor"]:
                raise Problem(403, "FORBIDDEN")
            decision = {"id": evaluation["id"], "evaluationId": evaluation["id"], **body,
                        "actorId": principal["id"], "createdAt": stamp(self.clock()), "expiresAt": evaluation["expiresAt"]}
            self.store.put(connection, "decision", decision, customer, context["request"]["id"])
            if body["decision"] == "reject":
                context["basket"]["_rejectedHash"] = digest(context["basket"]["lines"])
                self.store.put(connection, "basket", context["basket"], customer, context["request"]["id"])
            self.audit(connection, context, "evaluation.decided", trace, evaluationId=evaluation["id"])
            return 201, decision
        if operation == "commitOrder":
            self.ready(connection, context)
            current, evidence = fresh
            evaluation = context["evaluation"]
            if current["outcome"] == "blocked":
                raise Problem(409, "POLICY_BLOCKED", ", ".join(sorted({item["code"] for item in current["reasons"]})))
            if [line["pricing"] for line in current["lines"]] != [line["pricing"] for line in evaluation["lines"]]:
                raise Problem(409, "EVALUATION_REQUIRED", "Prices changed; evaluate and authorize again")
            if (self.clock() - timestamp(current["checkedAt"])).total_seconds() > 30 or timestamp(current["expiresAt"]) <= self.clock():
                raise Problem(410, "EVALUATION_EXPIRED", "Final recheck is no longer fresh")
            order = {"id": identity(), "requestId": context["request"]["id"], "evaluationId": evaluation["id"],
                     "commitEvidenceId": evidence["id"], "status": "ordered_mock", "mode": self.catalog.mode,
                     "committedBy": principal["id"], "committedAt": stamp(self.clock()),
                     "deliverySiteId": context["request"]["intent"]["deliverySiteId"],
                     "requestedDeliveryDate": context["request"]["intent"]["requestedDeliveryDate"],
                     "lines": current["lines"], "totals": current["totals"]}
            try:
                self.store.commit_order(connection, context["request"], order, policy["dailyLimitMinor"], self.day())
            except ValueError as error:
                raise Problem(409, "POLICY_BLOCKED", str(error)) from None
            self.store.put(connection, "evidence", evidence, customer, context["request"]["id"])
            self.audit(connection, context, "order.created", trace, orderId=order["id"], evaluationId=evaluation["id"])
            return 201, order
        raise Problem(404, "NOT_FOUND")