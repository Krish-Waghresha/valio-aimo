import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .common import Problem


class Wire:
    def __init__(self):
        packaged = Path(__file__).with_name("gateway.openapi.json")
        path = packaged if packaged.exists() else Path(__file__).resolve().parents[2] / "docs/gateway.openapi.json"
        self.spec = json.loads(path.read_text())
        self.operations = {}
        for path, methods in self.spec["paths"].items():
            for method, operation in methods.items():
                if method in ("get", "post", "put"):
                    self.operations[operation["operationId"]] = {**operation, "path": path, "method": method}

    def resolve(self, value):
        if "$ref" not in value:
            return value
        result = self.spec
        for part in value["$ref"].removeprefix("#/").split("/"):
            result = result[part]
        return result

    def valid(self, schema, value):
        validator = Draft202012Validator({**schema, "components": self.spec["components"]}, format_checker=FormatChecker())
        return not any(validator.iter_errors(value))

    def input(self, operation, body):
        definition = self.operations[operation].get("requestBody")
        if definition is None:
            if body is not None:
                raise Problem(422, "INVALID_INPUT", "This operation does not accept a body")
            return
        schema = self.resolve(definition)["content"]["application/json"]["schema"]
        if not self.valid(schema, body):
            raise Problem(422, "INVALID_INPUT", "Request does not match the published schema")

    def output(self, operation, status, value):
        schema = self.operations[operation]["responses"][str(status)]["content"]["application/json"]["schema"]
        if not self.valid(schema, value):
            raise Problem(500, "INTERNAL_ERROR", "Gateway output failed contract validation")