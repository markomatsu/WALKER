class Narrator:
    def narrate(self, facts):
        lines = []

        for fact in facts:
            if fact["type"] == "function":
                lines.append(
                    f"This program defines a function named '{fact['name']}'."
                )

            elif fact["type"] == "if_statement":
                lines.append(
                    "Inside the function, the program evaluates a condition."
                )

            elif fact["type"] == "variable":
                lines.append(
                    f"The program declares a variable named '{fact['name']}'."
                )

        return " ".join(lines)
