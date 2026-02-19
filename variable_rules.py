from clang.cindex import CursorKind
from base_rule import BaseRule


class VariableRule(BaseRule):
    """
    Describes variable declarations.
    """

    def matches(self, node: dict) -> bool:
        return node.get("kind") == CursorKind.VAR_DECL

    def apply(self, node: dict) -> str | None:
        name = node.get("name")
        line = node.get("line")

        if not name:
            return None

        if line:
            return f"Variable '{name}' is declared on line {line}."

        return f"Variable '{name}' is declared."
