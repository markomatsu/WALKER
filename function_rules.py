from clang.cindex import CursorKind
from base_rule import BaseRule


class FunctionRule(BaseRule):
    """
    Describes function declarations.
    """

    def matches(self, node: dict) -> bool:
        return node.get("kind") == CursorKind.FUNCTION_DECL

    def apply(self, node: dict) -> str | None:
        name = node.get("name")
        line = node.get("line")

        if not name:
            return None

        if line:
            return f"This defines a function named '{name}' on line {line}."

        return f"This defines a function named '{name}'."
