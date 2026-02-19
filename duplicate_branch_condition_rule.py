from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class DuplicateBranchConditionRule(BaseRule):
    """
    Warns when an else-if condition duplicates an earlier condition
    in the same if/else-if chain.
    """

    def matches(self, node):
        return node.get("kind") == CursorKind.IF_STMT

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _normalized_condition(self, if_node):
        cond = find_condition_node(if_node)
        if cond is None:
            return None
        if self._has_side_effect(cond):
            return None
        tokens = self._tokens(cond)
        if not tokens:
            return None
        normalized = [t for t in tokens if t not in {"(", ")", "{", "}", ";"}]
        return " ".join(normalized)

    def _has_side_effect(self, node):
        if node is None:
            return False

        kind = node.get("kind")

        call_kinds = set()
        for attr in ("CALL_EXPR", "CXX_MEMBER_CALL_EXPR", "CXX_OPERATOR_CALL_EXPR"):
            value = getattr(CursorKind, attr, None)
            if value is not None:
                call_kinds.add(value)

        if kind in call_kinds:
            return True

        tokens = self._tokens(node)
        if kind == CursorKind.UNARY_OPERATOR and ("++" in tokens or "--" in tokens):
            return True

        if kind == CursorKind.BINARY_OPERATOR:
            assign_ops = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}
            if any(op in tokens for op in assign_ops):
                return True

        for child in node.get("children", []):
            if self._has_side_effect(child):
                return True

        return False

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
        _, else_node = self._then_else_nodes(parent)
        return else_node is node

    def apply(self, node):
        if self._is_else_if(node):
            return None

        seen = {}
        current = node
        while current is not None and current.get("kind") == CursorKind.IF_STMT:
            norm = self._normalized_condition(current)
            line = current.get("line")
            if norm:
                if norm in seen:
                    first_line = seen[norm]
                    if line and first_line:
                        return (
                            f"[WARN] Else-if condition on line {line} duplicates "
                            f"an earlier condition from line {first_line}."
                        )
                    if line:
                        return f"[WARN] Else-if condition on line {line} duplicates an earlier condition."
                    return "[WARN] Else-if condition duplicates an earlier condition."
                seen[norm] = line

            _, else_node = self._then_else_nodes(current)
            if else_node is not None and else_node.get("kind") == CursorKind.IF_STMT:
                current = else_node
                continue
            break

        return None
