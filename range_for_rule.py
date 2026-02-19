from clang.cindex import CursorKind
from base_rule import BaseRule
from expr_renderer import describe_expr


class RangeForRule(BaseRule):
    """
    Describes range-based for-loops (for (auto x : range)).
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.CXX_FOR_RANGE_STMT

    def _find_range_expr(self, node):
        expr_kinds = {
            CursorKind.DECL_REF_EXPR,
            CursorKind.CALL_EXPR,
            CursorKind.UNEXPOSED_EXPR,
            CursorKind.PAREN_EXPR,
            CursorKind.MEMBER_REF_EXPR,
        }

        candidates = [c for c in node.get("children", []) if c.get("kind") in expr_kinds]
        if not candidates:
            return None

        return candidates[-1]

    def apply(self, node):
        line = node.get("line")
        range_node = self._find_range_expr(node)
        if range_node is None:
            if line:
                return f"This is a range-based for-loop on line {line}."
            return "This is a range-based for-loop."

        range_text = describe_expr(range_node)
        if line:
            return f"This is a range-based for-loop on line {line} iterating over {range_text}."
        return f"This is a range-based for-loop iterating over {range_text}."
