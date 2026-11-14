from datetime import datetime, timezone

import pytest

from aimo_gateway.auth import Auth
from aimo_gateway.common import Problem
from aimo_gateway.store import Store


@pytest.fixture
def auth(tmp_path):
    store = Store(tmp_path / "test.sqlite", "fixture")
    auth = Auth(store, lambda: datetime(2026, 11, 14, tzinfo=timezone.utc), "http://testserver")
    return auth, auth.bootstrap()


def test_agent_cannot_log_in_as_human(auth):
    service, credentials = auth
    with pytest.raises(Problem):
        service.login(credentials["buyer-agent"], "http://testserver")


def test_sessions_require_csrf_and_origin(auth):
    service, credentials = auth
    session, data = service.login(credentials["chef"], "http://testserver")
    assert service.authenticate(None, session, "http://testserver", data["csrfToken"], True)
    for origin, csrf in (("https://other.invalid", data["csrfToken"]), ("http://testserver", None)):
        with pytest.raises(Problem) as failure:
            service.authenticate(None, session, origin, csrf, True)
        assert failure.value.status == 403


def test_mixed_credentials_rejected(auth):
    service, credentials = auth
    session, data = service.login(credentials["chef"], "http://testserver")
    with pytest.raises(Problem):
        service.authenticate("Bearer " + credentials["buyer-agent"], session, "http://testserver", data["csrfToken"], True)


def test_revocation_is_immediate(auth):
    service, credentials = auth
    session, data = service.login(credentials["chef"], "http://testserver")
    with service.store.transaction() as connection:
        principal = service.store.get(connection, "principal", "chef")
        principal["revoked"] = True
        service.store.put(connection, "principal", principal, principal["customerId"])
    with pytest.raises(Problem):
        service.authenticate(None, session, "http://testserver", data["csrfToken"], True)