from clang.cindex import CursorKind

from base_rule import BaseRule


class UnreachableCodeRule(BaseRule):
    """
    Warns when a statement in the same block appears after a guaranteed
    control-flow transfer (return/break/continue/goto/throw).
    """

    def __init__(self):
        self.blocks = []
        self._seen = set()
        self._terminator_kinds = {
            CursorKind.RETURN_STMT,
            CursorKind.BREAK_STMT,
            CursorKind.CONTINUE_STMT,
            CursorKind.GOTO_STMT,
        }
        throw_kind = getattr(CursorKind, "CXX_THROW_EXPR", None)
        if throw_kind is not None:
            self._terminator_kinds.add(throw_kind)

        self._label_kinds = {
            CursorKind.CASE_STMT,
            CursorKind.DEFAULT_STMT,
        }
        label_stmt_kind = getattr(CursorKind, "LABEL_STMT", None)
        if label_stmt_kind is not None:
            self._label_kinds.add(label_stmt_kind)

    def matches(self, node):
        if node.get("kind") == CursorKind.COMPOUND_STMT:
            node_id = id(node)
            if node_id not in self._seen:
                self._seen.add(node_id)
                self.blocks.append(node)
        return False

    def apply(self, node):
        return None

    def _block_messages(self, block):
        messages = []
        children = block.get("children", [])
        terminated_line = None
        already_reported = False

        for child in children:
            kind = child.get("kind")
            line = child.get("line")

            if terminated_line is not None:
                if kind in self._label_kinds:
                    terminated_line = None
                    already_reported = False
                else:
                    if not already_reported and line and line != terminated_line:
                        messages.append(
                            f"[WARN] Statement on line {line} is unreachable (control flow ended on line {terminated_line})."
                        )
                    already_reported = True

            if kind in self._terminator_kinds:
                terminated_line = line
                already_reported = False

        return messages

    def finalize(self):
        messages = []
        for block in self.blocks:
            messages.extend(self._block_messages(block))
        return messages
