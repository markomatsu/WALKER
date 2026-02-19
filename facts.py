class Facts:
    def __init__(self):
        self.items = []

    def add(self, fact):
        if fact:
            self.items.append(fact)

    def all(self):
        return self.items
