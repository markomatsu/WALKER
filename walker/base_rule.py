class BaseRule:
    def matches(self, node):
        raise NotImplementedError("matches() must be implemented")

    def apply(self, node):
        raise NotImplementedError("apply() must be implemented")

    def finalize(self):
        """
        Optional hook for rules that need a full-AST pass before reporting.
        """
        return []
