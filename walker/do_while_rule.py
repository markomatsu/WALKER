from clang.cindex import CursorKind
from base_rule import BaseRule
from expr_renderer import find_condition_node, describe_expr


class DoWhileRule(BaseRule):
    """
    Describes do-while loops.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.DO_STMT

    def apply(self, node):
        line = node.get("line")
        condition_node = find_condition_node(node)
        if condition_node is None:
            if line:
                return f"This is a do-while loop on line {line}."
            return "This is a do-while loop."

        condition_text = describe_expr(condition_node)
        if line:
            return f"This is a do-while loop on line {line} that repeats while {condition_text}."
        return f"This is a do-while loop that repeats while {condition_text}."
