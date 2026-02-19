import re

from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class UnreachableElseIfRule(BaseRule):
    """
    Warn when an else-if branch is unreachable because an earlier
    branch in the same chain is statically always true.
    """

    _IDENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def matches(self, node):
        return node.get("kind") == CursorKind.IF_STMT

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _then_else_nodes(self, if_node):
        children = list(if_node.get("children", []))
        cond = find_condition_node(if_node)
        if cond in children:
            children.remove(cond)
        then_node = children[0] if len(children) > 0 else None
        else_node = children[1] if len(children) > 1 else None
        return then_node, else_node

    def _is_else_if(self, node):
        parent = node.get("parent")
        if parent is None or parent.get("kind") != CursorKind.IF_STMT:
            return False
        _then_node, else_node = self._then_else_nodes(parent)
        return else_node is node

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

    def _condition_is_always_true(self, if_node):
        cond = find_condition_node(if_node)
        if cond is None:
            return False
        tokens = self._tokens(cond)
        if not tokens:
            return False
        value = self._constant_truthiness(tokens)
        return value is True

    def apply(self, node):
        # Process each chain once from the top-level if.
        if self._is_else_if(node):
            return None

        current = node
        always_true_line = None
        first = True

        while current is not None and current.get("kind") == CursorKind.IF_STMT:
            line = current.get("line")
            if not first and always_true_line is not None:
                if line:
                    return (
                        f"[WARN] Else-if branch on line {line} is unreachable because "
                        f"an earlier branch on line {always_true_line} is always true."
                    )
                return (
                    "[WARN] Else-if branch is unreachable because an earlier branch "
                    "is always true."
                )

            if always_true_line is None and self._condition_is_always_true(current):
                always_true_line = line

            _then_node, else_node = self._then_else_nodes(current)
            if else_node is not None and else_node.get("kind") == CursorKind.IF_STMT:
                current = else_node
                first = False
                continue
            break

        return None
