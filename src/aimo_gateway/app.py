import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .common import Problem, identity


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys")
        result[key] = value
    return result


async def body(request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 65536:
            raise Problem(422, "INVALID_INPUT", "Request body exceeds 64 KiB")
    if not content:
        return None
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise Problem(400, "MALFORMED_REQUEST", "Content-Type must be application/json")
    try:
        return json.loads(content, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise Problem(400, "MALFORMED_REQUEST", "Invalid JSON") from None


def create_app(gateway):
    from .workspace import Workspace
    workspace = Workspace(gateway)
    @asynccontextmanager
    async def lifespan(app):
        yield
        workspace.close()
        gateway.source.close()

    app = FastAPI(title="Aimo Gateway", lifespan=lifespan, redirect_slashes=False, redoc_url=None)
    app.openapi = lambda: gateway.wire.spec
    app.state.gateway = gateway
    app.state.workspace = workspace

    @app.middleware("http")
    async def errors(request, call_next):
        trace = identity()
        request.state.trace = trace
        try:
            response = await call_next(request)
        except Problem as error:
            logging.getLogger("aimo_gateway.security").warning("Denied trace=%s status=%s code=%s", trace, error.status, error.code)
            response = problem(error, request, trace)
        except Exception as error:
            logging.getLogger("aimo_gateway").error("Request failed trace=%s class=%s", trace, type(error).__name__)
            response = problem(Problem(500, "INTERNAL_ERROR", "Gateway failed safely; inspect server trace"), request, trace)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Trace-Id"] = trace
        return response

    def problem(error, request, trace):
        headers = {"Retry-After": "1"} if error.code == "REQUEST_IN_PROGRESS" else ({"Retry-After": "60"} if error.status == 429 else {})
        return JSONResponse(status_code=error.status, media_type="application/problem+json", headers=headers, content={
            "type": "urn:aimo-gateway:problem:" + error.code.lower().replace("_", "-"),
            "title": error.code.replace("_", " ").capitalize(), "status": error.status, "code": error.code,
            "detail": error.detail[:500], "instance": request.url.path, "traceId": trace,
        })

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        codes = {400: "MALFORMED_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                 405: "METHOD_NOT_ALLOWED", 422: "INVALID_INPUT", 429: "RATE_LIMITED"}
        status = error.status_code if error.status_code in codes else 500
        response = problem(Problem(status, codes.get(status, "INTERNAL_ERROR")), request, request.state.trace)
        if status == 405 and error.headers and "Allow" in error.headers:
            response.headers["Allow"] = error.headers["Allow"]
        return response

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "mode": gateway.catalog.mode, "orders": "local_mock_only"}

    @app.post("/auth/login", include_in_schema=False)
    async def login(request: Request):
        await run_in_threadpool(gateway.throttle, "login:" + request.client.host, 30)
        data = await body(request)
        if not isinstance(data, dict) or set(data) != {"loginToken"}:
            raise Problem(422, "INVALID_INPUT")
        session, result = await run_in_threadpool(gateway.auth.login, data["loginToken"], request.headers.get("origin"))
        response = JSONResponse(result)
        response.set_cookie("gateway_session", session, httponly=True, samesite="strict", secure=gateway.auth.origin.startswith("https://"), max_age=3600)
        return response

    def endpoint(operation_id, definition):
        async def route(request: Request):
            mutation = definition["method"] != "get"
            for name in ("authorization", "x-csrf-token", "idempotency-key", "origin", "x-expected-basket-version"):
                if len(request.headers.getlist(name)) > 1:
                    raise Problem(400, "MALFORMED_REQUEST", "Duplicate security/precondition header")
            credential = await run_in_threadpool(gateway.auth.authenticate, request.headers.get("authorization"),
                                                 request.cookies.get("gateway_session"), request.headers.get("origin"),
                                                 request.headers.get("x-csrf-token"), mutation)
            await run_in_threadpool(gateway.throttle_credential, credential)
            params = {}
            for key, value in request.path_params.items():
                try:
                    params[key] = str(UUID(value))
                except ValueError:
                    raise Problem(404, "NOT_FOUND") from None
            query = {}
            declared = [gateway.wire.resolve(item) for item in definition.get("parameters", [])]
            query_definitions = {item["name"]: item for item in declared if item["in"] == "query"}
            if set(request.query_params) - set(query_definitions):
                raise Problem(422, "INVALID_INPUT", "Unknown query parameter")
            for name, parameter in query_definitions.items():
                if len(request.query_params.getlist(name)) > 1:
                    raise Problem(422, "INVALID_INPUT")
                value = request.query_params.get(name, parameter["schema"].get("default"))
                if parameter["schema"].get("type") == "integer":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise Problem(422, "INVALID_INPUT") from None
                if not gateway.wire.valid(parameter["schema"], value):
                    raise Problem(422, "INVALID_INPUT")
                query[name] = value
            if not mutation:
                result = await run_in_threadpool(gateway.read, credential, operation_id, params, query)
            else:
                data = await body(request)
                key = request.headers.get("idempotency-key")
                try:
                    key = str(UUID(key))
                except (ValueError, TypeError, AttributeError):
                    raise Problem(422, "INVALID_INPUT", "A UUID Idempotency-Key is required") from None
                version = request.headers.get("x-expected-basket-version")
                if version is not None:
                    if not version.isascii() or not version.isdecimal() or int(version) < 1:
                        raise Problem(422, "INVALID_INPUT", "Invalid expected basket version")
                    version = int(version)
                result = await run_in_threadpool(gateway.mutate, credential, operation_id, params, data, key, version, request.state.trace)
            headers = {"X-Basket-Version": str(result["body"]["version"])} if operation_id in ("createBasket", "getBasket", "replaceBasket") else {}
            return JSONResponse(result["body"], status_code=result["status"], headers=headers)
        return route

    for operation_id, definition in gateway.wire.operations.items():
        app.add_api_route(definition["path"], endpoint(operation_id, definition), methods=[definition["method"].upper()], operation_id=operation_id)

    async def workspace_credential(request, mutation=False):
        credential = await run_in_threadpool(gateway.auth.authenticate, request.headers.get("authorization"), request.cookies.get("gateway_session"),
                                             request.headers.get("origin"), request.headers.get("x-csrf-token"), mutation)
        await run_in_threadpool(gateway.throttle_credential, credential)
        return credential

    @app.get("/workspace/session", include_in_schema=False)
    async def workspace_session(request: Request):
        return await run_in_threadpool(workspace.session, await workspace_credential(request))

    @app.post("/workspace/logout", include_in_schema=False)
    async def workspace_logout(request: Request):
        result = await run_in_threadpool(workspace.logout, await workspace_credential(request, True))
        response = JSONResponse(result)
        response.delete_cookie("gateway_session")
        return response

    @app.get("/workspace/jobs", include_in_schema=False)
    async def list_jobs(request: Request):
        return await run_in_threadpool(workspace.list_jobs, await workspace_credential(request))

    @app.post("/workspace/jobs", include_in_schema=False)
    async def create_job(request: Request):
        credential = await workspace_credential(request, True)
        try:
            key = str(UUID(request.headers.get("x-request-key")))
        except (TypeError, ValueError, AttributeError):
            raise Problem(422, "INVALID_INPUT", "X-Request-Key must be a UUID") from None
        result = await run_in_threadpool(workspace.create, credential, await body(request), key)
        return JSONResponse(result, status_code=201)

    @app.get("/workspace/jobs/{job_id}", include_in_schema=False)
    async def get_job(job_id: str, request: Request):
        return await run_in_threadpool(workspace.get_job, await workspace_credential(request), job_id)

    @app.get("/workspace/jobs/{job_id}/events", include_in_schema=False)
    async def job_events(job_id: str, request: Request):
        return await run_in_threadpool(workspace.events, await workspace_credential(request), job_id)

    @app.get("/workspace/jobs/{job_id}/export", include_in_schema=False)
    async def export_job(job_id: str, request: Request):
        result = await run_in_threadpool(workspace.export, await workspace_credential(request), job_id)
        return JSONResponse(result, headers={"Content-Disposition": 'attachment; filename="aimo-order-record.json"'})

    @app.post("/workspace/jobs/{job_id}/{action}", include_in_schema=False)
    async def job_action(job_id: str, action: str, request: Request):
        credential = await workspace_credential(request, True)
        data = await body(request)
        if action == "decision":
            gateway.wire.input("decideEvaluation", data)
            return await run_in_threadpool(workspace.decide, credential, job_id, data)
        if action not in ("commit", "cancel", "recheck") or data not in (None, {}):
            raise Problem(422, "INVALID_INPUT")
        return await run_in_threadpool(getattr(workspace, action), credential, job_id)

    app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="workspace")
    return app