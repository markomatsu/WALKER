from clang.cindex import CursorKind

from base_rule import BaseRule


class UnusedFunctionRule(BaseRule):
    """
    Warns when a user-defined free function is never called.
    """

    def __init__(self):
        self.functions = {}
        self.called = set()
        self.non_decl_tokens = []

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _has_body(self, node):
        for child in node.get("children", []):
            if child.get("kind") == CursorKind.COMPOUND_STMT:
                return True
        return False

    def matches(self, node):
        kind = node.get("kind")

        if kind == CursorKind.FUNCTION_DECL:
            name = node.get("name")
            if not name or name == "main":
                return False
            if self._has_body(node):
                self.functions[name] = node.get("line")
            return False

        tokens = self._tokens(node)
        if tokens:
            self.non_decl_tokens.append(tokens)

        if kind == CursorKind.CALL_EXPR:
            name = node.get("name")
            if name:
                self.called.add(name)

        return False

    def apply(self, node):
        return None

    def finalize(self):
        messages = []

        def referenced_textually(name):
            for tokens in self.non_decl_tokens:
                for i in range(len(tokens) - 1):
                    if tokens[i] == name and tokens[i + 1] == "(":
                        return True
            return False

        for name, line in sorted(self.functions.items(), key=lambda x: (x[1] or 10**9, x[0])):
            if name in self.called or referenced_textually(name):
                continue
            if line:
                messages.append(f"[WARN] Function '{name}' declared on line {line} is never called.")
            else:
                messages.append(f"[WARN] Function '{name}' is never called.")
        return messages
