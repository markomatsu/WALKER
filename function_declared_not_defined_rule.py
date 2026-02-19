from clang.cindex import CursorKind

from base_rule import BaseRule


class FunctionDeclaredNotDefinedRule(BaseRule):
    """
    Warn when a free function is declared and called, but not defined in this file.
    This avoids false positives for normal external declarations.
    """

    def __init__(self):
        self.declared = {}
        self.defined = set()
        self.called = set()

    def _has_body(self, node):
        return any(child.get("kind") == CursorKind.COMPOUND_STMT for child in node.get("children", []))

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _usr(self, cursor):
        if cursor is None:
            return None
        try:
            usr = cursor.get_usr()
        except Exception:
            usr = None
        return usr or None

    def _function_usr(self, node):
        return self._usr(node.get("cursor"))

    def _is_external_declaration(self, node):
        # External declarations are often defined in other translation units.
        tokens = self._tokens(node)
        return "extern" in tokens

    def matches(self, node):
        kind = node.get("kind")

        if kind == CursorKind.CALL_EXPR:
            cursor = node.get("cursor")
            if cursor is None:
                return False
            try:
                referenced = cursor.referenced
            except Exception:
                referenced = None
            if referenced is None:
                return False
            if referenced.kind != CursorKind.FUNCTION_DECL:
                return False
            usr = self._usr(referenced)
            if usr:
                self.called.add(usr)
            return False

        if kind != CursorKind.FUNCTION_DECL:
            return False

        name = node.get("name")
        if not name:
            return False

        usr = self._function_usr(node)
        if not usr:
            return False

        if self._has_body(node):
            self.defined.add(usr)
            return False

        if self._is_external_declaration(node):
            return False

        if usr not in self.declared:
            self.declared[usr] = {
                "name": name,
                "line": node.get("line"),
            }
        return False

    def apply(self, node):
        return None

    def finalize(self):
        messages = []
        sortable = []
        for usr, meta in self.declared.items():
            sortable.append((meta.get("line") or 10**9, meta.get("name") or "", usr, meta))
        for _, _, usr, meta in sorted(sortable):
            if usr in self.defined:
                continue
            if usr not in self.called:
                continue

            name = meta.get("name") or "function"
            line = meta.get("line")
            if line:
                messages.append(
                    f"[WARN] Function '{name}' declared on line {line} is called "
                    "but not defined in this file."
                )
            else:
                messages.append(
                    f"[WARN] Function '{name}' is called but not defined in this file."
                )
        return messages
