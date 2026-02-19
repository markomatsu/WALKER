from clang.cindex import CursorKind

from base_rule import BaseRule
from expr_renderer import describe_expr, find_condition_node


class SwitchSafetyRule(BaseRule):
    """
    Reports common switch safety problems:
    - missing default
    - potential fallthrough between case labels
    """

    def __init__(self):
        self.switch_nodes = []
        self._seen = set()
        self._terminator_kinds = {
            CursorKind.BREAK_STMT,
            CursorKind.RETURN_STMT,
            CursorKind.CONTINUE_STMT,
            CursorKind.GOTO_STMT,
        }
        throw_kind = getattr(CursorKind, "CXX_THROW_EXPR", None)
        if throw_kind is not None:
            self._terminator_kinds.add(throw_kind)

    def matches(self, node):
        if node.get("kind") == CursorKind.SWITCH_STMT:
            node_id = id(node)
            if node_id not in self._seen:
                self._seen.add(node_id)
                self.switch_nodes.append(node)
        return False

    def apply(self, node):
        return None

    def _tokens(self, node):
        cursor = node.get("cursor")
        if cursor is None:
            return []
        return [t.spelling for t in cursor.get_tokens()]

    def _descendants(self, node):
        out = [node]
        for child in node.get("children", []):
            out.extend(self._descendants(child))
        return out

    def _switch_body(self, switch_node):
        for child in switch_node.get("children", []):
            if child.get("kind") == CursorKind.COMPOUND_STMT:
                return child
        return None

    def _has_default(self, switch_node):
        for node in self._descendants(switch_node):
            if node.get("kind") == CursorKind.DEFAULT_STMT:
                return True
        return False

    def _label_text(self, label_node):
        if label_node.get("kind") == CursorKind.DEFAULT_STMT:
            return "default"

        tokens = self._tokens(label_node)
        if "case" in tokens and ":" in tokens:
            start = tokens.index("case") + 1
            end = len(tokens) - 1 - tokens[::-1].index(":")
            if start < end:
                text = " ".join(tokens[start:end]).strip()
                if text:
                    return text

        for child in label_node.get("children", []):
            text = describe_expr(child)
            if text and text != "an expression":
                return text
        return "case"

    def _contains_terminator(self, nodes):
        for node in nodes:
            for descendant in self._descendants(node):
                if descendant.get("kind") in self._terminator_kinds:
                    return True
        return False

    def _has_fallthrough_marker(self, nodes):
        for node in nodes:
            tokens = self._tokens(node)
            if any(tok.lower() == "fallthrough" for tok in tokens):
                return True
        return False

    def _fallthrough_messages(self, switch_node):
        messages = []
        body = self._switch_body(switch_node)
        if body is None:
            return messages

        children = body.get("children", [])
        labels = [
            (i, child)
            for i, child in enumerate(children)
            if child.get("kind") in {CursorKind.CASE_STMT, CursorKind.DEFAULT_STMT}
        ]
        if len(labels) < 2:
            return messages

        for idx, (start, label) in enumerate(labels[:-1]):
            next_start = labels[idx + 1][0]
            section_nodes = children[start:next_start]
            if self._has_fallthrough_marker(section_nodes):
                continue
            if self._contains_terminator(section_nodes):
                continue

            label_text = self._label_text(label)
            line = label.get("line") or switch_node.get("line")
            if line:
                messages.append(
                    f"[WARN] Switch case '{label_text}' on line {line} may fall through to the next case."
                )
            else:
                messages.append(f"[WARN] Switch case '{label_text}' may fall through to the next case.")

        return messages

    def finalize(self):
        messages = []

        for switch_node in self.switch_nodes:
            line = switch_node.get("line")
            if not self._has_default(switch_node):
                condition = find_condition_node(switch_node)
                condition_text = describe_expr(condition) if condition is not None else None
                if line and condition_text:
                    messages.append(
                        f"[WARN] Switch statement on line {line} over {condition_text} has no default case."
                    )
                elif line:
                    messages.append(f"[WARN] Switch statement on line {line} has no default case.")
                else:
                    messages.append("[WARN] Switch statement has no default case.")

            messages.extend(self._fallthrough_messages(switch_node))

        return messages
