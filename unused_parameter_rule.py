from clang.cindex import CursorKind

from base_rule import BaseRule


class UnusedParameterRule(BaseRule):
    """
    Warns when a function/method parameter is never referenced.
    """

    _FUNC_KINDS = {CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD}

    def __init__(self):
        self.func_meta = {}
        self.params = {}
        self.used_names = {}
        self.func_tokens = {}

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _enclosing_function(self, node):
        cur = node.get("parent")
        while cur is not None:
            if cur.get("kind") in self._FUNC_KINDS:
                return cur
            cur = cur.get("parent")
        return None

    def matches(self, node):
        kind = node.get("kind")

        if kind in self._FUNC_KINDS:
            key = id(node)
            if key not in self.func_meta:
                self.func_meta[key] = {
                    "name": node.get("name") or "anonymous",
                    "line": node.get("line"),
                }
                self.params[key] = []
                self.used_names[key] = set()
                self.func_tokens[key] = []
            return False

        if kind == CursorKind.PARM_DECL:
            func = self._enclosing_function(node)
            if func is None:
                return False
            key = id(func)
            if key not in self.func_meta:
                self.func_meta[key] = {
                    "name": func.get("name") or "anonymous",
                    "line": func.get("line"),
                }
                self.params[key] = []
                self.used_names[key] = set()
                self.func_tokens[key] = []
            self.params[key].append((node.get("name"), node.get("line")))
            return False

        if kind == CursorKind.DECL_REF_EXPR and node.get("name"):
            func = self._enclosing_function(node)
            if func is None:
                return False
            key = id(func)
            if key not in self.used_names:
                self.used_names[key] = set()
            self.used_names[key].add(node["name"])
            return False

        func = self._enclosing_function(node)
        if func is not None and kind != CursorKind.PARM_DECL:
            key = id(func)
            if key not in self.func_tokens:
                self.func_tokens[key] = []
            tokens = self._tokens(node)
            if tokens:
                self.func_tokens[key].append(tokens)

        return False

    def apply(self, node):
        return None

    def finalize(self):
        messages = []
        for key, params in self.params.items():
            if not params:
                continue
            used = self.used_names.get(key, set())
            token_chunks = self.func_tokens.get(key, [])
            func_name = self.func_meta.get(key, {}).get("name", "anonymous")
            for param_name, line in params:
                if not param_name:
                    continue
                textual_use = any(param_name in chunk for chunk in token_chunks)
                if param_name in used or textual_use:
                    continue
                if line:
                    messages.append(
                        f"[WARN] Parameter '{param_name}' in function '{func_name}' "
                        f"on line {line} is never used."
                    )
                else:
                    messages.append(
                        f"[WARN] Parameter '{param_name}' in function '{func_name}' is never used."
                    )
        return messages
