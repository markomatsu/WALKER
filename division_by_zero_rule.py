from base_rule import BaseRule
from clang.cindex import CursorKind


class DivisionByZeroRule(BaseRule):
    """
    Detects obvious division/modulo-by-zero operations.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.BINARY_OPERATOR

    def apply(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return None

        tokens = [t.spelling for t in cursor.get_tokens()]
        if not tokens:
            return None

        has_div = "/" in tokens
        has_mod = "%" in tokens
        if not has_div and not has_mod:
            return None

        operator_index = None
        for i, tok in enumerate(tokens):
            if tok in {"/", "%"}:
                operator_index = i
                break

        if operator_index is None or operator_index + 1 >= len(tokens):
            return None

        rhs = tokens[operator_index + 1]
        if rhs not in {"0", "0.0", "0.0f", "0.0F"}:
            return None

        line = node.get("line")
        if line:
            return f"[ERROR] Possible division by zero on line {line}."
        return "[ERROR] Possible division by zero."
