from clang.cindex import CursorKind
from base_rule import BaseRule
from expr_renderer import describe_expr


class ForLoopRule(BaseRule):
    """
    Describes classic for-loops (for (init; condition; increment)).
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.FOR_STMT

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _find_condition_node(self, node):
        # Heuristic: pick the first expression child containing a comparison/logical operator.
        expr_kinds = {
            CursorKind.BINARY_OPERATOR,
            CursorKind.UNARY_OPERATOR,
            CursorKind.PAREN_EXPR,
            CursorKind.UNEXPOSED_EXPR,
            CursorKind.DECL_REF_EXPR,
            CursorKind.INTEGER_LITERAL,
            CursorKind.FLOATING_LITERAL,
            CursorKind.CXX_BOOL_LITERAL_EXPR,
            CursorKind.CALL_EXPR,
        }

        candidates = [c for c in node.get("children", []) if c.get("kind") in expr_kinds]
        for c in candidates:
            toks = self._tokens(c)
            if any(op in toks for op in ("<", ">", "<=", ">=", "==", "!=", "&&", "||")):
                return c

        return candidates[0] if candidates else None

    def apply(self, node):
        line = node.get("line")
        condition_node = self._find_condition_node(node)
        if condition_node is None:
            if line:
                return f"This is a for-loop on line {line}."
            return "This is a for-loop."

        condition_text = describe_expr(condition_node)
        if line:
            return f"This is a for-loop on line {line} that continues while {condition_text}."
        return f"This is a for-loop that continues while {condition_text}."
