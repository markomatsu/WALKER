from clang.cindex import CursorKind

from base_rule import BaseRule


class ShadowedVariableRule(BaseRule):
    """
    Warns when a local variable/parameter shadows an outer declaration.
    """

    _DECL_KINDS = {CursorKind.VAR_DECL, CursorKind.PARM_DECL}
    _SCOPE_KINDS = {
        CursorKind.FUNCTION_DECL,
        CursorKind.COMPOUND_STMT,
        CursorKind.IF_STMT,
        CursorKind.FOR_STMT,
        CursorKind.CXX_FOR_RANGE_STMT,
        CursorKind.WHILE_STMT,
        CursorKind.DO_STMT,
        CursorKind.SWITCH_STMT,
    }

    def __init__(self):
        self.function_nodes = []
        self._seen = set()

    def matches(self, node):
        if node.get("kind") == CursorKind.FUNCTION_DECL:
            node_id = id(node)
            if node_id not in self._seen:
                self._seen.add(node_id)
                self.function_nodes.append(node)
        return False

    def apply(self, node):
        return None

    def _opens_scope(self, node):
        return node.get("kind") in self._SCOPE_KINDS

    def _walk(self, node, scopes, messages):
        pushed = False
        if self._opens_scope(node):
            scopes.append({})
            pushed = True

        kind = node.get("kind")
        if kind in self._DECL_KINDS:
            name = node.get("name")
            line = node.get("line")
            if name:
                shadowed_line = None
                for scope in reversed(scopes[:-1]):
                    if name in scope:
                        shadowed_line = scope[name]
                        break

                if shadowed_line is not None:
                    if line:
                        messages.append(
                            f"[WARN] Variable '{name}' on line {line} shadows an outer declaration from line {shadowed_line}."
                        )
                    else:
                        messages.append(f"[WARN] Variable '{name}' shadows an outer declaration.")

                scopes[-1].setdefault(name, line)

        for child in node.get("children", []):
            self._walk(child, scopes, messages)

        if pushed:
            scopes.pop()

    def finalize(self):
        messages = []
        for function_node in self.function_nodes:
            self._walk(function_node, [{}], messages)
        return messages
