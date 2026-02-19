from collections import defaultdict

from clang.cindex import CursorKind

from base_rule import BaseRule


class ClassFieldRule(BaseRule):
    """
    Basic class-field diagnostics:
    - field never used
    - field possibly uninitialized
    """

    _CLASS_KINDS = {CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL}
    _ASSIGN_TOKENS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}

    def __init__(self):
        self.classes = {}
        self.class_field_usage = defaultdict(set)
        self.global_field_like_usage = set()

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _enclosing_class(self, node):
        cur = node.get("parent")
        while cur is not None:
            if cur.get("kind") in self._CLASS_KINDS:
                return cur
            cur = cur.get("parent")
        return None

    def _ensure_class(self, class_name):
        if class_name not in self.classes:
            self.classes[class_name] = {
                "fields": {},
                "constructors": [],
            }
        return self.classes[class_name]

    def _has_inline_initializer(self, field_node):
        tokens = self._tokens(field_node)
        return ("=" in tokens) or ("{" in tokens and "}" in tokens)

    def matches(self, node):
        kind = node.get("kind")

        if kind in self._CLASS_KINDS:
            class_name = node.get("name")
            if class_name:
                self._ensure_class(class_name)
            return False

        if kind == CursorKind.FIELD_DECL:
            class_node = self._enclosing_class(node)
            if class_node is None:
                return False
            class_name = class_node.get("name")
            field_name = node.get("name")
            if not class_name or not field_name:
                return False
            data = self._ensure_class(class_name)
            data["fields"][field_name] = {
                "line": node.get("line"),
                "inline_init": self._has_inline_initializer(node),
            }
            return False

        if kind == CursorKind.CONSTRUCTOR:
            class_node = self._enclosing_class(node)
            if class_node is None:
                return False
            class_name = class_node.get("name")
            if not class_name:
                return False
            data = self._ensure_class(class_name)
            data["constructors"].append(node)
            return False

        if kind == CursorKind.MEMBER_REF_EXPR:
            member_name = node.get("name")
            if not member_name:
                return False

            parent = node.get("parent")
            if parent is not None and parent.get("kind") == CursorKind.CALL_EXPR:
                # Method call (obj.method()), not a field usage.
                return False

            class_node = self._enclosing_class(node)
            if class_node is not None and class_node.get("name"):
                self.class_field_usage[class_node["name"]].add(member_name)
            self.global_field_like_usage.add(member_name)
            return False

        return False

    def apply(self, node):
        return None

    def _ctor_init_list_fields(self, ctor_node, field_names):
        tokens = self._tokens(ctor_node)
        if not tokens:
            return set()

        colon_idx = None
        for i, tok in enumerate(tokens):
            if tok != ":":
                continue
            prev_tok = tokens[i - 1] if i > 0 else None
            next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
            if prev_tok == ":" or next_tok == ":":
                continue
            colon_idx = i
            break

        if colon_idx is None:
            return set()

        end_idx = len(tokens)
        for i in range(colon_idx + 1, len(tokens)):
            if tokens[i] == "{":
                end_idx = i
                break

        initialized = set()
        for i in range(colon_idx + 1, end_idx - 1):
            tok = tokens[i]
            nxt = tokens[i + 1]
            if tok in field_names and nxt in {"(", "{", "="}:
                initialized.add(tok)
        return initialized

    def _ctor_assigned_fields(self, ctor_node, field_names):
        tokens = self._tokens(ctor_node)
        if not tokens:
            return set()

        assigned = set()
        for i, tok in enumerate(tokens):
            if tok not in field_names:
                continue
            prev_tok = tokens[i - 1] if i > 0 else None
            next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
            if next_tok in self._ASSIGN_TOKENS or next_tok in {"++", "--"}:
                assigned.add(tok)
            elif prev_tok in {"++", "--"}:
                assigned.add(tok)
        return assigned

    def _ctor_initialized_fields(self, ctor_node, field_names):
        initialized = set()
        initialized.update(self._ctor_init_list_fields(ctor_node, field_names))
        initialized.update(self._ctor_assigned_fields(ctor_node, field_names))
        return initialized

    def finalize(self):
        messages = []

        for class_name, data in sorted(self.classes.items()):
            fields = data.get("fields", {})
            constructors = data.get("constructors", [])
            if not fields:
                continue

            usage_for_class = self.class_field_usage.get(class_name, set())

            for field_name, meta in fields.items():
                field_line = meta.get("line")

                used = (field_name in usage_for_class) or (field_name in self.global_field_like_usage)
                if not used:
                    if field_line:
                        messages.append(
                            f"[WARN] Field '{field_name}' in class '{class_name}' declared at line "
                            f"{field_line} is never used."
                        )
                    else:
                        messages.append(f"[WARN] Field '{field_name}' in class '{class_name}' is never used.")

                if meta.get("inline_init"):
                    continue

                if not constructors:
                    if field_line:
                        messages.append(
                            f"[WARN] Field '{field_name}' in class '{class_name}' declared at line "
                            f"{field_line} may be uninitialized."
                        )
                    else:
                        messages.append(
                            f"[WARN] Field '{field_name}' in class '{class_name}' may be uninitialized."
                        )
                    continue

                missing_ctor_line = None
                for ctor in constructors:
                    initialized = self._ctor_initialized_fields(ctor, set(fields.keys()))
                    if field_name not in initialized:
                        missing_ctor_line = ctor.get("line")
                        break

                if missing_ctor_line is not None:
                    messages.append(
                        f"[WARN] Field '{field_name}' in class '{class_name}' may be uninitialized "
                        f"in constructor on line {missing_ctor_line}."
                    )

        return messages
