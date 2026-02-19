import re

from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import describe_expr, find_condition_node


class IOStreamRule(BaseRule):
    """
    Describe basic iostream usage (cin/cout/cerr/clog).
    AST detection is primary; fallback scanning is used only when
    a file has no AST-detected IO at all.
    """

    _OUTPUT_NAMES = {"cout", "cerr", "clog"}
    _INPUT_NAMES = {"cin"}
    _SKIP_OUTPUT_ITEMS = {"std", "::", "endl", "std::endl"}

    def __init__(self):
        self._seen_files = set()
        self._ast_io_found_files = set()
        self._emitted_keys = set()
        self._candidate_kinds = {
            CursorKind.UNEXPOSED_EXPR,
            CursorKind.BINARY_OPERATOR,
            CursorKind.CALL_EXPR,
        }
        self._cxx_operator_call = getattr(CursorKind, "CXX_OPERATOR_CALL_EXPR", None)

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _has_stream_token(self, tokens, names):
        for tok in tokens:
            base = tok.split("::")[-1]
            if base in names:
                return True
        return False

    def _node_has_io(self, node):
        tokens = self._tokens(node)
        if not tokens:
            return False
        has_shift = ("<<" in tokens) or (">>" in tokens)
        if not has_shift:
            return False
        return self._has_stream_token(tokens, self._OUTPUT_NAMES | self._INPUT_NAMES)

    def _is_descendant(self, node, root):
        cur = node
        while cur is not None:
            if cur is root:
                return True
            cur = cur.get("parent")
        return False

    def _if_context(self, node):
        cur = node.get("parent")
        while cur is not None:
            if cur.get("kind") == CursorKind.IF_STMT:
                cond_node = find_condition_node(cur)
                condition = describe_expr(cond_node) if cond_node is not None else None

                children = list(cur.get("children", []))
                if cond_node in children:
                    children.remove(cond_node)
                then_node = children[0] if len(children) > 0 else None
                else_node = children[1] if len(children) > 1 else None

                in_else = else_node is not None and self._is_descendant(node, else_node)
                if in_else:
                    if condition:
                        return f"Inside the else-branch of an if-statement that checks whether {condition}, "
                    return "Inside the else-branch of an if-statement, "
                if condition:
                    return f"Inside an if-statement that checks whether {condition}, "
                return "Inside an if-statement, "
            cur = cur.get("parent")
        return ""

    def _switch_context(self, node):
        switch_node = None
        case_node = None
        cur = node.get("parent")
        while cur is not None:
            kind = cur.get("kind")
            if kind == CursorKind.SWITCH_STMT:
                switch_node = cur
                break
            if kind in {CursorKind.CASE_STMT, CursorKind.DEFAULT_STMT} and case_node is None:
                case_node = cur
            cur = cur.get("parent")

        if switch_node is None:
            return ""

        cond_node = find_condition_node(switch_node)
        switch_expr = describe_expr(cond_node) if cond_node is not None else None

        if case_node is None:
            if switch_expr:
                return f"Inside a switch statement over {switch_expr}, "
            return "Inside a switch statement, "

        if case_node.get("kind") == CursorKind.DEFAULT_STMT:
            if switch_expr:
                return f"Inside a switch statement over {switch_expr}, default case, "
            return "Inside a switch statement, default case, "

        case_label = None
        for child in case_node.get("children", []):
            text = describe_expr(child)
            if text and text != "an expression":
                case_label = text
                break
        if not case_label:
            case_label = "case"

        if switch_expr:
            return f"Inside a switch statement over {switch_expr}, case {case_label}, "
        return f"Inside a switch statement, case {case_label}, "

    def _prefix(self, node):
        # Switch context is usually broader, so place it first.
        return f"{self._switch_context(node)}{self._if_context(node)}"

    def _with_prefix(self, prefix, sentence):
        if not prefix:
            return sentence
        if not sentence:
            return prefix
        return prefix + sentence[0].lower() + sentence[1:]

    def _stream_target(self, tokens):
        if self._has_stream_token(tokens, {"cerr"}):
            return "standard error"
        if self._has_stream_token(tokens, {"clog"}):
            return "standard log"
        return "standard output"

    def _extract_output_item(self, tokens):
        for i, tok in enumerate(tokens):
            if tok != "<<" or i + 1 >= len(tokens):
                continue
            nxt = tokens[i + 1]
            if nxt in self._SKIP_OUTPUT_ITEMS:
                continue
            if nxt in {"cout", "cin", "cerr", "clog", "std::cout", "std::cin", "std::cerr", "std::clog"}:
                continue
            if nxt == "std" and i + 2 < len(tokens) and tokens[i + 2] == "::":
                continue
            return nxt
        return None

    def _extract_input_target(self, tokens):
        for i, tok in enumerate(tokens):
            if tok != ">>" or i + 1 >= len(tokens):
                continue
            nxt = tokens[i + 1]
            if nxt in {"std", "::", "cin", "std::cin"}:
                continue
            return nxt
        return None

    def _subtree_nodes(self, node):
        out = [node]
        for child in node.get("children", []):
            out.extend(self._subtree_nodes(child))
        return out

    def _literal_or_name_fallback(self, node, for_input=False):
        for cur in self._subtree_nodes(node):
            kind = cur.get("kind")
            if not for_input and kind in {
                CursorKind.STRING_LITERAL,
                CursorKind.INTEGER_LITERAL,
                CursorKind.FLOATING_LITERAL,
                CursorKind.CHARACTER_LITERAL,
                CursorKind.CXX_BOOL_LITERAL_EXPR,
            }:
                toks = self._tokens(cur)
                if toks:
                    return toks[0]

            toks = self._tokens(cur)
            for tok in toks:
                if tok.startswith('"') and tok.endswith('"'):
                    return tok

            if kind == CursorKind.DECL_REF_EXPR:
                name = cur.get("name") or ""
                if name and name not in self._OUTPUT_NAMES and name not in self._INPUT_NAMES:
                    return name

        return None

    def matches(self, node):
        path = node.get("file")
        if path:
            self._seen_files.add(path)

        kind = node.get("kind")
        if kind not in self._candidate_kinds and kind != self._cxx_operator_call:
            return False

        if not self._node_has_io(node):
            return False

        parent = node.get("parent")
        while parent is not None:
            parent_kind = parent.get("kind")
            if parent_kind in self._candidate_kinds or parent_kind == self._cxx_operator_call:
                if self._node_has_io(parent):
                    return False
            parent = parent.get("parent")

        return True

    def apply(self, node):
        tokens = self._tokens(node)
        line = node.get("line")
        path = node.get("file")
        if not line:
            return None

        has_output = ("<<" in tokens) and self._has_stream_token(tokens, self._OUTPUT_NAMES)
        has_input = (">>" in tokens) and self._has_stream_token(tokens, self._INPUT_NAMES)

        if not has_output and not has_input:
            return None

        prefix = self._prefix(node)

        if has_output:
            item = self._extract_output_item(tokens)
            if item is None:
                item = self._literal_or_name_fallback(node, for_input=False)
            target = self._stream_target(tokens)
            key = (path, line, "output", item or "")
            if key in self._emitted_keys:
                return None
            self._emitted_keys.add(key)
            if path:
                self._ast_io_found_files.add(path)

            if item:
                return self._with_prefix(prefix, f"This outputs {item} to {target} on line {line}.")
            return self._with_prefix(prefix, f"This outputs a value to {target} on line {line}.")

        item = self._extract_input_target(tokens)
        if item is None:
            item = self._literal_or_name_fallback(node, for_input=True)
        key = (path, line, "input", item or "")
        if key in self._emitted_keys:
            return None
        self._emitted_keys.add(key)
        if path:
            self._ast_io_found_files.add(path)

        if item:
            return self._with_prefix(prefix, f"This reads input into {item} from standard input on line {line}.")
        return self._with_prefix(prefix, f"This reads a value from standard input on line {line}.")

    def _fallback_messages_for_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return []

        messages = []
        for idx, raw in enumerate(lines, start=1):
            line = re.sub(r"//.*$", "", raw).strip()
            if not line:
                continue

            has_output = ("<<" in line) and re.search(r"\b(cout|cerr|clog|std::cout|std::cerr|std::clog)\b", line)
            has_input = (">>" in line) and re.search(r"\b(cin|std::cin)\b", line)
            if not has_output and not has_input:
                continue

            if has_output:
                key = (path, idx, "output", "")
                if key not in self._emitted_keys:
                    self._emitted_keys.add(key)
                    messages.append(f"This outputs a value to standard output on line {idx}.")
            if has_input:
                key = (path, idx, "input", "")
                if key not in self._emitted_keys:
                    self._emitted_keys.add(key)
                    messages.append(f"This reads a value from standard input on line {idx}.")

        return messages

    def finalize(self):
        messages = []
        for path in sorted(self._seen_files):
            if path in self._ast_io_found_files:
                continue
            messages.extend(self._fallback_messages_for_file(path))
        return messages
