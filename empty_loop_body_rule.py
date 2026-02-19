from clang.cindex import CursorKind

from base_rule import BaseRule


class EmptyLoopBodyRule(BaseRule):
    """
    Warns when a loop body is empty (e.g., while (...); or for (...){ }).
    """

    _LOOP_KINDS = {
        CursorKind.WHILE_STMT,
        CursorKind.FOR_STMT,
        CursorKind.DO_STMT,
        CursorKind.CXX_FOR_RANGE_STMT,
    }

    def matches(self, node):
        return node.get("kind") in self._LOOP_KINDS

    def _body_node(self, loop_node):
        children = list(loop_node.get("children", []))
        if not children:
            return None

        if loop_node.get("kind") == CursorKind.DO_STMT:
            return children[0]

        if children[-1].get("kind") in {CursorKind.NULL_STMT, CursorKind.COMPOUND_STMT}:
            return children[-1]

        for child in children:
            if child.get("kind") in {CursorKind.NULL_STMT, CursorKind.COMPOUND_STMT}:
                return child

        return None

    def _loop_label(self, kind):
        if kind == CursorKind.WHILE_STMT:
            return "while-loop"
        if kind == CursorKind.FOR_STMT:
            return "for-loop"
        if kind == CursorKind.DO_STMT:
            return "do-while loop"
        return "range-based for-loop"

    def apply(self, node):
        body = self._body_node(node)
        if body is None:
            return None

        kind = body.get("kind")
        empty = False
        if kind == CursorKind.NULL_STMT:
            empty = True
        elif kind == CursorKind.COMPOUND_STMT and not body.get("children"):
            empty = True

        if not empty:
            return None

        line = node.get("line")
        label = self._loop_label(node.get("kind"))
        if line:
            return f"[WARN] Empty {label} body on line {line}."
        return f"[WARN] Empty {label} body."
