from clang.cindex import CursorKind
from base_rule import BaseRule


class UnusedVariableRule(BaseRule):
    def __init__(self):
        self.declared = set()
        self.used = set()

    def matches(self, node):
        if node["kind"] == CursorKind.VAR_DECL:
            self.declared.add((node["name"], node["line"]))

        if node["kind"] == CursorKind.DECL_REF_EXPR:
            self.used.add(node["name"])

        return False  # diagnostics trigger at end

    def apply(self, node):
        return None

    def finalize(self):
        messages = []
        for name, line in self.declared:
            if name not in self.used:
                messages.append(
                    f"⚠️ Variable '{name}' declared at line {line} is never used."
                )
        return messages
