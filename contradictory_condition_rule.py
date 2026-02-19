from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class ContradictoryConditionRule(BaseRule):
    """
    Detects simple contradictory conjunctions like:
    - x < 5 && x > 10
    - x == 3 && x != 3
    """

    _TARGET_KINDS = {
        CursorKind.IF_STMT,
        CursorKind.WHILE_STMT,
        CursorKind.DO_STMT,
        CursorKind.FOR_STMT,
    }

    def __init__(self):
        self._cxx_operator_call = getattr(CursorKind, "CXX_OPERATOR_CALL_EXPR", None)

    def matches(self, node):
        return node.get("kind") in self._TARGET_KINDS

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _operator(self, node, operators):
        for tok in self._tokens(node):
            if tok in operators:
                return tok
        return None

    def _unwrap(self, node):
        cur = node
        while cur is not None and cur.get("kind") in {CursorKind.UNEXPOSED_EXPR, CursorKind.PAREN_EXPR}:
            children = cur.get("children", [])
            if not children:
                break
            cur = children[0]
        return cur

    def _parse_number(self, token):
        text = token.lower()
        while text and text[-1] in {"u", "l", "f"}:
            text = text[:-1]
        if not text:
            return None

        try:
            if text.startswith("0x"):
                return int(text, 16)
            if text.startswith("0b"):
                return int(text, 2)
            if text.startswith("0") and text != "0" and text.isdigit():
                return int(text, 8)
            if "." in text or "e" in text:
                return float(text)
            return int(text, 10)
        except ValueError:
            return None

    def _literal_value(self, node):
        node = self._unwrap(node)
        if node is None:
            return None
        if node.get("kind") not in {CursorKind.INTEGER_LITERAL, CursorKind.FLOATING_LITERAL}:
            return None
        tokens = self._tokens(node)
        if not tokens:
            return None
        return self._parse_number(tokens[0])

    def _var_name(self, node):
        node = self._unwrap(node)
        if node is None:
            return None
        if node.get("kind") == CursorKind.DECL_REF_EXPR and node.get("name"):
            return node["name"]
        return None

    def _reverse_op(self, op):
        return {
            "<": ">",
            "<=": ">=",
            ">": "<",
            ">=": "<=",
            "==": "==",
            "!=": "!=",
        }.get(op)

    def _atomic_comparison(self, node):
        node = self._unwrap(node)
        if node is None:
            return None

        kind = node.get("kind")
        if kind == CursorKind.BINARY_OPERATOR:
            op = self._operator(node, {"<", "<=", ">", ">=", "==", "!="})
        elif self._cxx_operator_call is not None and kind == self._cxx_operator_call:
            op = self._operator(node, {"<", "<=", ">", ">=", "==", "!="})
        else:
            return None

        if op is None:
            return None

        children = node.get("children", [])
        if len(children) < 2:
            return None

        left = self._unwrap(children[0])
        right = self._unwrap(children[1])
        left_var = self._var_name(left)
        right_var = self._var_name(right)
        left_val = self._literal_value(left)
        right_val = self._literal_value(right)

        if left_var is not None and right_val is not None:
            return left_var, op, float(right_val)
        if right_var is not None and left_val is not None:
            rev = self._reverse_op(op)
            if rev is None:
                return None
            return right_var, rev, float(left_val)

        return None

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
        for c in candidates:
            toks = self._tokens(c)
            if any(op in toks for op in ("<", ">", "<=", ">=", "==", "!=", "&&")):
                return c
        return candidates[0] if candidates else None

    def _condition_node(self, node):
        if node.get("kind") == CursorKind.FOR_STMT:
            return self._for_condition_node(node)
        return find_condition_node(node)

    def _constraints_conflict(self, c1, c2):
        _, op1, v1 = c1
        _, op2, v2 = c2

        eq = None
        neq = set()
        low = float("-inf")
        high = float("inf")
        low_inc = True
        high_inc = True

        def apply(op, v):
            nonlocal eq, low, high, low_inc, high_inc
            if op == "==":
                eq = v if eq is None else eq
                if eq != v:
                    return False
            elif op == "!=":
                neq.add(v)
            elif op == ">":
                if v > low or (v == low and low_inc):
                    low = v
                    low_inc = False
            elif op == ">=":
                if v > low:
                    low = v
                    low_inc = True
                elif v == low:
                    low_inc = low_inc and True
            elif op == "<":
                if v < high or (v == high and high_inc):
                    high = v
                    high_inc = False
            elif op == "<=":
                if v < high:
                    high = v
                    high_inc = True
                elif v == high:
                    high_inc = high_inc and True
            return True

        if not apply(op1, v1) or not apply(op2, v2):
            return True

        if eq is not None:
            if eq in neq:
                return True
            if eq < low or eq > high:
                return True
            if eq == low and not low_inc:
                return True
            if eq == high and not high_inc:
                return True
            return False

        if low > high:
            return True
        if low == high and not (low_inc and high_inc):
            return True
        if low == high and low in neq:
            return True
        return False

    def apply(self, node):
        condition = self._condition_node(node)
        condition = self._unwrap(condition)
        if condition is None:
            return None

        kind = condition.get("kind")
        op = None
        if kind == CursorKind.BINARY_OPERATOR:
            op = self._operator(condition, {"&&"})
        elif self._cxx_operator_call is not None and kind == self._cxx_operator_call:
            op = self._operator(condition, {"&&"})

        if op != "&&":
            return None

        children = condition.get("children", [])
        if len(children) < 2:
            return None

        c1 = self._atomic_comparison(children[0])
        c2 = self._atomic_comparison(children[1])
        if c1 is None or c2 is None:
            return None
        if c1[0] != c2[0]:
            return None

        if not self._constraints_conflict(c1, c2):
            return None

        line = node.get("line")
        var_name = c1[0]
        if line:
            return (
                f"[WARN] Contradictory condition on line {line} for '{var_name}' "
                "is always false."
            )
        return f"[WARN] Contradictory condition for '{var_name}' is always false."
