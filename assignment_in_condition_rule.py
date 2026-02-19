from base_rule import BaseRule
from clang.cindex import CursorKind
from expr_renderer import find_condition_node


class AssignmentInConditionRule(BaseRule):
    """
    Warns when an if-condition appears to use assignment (=) instead of comparison.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.IF_STMT

    def apply(self, node):
        condition = find_condition_node(node)
        if condition is None:
            return None

        cursor = condition.get("cursor")
        if cursor is None:
            return None

        tokens = [t.spelling for t in cursor.get_tokens()]
        if not tokens:
            return None

        has_assignment = "=" in tokens
        has_comparison = any(tok in tokens for tok in ("==", "!=", ">=", "<="))
        if not has_assignment or has_comparison:
            return None

        line = node.get("line")
        if line:
            return f"[WARN] Possible assignment used as condition on line {line}."
        return "[WARN] Possible assignment used as condition."
