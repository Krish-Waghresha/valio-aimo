import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from .store import encode


class Problem(Exception):
    def __init__(self, status, code, detail=None):
        self.status = status
        self.code = code
        self.detail = detail or code.replace("_", " ").capitalize()
        super().__init__(self.detail)


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def identity():
    return str(uuid4())


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def public(value):
    return {key: item for key, item in value.items() if not key.startswith("_")}