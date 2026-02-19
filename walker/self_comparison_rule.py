from clang.cindex import CursorKind

from base_rule import BaseRule


class SelfComparisonRule(BaseRule):
    """
    Warns on comparisons where both sides are syntactically identical.
    Example: x == x, value > value.
    """

    _OPS = {"==", "!=", "<", ">", "<=", ">="}

    def __init__(self):
        self._cxx_operator_call = getattr(CursorKind, "CXX_OPERATOR_CALL_EXPR", None)

    def matches(self, node):
        kind = node.get("kind")
        if kind == CursorKind.BINARY_OPERATOR:
            return True
        return self._cxx_operator_call is not None and kind == self._cxx_operator_call

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _strip_wrapping_parens(self, tokens):
        out = list(tokens)
        while len(out) >= 2 and out[0] == "(" and out[-1] == ")":
            depth = 0
            balanced = True
            for i, tok in enumerate(out):
                if tok == "(":
                    depth += 1
                elif tok == ")":
                    depth -= 1
                if depth == 0 and i != len(out) - 1:
                    balanced = False
                    break
            if not balanced or depth != 0:
                break
            out = out[1:-1]
        return out

    def _normalize_side(self, tokens):
        cleaned = [t for t in tokens if t not in {" ", "\t"}]
        while cleaned and cleaned[-1] in {";", ","}:
            cleaned = cleaned[:-1]
        cleaned = self._strip_wrapping_parens(cleaned)
        return cleaned

    def apply(self, node):
        tokens = self._tokens(node)
        if not tokens:
            return None

        op_index = None
        op_token = None
        for i, tok in enumerate(tokens):
            if tok in self._OPS:
                op_index = i
                op_token = tok
                break

        if op_index is None:
            return None

        left = self._normalize_side(tokens[:op_index])
        right = self._normalize_side(tokens[op_index + 1 :])
        if not left or not right:
            return None

        if left != right:
            return None

        left_text = " ".join(left)
        line = node.get("line")

        always_true_ops = {"==", "<=", ">="}
        result = "true" if op_token in always_true_ops else "false"

        if line:
            return (
                f"[WARN] Self-comparison on line {line}: "
                f"'{left_text} {op_token} {left_text}' is always {result}."
            )
        return f"[WARN] Self-comparison: '{left_text} {op_token} {left_text}' is always {result}."
