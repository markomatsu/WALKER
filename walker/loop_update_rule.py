from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class LoopUpdateRule(BaseRule):
    """
    Warns when a loop condition variable does not appear to be updated,
    which may indicate an infinite-loop bug.
    """

    _LOOP_KINDS = {
        CursorKind.WHILE_STMT,
        CursorKind.FOR_STMT,
        CursorKind.DO_STMT,
    }

    _ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}

    def matches(self, node):
        return node.get("kind") in self._LOOP_KINDS

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _for_condition_node(self, node):
        expr_kinds = {
            CursorKind.BINARY_OPERATOR,
            CursorKind.UNARY_OPERATOR,
            CursorKind.PAREN_EXPR,
            CursorKind.UNEXPOSED_EXPR,
            CursorKind.DECL_REF_EXPR,
            CursorKind.INTEGER_LITERAL,
            CursorKind.FLOATING_LITERAL,
            CursorKind.CXX_BOOL_LITERAL_EXPR,
            CursorKind.CALL_EXPR,
        }

        candidates = [c for c in node.get("children", []) if c.get("kind") in expr_kinds]
        for candidate in candidates:
            toks = self._tokens(candidate)
            if any(op in toks for op in ("<", ">", "<=", ">=", "==", "!=", "&&", "||")):
                return candidate
        return candidates[0] if candidates else None

    def _condition_node(self, node):
        if node.get("kind") == CursorKind.FOR_STMT:
            return self._for_condition_node(node)
        return find_condition_node(node)

    def _body_node(self, loop_node):
        children = list(loop_node.get("children", []))
        if not children:
            return None

        if loop_node.get("kind") == CursorKind.DO_STMT:
            return children[0] if children else None

        return children[-1]

    def _decl_refs(self, node):
        out = set()

        def walk(cur):
            if cur.get("kind") == CursorKind.DECL_REF_EXPR and cur.get("name"):
                out.add(cur["name"])
            for child in cur.get("children", []):
                walk(child)

        if node is not None:
            walk(node)
        return out

    def _for_update_clause_tokens(self, node):
        tokens = self._tokens(node)
        if not tokens:
            return []

        try:
            lpar = tokens.index("(")
        except ValueError:
            return []

        depth = 0
        semicolons = []
        rpar = None
        for i in range(lpar + 1, len(tokens)):
            tok = tokens[i]
            if tok == "(":
                depth += 1
            elif tok == ")":
                if depth == 0:
                    rpar = i
                    break
                depth -= 1
            elif tok == ";" and depth == 0:
                semicolons.append(i)

        if rpar is None or len(semicolons) < 2:
            return []

        start = semicolons[1] + 1
        end = rpar
        return tokens[start:end]

    def _tokens_update_var(self, tokens, var_name):
        if var_name not in tokens:
            return False

        for i, tok in enumerate(tokens):
            if tok != var_name:
                continue
            if i + 1 < len(tokens) and tokens[i + 1] in {"++", "--"}:
                return True
            if i > 0 and tokens[i - 1] in {"++", "--"}:
                return True
            if i + 1 < len(tokens) and tokens[i + 1] in self._ASSIGN_OPS:
                return True
        return False

    def _subtree_updates_var(self, node, var_name):
        if node is None:
            return False

        tokens = self._tokens(node)
        if self._tokens_update_var(tokens, var_name):
            return True

        for child in node.get("children", []):
            if self._subtree_updates_var(child, var_name):
                return True
        return False

    def apply(self, node):
        condition = self._condition_node(node)
        if condition is None:
            return None

        condition_vars = sorted(self._decl_refs(condition))
        if not condition_vars:
            return None

        body = self._body_node(node)
        header_update_tokens = []
        if node.get("kind") == CursorKind.FOR_STMT:
            header_update_tokens = self._for_update_clause_tokens(node)

        for var_name in condition_vars:
            updated_in_header = self._tokens_update_var(header_update_tokens, var_name)
            updated_in_body = self._subtree_updates_var(body, var_name)
            if updated_in_header or updated_in_body:
                continue

            line = node.get("line")
            if line:
                return (
                    f"[WARN] Loop on line {line} may not update condition variable "
                    f"'{var_name}' (possible infinite loop)."
                )
            return (
                f"[WARN] Loop may not update condition variable "
                f"'{var_name}' (possible infinite loop)."
            )

        return None
