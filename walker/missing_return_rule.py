from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import find_condition_node


class MissingReturnRule(BaseRule):
    """
    Warn when a non-void function may end without returning a value.
    """

    def __init__(self):
        self._functions = []
        self._seen = set()

    def matches(self, node):
        if node.get("kind") != CursorKind.FUNCTION_DECL:
            return False

        node_id = id(node)
        if node_id in self._seen:
            return False

        self._seen.add(node_id)
        self._functions.append(node)
        return False

    def apply(self, node):
        return None

    def _has_body(self, func_node):
        return any(child.get("kind") == CursorKind.COMPOUND_STMT for child in func_node.get("children", []))

    def _return_type(self, func_node):
        cursor = func_node.get("cursor")
        if cursor is None:
            return None
        try:
            return cursor.result_type.spelling
        except Exception:
            return None

    def _function_body(self, func_node):
        for child in func_node.get("children", []):
            if child.get("kind") == CursorKind.COMPOUND_STMT:
                return child
        return None

    def _if_then_else(self, if_node):
        children = list(if_node.get("children", []))
        cond = find_condition_node(if_node)
        if cond in children:
            children.remove(cond)
        then_node = children[0] if len(children) > 0 else None
        else_node = children[1] if len(children) > 1 else None
        return then_node, else_node

    def _stmt_guarantees_return(self, node):
        kind = node.get("kind")

        if kind == CursorKind.RETURN_STMT:
            return True

        if kind == CursorKind.COMPOUND_STMT:
            return self._block_guarantees_return(node)

        if kind == CursorKind.IF_STMT:
            then_node, else_node = self._if_then_else(node)
            if then_node is None or else_node is None:
                return False
            return self._stmt_guarantees_return(then_node) and self._stmt_guarantees_return(else_node)

        if kind == CursorKind.SWITCH_STMT:
            return self._switch_guarantees_return(node)

        return False

    def _block_guarantees_return(self, block_node):
        for child in block_node.get("children", []):
            if self._stmt_guarantees_return(child):
                return True
        return False

    def _switch_guarantees_return(self, switch_node):
        body = None
        for child in switch_node.get("children", []):
            if child.get("kind") == CursorKind.COMPOUND_STMT:
                body = child
                break

        if body is None:
            return False

        entries = []
        current_label = None
        current_nodes = []

        for child in body.get("children", []):
            if child.get("kind") in {CursorKind.CASE_STMT, CursorKind.DEFAULT_STMT}:
                if current_label is not None:
                    entries.append((current_label, current_nodes))
                current_label = child
                current_nodes = [child]
            else:
                if current_label is not None:
                    current_nodes.append(child)

        if current_label is not None:
            entries.append((current_label, current_nodes))

        if not entries:
            return False

        has_default = any(label.get("kind") == CursorKind.DEFAULT_STMT for label, _ in entries)
        if not has_default:
            return False

        for _label, nodes in entries:
            if not any(self._stmt_guarantees_return(stmt) for stmt in nodes):
                return False

        return True

    def _needs_return_check(self, func_node):
        name = func_node.get("name") or ""
        if name == "main":
            return False

        return_type = (self._return_type(func_node) or "").strip()
        if not return_type:
            return False
        if return_type == "void":
            return False

        return True

    def finalize(self):
        messages = []

        for func in self._functions:
            if not self._has_body(func):
                continue
            if not self._needs_return_check(func):
                continue

            body = self._function_body(func)
            if body is None:
                continue

            if self._block_guarantees_return(body):
                continue

            name = func.get("name") or "anonymous"
            line = func.get("line")
            if line:
                messages.append(
                    f"❌ Function '{name}' declared at line {line} may exit without returning a value on some paths."
                )
            else:
                messages.append(f"❌ Function '{name}' may exit without returning a value on some paths.")

        return messages
