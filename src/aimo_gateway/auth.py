import secrets
import hashlib
import hmac
from datetime import timedelta

from .common import Problem, digest, stamp
from .upstream import timestamp


BUYER_SCOPES = ["catalog:read", "requests:read", "baskets:read", "baskets:write", "baskets:evaluate", "orders:commit", "orders:read", "audit:read"]

def csrf_token(credential_id):
    return hmac.new(credential_id.encode(), b"aimo-session-csrf", hashlib.sha256).hexdigest()


class Auth:
    def __init__(self, store, clock, origin):
        self.store, self.clock, self.origin = store, clock, origin

    def issue(self, connection, principal, kind):
        token = secrets.token_urlsafe(32)
        credential = {"id": digest(token), "principalId": principal["id"], "customerId": principal["customerId"], "kind": kind,
                      "expiresAt": principal["expiresAt"], "revoked": False}
        self.store.put(connection, "credential", credential, principal["customerId"])
        return token

    def bootstrap(self, customer="demo-customer"):
        with self.store.transaction() as connection:
            if self.store.get(connection, "policy", customer):
                raise ValueError("Database already initialized; refusing to overwrite its policies or credentials")
            if any(self.store.get(connection, "principal", actor) for actor in ("chef", "manager", "buyer-agent")):
                raise ValueError("Demo principal IDs already exist; do not overwrite another customer's principals")
            policy = {"id": customer, "version": "demo-policy-1", "active": True, "upstreamCustomer": "123",
                      "sites": ["demo-kitchen"], "autonomousLimitMinor": 1000, "orderLimitMinor": 100000,
                      "dailyLimitMinor": 200000, "eligibleProducts": None}
            self.store.put(connection, "policy", policy, customer)
            credentials = {}
            for actor, kind, scopes in (
                ("chef", "human", BUYER_SCOPES + ["requests:create", "requests:cancel"]),
                ("manager", "human", BUYER_SCOPES + ["approvals:decide"]),
                ("buyer-agent", "agent", BUYER_SCOPES),
            ):
                principal = {"id": actor, "customerId": customer, "kind": kind, "scopes": scopes,
                             "expiresAt": stamp(self.clock() + timedelta(hours=8)), "revoked": False,
                             "approvalLimitMinor": 100000 if actor == "manager" else 0}
                self.store.put(connection, "principal", principal, customer)
                credentials[actor] = self.issue(connection, principal, "login" if kind == "human" else "agent")
            return credentials

    def current(self, connection, credential_id, expected=None):
        credential = self.store.get(connection, "credential", credential_id)
        if not credential or credential["revoked"] or timestamp(credential["expiresAt"]) <= self.clock():
            raise Problem(401, "UNAUTHENTICATED")
        principal = self.store.get(connection, "principal", credential["principalId"])
        if not principal or principal["revoked"] or timestamp(principal["expiresAt"]) <= self.clock():
            raise Problem(401, "UNAUTHENTICATED")
        if credential["customerId"] != principal["customerId"]:
            raise Problem(401, "UNAUTHENTICATED")
        if expected and credential["kind"] != expected:
            raise Problem(401, "UNAUTHENTICATED")
        if principal["kind"] != ("agent" if credential["kind"] == "agent" else "human"):
            raise Problem(401, "UNAUTHENTICATED")
        return principal, credential

    def login(self, token, origin):
        if origin != self.origin or not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise Problem(403, "FORBIDDEN")
        with self.store.transaction() as connection:
            principal, _ = self.current(connection, digest(token), "login")
            session = self.issue(connection, principal, "session")
            credential = self.store.get(connection, "credential", digest(session))
            csrf = csrf_token(credential["id"])
            credential["csrfHash"] = digest(csrf)
            credential["expiresAt"] = stamp(min(timestamp(principal["expiresAt"]), self.clock() + timedelta(hours=1)))
            self.store.put(connection, "credential", credential, principal["customerId"])
            return session, {"principalId": principal["id"], "csrfToken": csrf, "expiresAt": credential["expiresAt"]}

    def authenticate(self, authorization, session, origin, csrf, mutation):
        if authorization and session:
            raise Problem(401, "UNAUTHENTICATED", "Use one credential type")
        if authorization:
            scheme, separator, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not separator or not token:
                raise Problem(401, "UNAUTHENTICATED")
            kind = "agent"
        elif session:
            token, kind = session, "session"
        else:
            raise Problem(401, "UNAUTHENTICATED")
        with self.store.transaction() as connection:
            _, credential = self.current(connection, digest(token), kind)
            if kind == "session" and mutation:
                if origin != self.origin or not csrf or not secrets.compare_digest(credential["csrfHash"], digest(csrf)):
                    raise Problem(403, "FORBIDDEN", "Origin or CSRF verification failed")
        return digest(token)

    def grant(self, connection, principal_id, request_id):
        principal = self.store.get(connection, "principal", principal_id)
        request = self.store.get(connection, "request", request_id)
        if not principal or not request or principal["customerId"] != request["customerId"]:
            raise ValueError("Principal and request must belong to the same customer")
        self.store.put(connection, "grant", {"id": principal_id + ":" + request_id, "revoked": False}, request["customerId"])

    def access(self, connection, principal, request):
        grant = self.store.get(connection, "grant", principal["id"] + ":" + request["id"])
        if principal["customerId"] != request["customerId"] or not grant or grant["revoked"]:
            raise Problem(404, "NOT_FOUND")