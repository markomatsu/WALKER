from clang.cindex import CursorKind
from base_rule import BaseRule
from expr_renderer import find_condition_node, describe_expr


class WhileLoopRule(BaseRule):
    """
    Describes while-loops.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.WHILE_STMT

    def apply(self, node):
        line = node.get("line")
        condition_node = find_condition_node(node)
        if condition_node is None:
            if line:
                return f"This is a while-loop on line {line}."
            return "This is a while-loop."

        condition_text = describe_expr(condition_node)
        if line:
            return f"This is a while-loop on line {line} that continues while {condition_text}."
        return f"This is a while-loop that continues while {condition_text}."
