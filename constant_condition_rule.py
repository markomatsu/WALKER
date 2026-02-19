import re
from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class ConstantConditionRule(BaseRule):
    """
    Warns when a branch/loop condition looks constant.
    """

    _TARGET_KINDS = {
        CursorKind.IF_STMT,
        CursorKind.WHILE_STMT,
        CursorKind.DO_STMT,
        CursorKind.FOR_STMT,
    }

    _IDENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def matches(self, node):
        return node.get("kind") in self._TARGET_KINDS

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _find_for_condition_node(self, node):
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
            return self._find_for_condition_node(node)
        return find_condition_node(node)

    def _is_identifier(self, token):
        if not self._IDENT_PATTERN.match(token):
            return False
        return token not in {"true", "false", "nullptr"}

    def _parse_number(self, token):
        lowered = token.lower()
        while lowered and lowered[-1] in {"u", "l", "f"}:
            lowered = lowered[:-1]
        if not lowered:
            return None

        try:
            if lowered.startswith("0x"):
                return int(lowered, 16)
            if lowered.startswith("0b"):
                return int(lowered, 2)
            if lowered.startswith("0") and lowered != "0" and lowered.isdigit():
                return int(lowered, 8)
            if "." in lowered or "e" in lowered:
                return float(lowered)
            return int(lowered, 10)
        except ValueError:
            return None

    def _constant_truthiness(self, tokens):
        cleaned = [t for t in tokens if t not in {"(", ")", " ", ";"}]
        if not cleaned:
            return None

        if any(self._is_identifier(t) for t in cleaned):
            return None

        negate_count = 0
        while cleaned and cleaned[0] == "!":
            negate_count += 1
            cleaned = cleaned[1:]

        if not cleaned:
            return None

        value = None

        if len(cleaned) == 1:
            token = cleaned[0]
            if token == "true":
                value = True
            elif token in {"false", "nullptr"}:
                value = False
            elif token.startswith('"') and token.endswith('"'):
                value = len(token) > 2
            else:
                number = self._parse_number(token)
                if number is not None:
                    value = (number != 0)
        elif len(cleaned) == 2 and cleaned[0] in {"+", "-"}:
            number = self._parse_number(cleaned[1])
            if number is not None:
                if cleaned[0] == "-":
                    number = -number
                value = (number != 0)

        if value is None:
            return None

        if negate_count % 2 == 1:
            value = not value
        return value

    def _kind_label(self, kind):
        if kind == CursorKind.IF_STMT:
            return "if-statement"
        if kind == CursorKind.WHILE_STMT:
            return "while-loop"
        if kind == CursorKind.DO_STMT:
            return "do-while loop"
        if kind == CursorKind.FOR_STMT:
            return "for-loop"
        return "condition"

    def apply(self, node):
        condition = self._condition_node(node)
        if condition is None:
            return None

        tokens = self._tokens(condition)
        if not tokens:
            return None

        value = self._constant_truthiness(tokens)
        if value is None:
            return None

        line = node.get("line")
        label = self._kind_label(node.get("kind"))
        truth = "true" if value else "false"

        if line:
            return f"[WARN] Condition in {label} on line {line} is always {truth}."
        return f"[WARN] Condition in {label} is always {truth}."
