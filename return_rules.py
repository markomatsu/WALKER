from clang.cindex import CursorKind
from base_rule import BaseRule


class ReturnRule(BaseRule):
    """
    Describes return statements and any literal value it can infer.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.RETURN_STMT

    def apply(self, node):
        value = "a value"
        line = node.get("line")

        for child in node.get("children", []):
            if child.get("kind") == CursorKind.INTEGER_LITERAL:
                cursor = child.get("cursor")
                tokens = list(cursor.get_tokens()) if cursor else []
                value = tokens[0].spelling if tokens else "0"

        if line:
            return f"The function returns {value} on line {line}."
        return f"The function returns {value}."
