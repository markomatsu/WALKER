from clang.cindex import CursorKind

from base_rule import BaseRule


class UninitializedLocalRule(BaseRule):
    """
    Basic check for local variables used before first assignment.
    """

    _ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}

    def __init__(self):
        # func_key -> usr -> meta
        self.vars = {}
        self._warned = set()

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _enclosing_function(self, node):
        cur = node.get("parent")
        while cur is not None:
            if cur.get("kind") == CursorKind.FUNCTION_DECL:
                return cur
            cur = cur.get("parent")
        return None

    def _func_key(self, func_node):
        cursor = func_node.get("cursor")
        if cursor is None:
            return f"func:{id(func_node)}"
        usr = cursor.get_usr()
        if usr:
            return usr
        return f"func:{id(func_node)}"

    def _var_usr(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return None
        usr = cursor.get_usr()
        if usr:
            return usr
        return None

    def _referenced_usr(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return None
        try:
            referenced = cursor.referenced
        except Exception:
            referenced = None
        if referenced is None:
            return None
        usr = referenced.get_usr()
        return usr or None

    def _has_initializer(self, node):
        tokens = self._tokens(node)
        if not tokens:
            return False

        if "=" in tokens:
            return True

        name = node.get("name")
        if not name:
            return False
        try:
            idx = tokens.index(name)
        except ValueError:
            return False
        for tok in tokens[idx + 1 :]:
            if tok in {"(", "{", ")"}:
                return True
        return False

    def _assignment_target_usr(self, node):
        kind = node.get("kind")
        tokens = self._tokens(node)

        if kind == CursorKind.BINARY_OPERATOR:
            if not any(op in tokens for op in self._ASSIGN_OPS):
                return None
            children = node.get("children", [])
            if not children:
                return None
            lhs = children[0]
            lhs_kind = lhs.get("kind")
            if lhs_kind != CursorKind.DECL_REF_EXPR:
                return None
            return self._referenced_usr(lhs)

        if kind == CursorKind.UNARY_OPERATOR:
            tokens = self._tokens(node)
            if "++" not in tokens and "--" not in tokens:
                return None
            children = node.get("children", [])
            if not children:
                return None
            target = children[0]
            if target.get("kind") != CursorKind.DECL_REF_EXPR:
                return None
            return self._referenced_usr(target)

        # Treat cin >> var as an assignment-like initialization.
        if ">>" in tokens and ("cin" in tokens or "std::cin" in tokens):
            children = list(node.get("children", []))
            for child in reversed(children):
                if child.get("kind") != CursorKind.DECL_REF_EXPR:
                    continue
                name = child.get("name") or ""
                if name in {"cin", "std::cin"}:
                    continue
                return self._referenced_usr(child)

        return None

    def matches(self, node):
        func = self._enclosing_function(node)
        if func is None:
            return False

        fkey = self._func_key(func)
        if fkey not in self.vars:
            self.vars[fkey] = {}

        kind = node.get("kind")

        if kind == CursorKind.VAR_DECL:
            usr = self._var_usr(node)
            if not usr:
                return False
            if self._has_initializer(node):
                return False
            if usr not in self.vars[fkey]:
                self.vars[fkey][usr] = {
                    "name": node.get("name") or "variable",
                    "decl_line": node.get("line"),
                    "first_assign_line": None,
                    "first_use_line": None,
                }
            return False

        target_usr = self._assignment_target_usr(node)
        if target_usr and target_usr in self.vars[fkey]:
            line = node.get("line")
            if isinstance(line, int):
                cur = self.vars[fkey][target_usr]["first_assign_line"]
                if cur is None or line < cur:
                    self.vars[fkey][target_usr]["first_assign_line"] = line
            return False

        if kind == CursorKind.DECL_REF_EXPR:
            usr = self._referenced_usr(node)
            if not usr or usr not in self.vars[fkey]:
                return False
            line = node.get("line")
            if isinstance(line, int):
                cur = self.vars[fkey][usr]["first_use_line"]
                if cur is None or line < cur:
                    self.vars[fkey][usr]["first_use_line"] = line
            return False

        return False

    def apply(self, node):
        return None

    def finalize(self):
        messages = []
        for _fkey, by_usr in self.vars.items():
            for usr, meta in by_usr.items():
                use_line = meta.get("first_use_line")
                assign_line = meta.get("first_assign_line")
                name = meta.get("name")

                if use_line is None:
                    continue
                if assign_line is not None and use_line >= assign_line:
                    continue

                dedupe_key = (usr, use_line)
                if dedupe_key in self._warned:
                    continue
                self._warned.add(dedupe_key)

                if assign_line is None:
                    messages.append(
                        f"[WARN] Local variable '{name}' is used on line {use_line} before it is initialized."
                    )
                else:
                    messages.append(
                        f"[WARN] Local variable '{name}' is used on line {use_line} before first assignment on line {assign_line}."
                    )
        return messages
