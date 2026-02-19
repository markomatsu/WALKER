class RuleEngine:
    """
    Applies a collection of rules to a flat list of AST nodes
    and collects human-readable explanations.
    """

    def __init__(self, rules):
        self.rules = rules

    def run(self, nodes):
        explanations = []

        for node in nodes:
            for rule in self.rules:
                # Check if the rule applies to this node
                if rule.matches(node):
                    # Generate explanation
                    result = rule.apply(node)

                    # Only keep meaningful output
                    if result:
                        explanations.append(result)

        for rule in self.rules:
            if hasattr(rule, "finalize"):
                explanations.extend(rule.finalize() or [])

        def line_key(text, index):
            import re
            m = re.search(r"\bline (\d+)\b", text)
            if m:
                return (int(m.group(1)), index)
            return (10**9, index)

        explanations = [
            text for _, text in sorted(
                [(line_key(text, i), text) for i, text in enumerate(explanations)],
                key=lambda x: x[0]
            )
        ]

        return explanations
