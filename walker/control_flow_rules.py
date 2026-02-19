from clang.cindex import CursorKind
from base_rule import BaseRule
from expr_renderer import describe_expr, find_condition_node


class ControlFlowRule(BaseRule):
    """
    Rule responsible for describing C/C++ control-flow constructs.

    NOTE:
    This rule currently operates on a *flat* AST representation.
    As a result, it does not attempt to reconstruct conditions
    or nested expressions. That responsibility belongs either
    to the AST walker or a dedicated expression analyzer.
    """

    def matches(self, node: dict) -> bool:
        """
        Determine whether this rule applies to the given AST node.
        """
        return node.get("kind") in {
            CursorKind.IF_STMT,
            CursorKind.SWITCH_STMT,
            CursorKind.CASE_STMT,
            CursorKind.DEFAULT_STMT,
        }

    def apply(self, node: dict) -> str | None:
        """
        Generate a human-readable description of the control-flow node.
        """
        line = node.get("line")

        kind = node.get("kind")
        if kind == CursorKind.IF_STMT:
            if line is None:
                return "This is an if-statement."

            condition_node = find_condition_node(node)
            if condition_node is None:
                return f"This is an if-statement on line {line}."

            condition_text = describe_expr(condition_node)
            return f"This is an if-statement on line {line} checking whether {condition_text}."

        if kind == CursorKind.SWITCH_STMT:
            if line is None:
                return "This is a switch statement."

            condition_node = find_condition_node(node)
            if condition_node is None:
                return f"This is a switch statement on line {line}."

            condition_text = describe_expr(condition_node)
            return f"This is a switch statement on line {line} over {condition_text}."

        if kind == CursorKind.CASE_STMT:
            if line is None:
                return "This is a case label."

            case_expr = None
            for child in node.get("children", []):
                if child.get("kind") in {
                    CursorKind.INTEGER_LITERAL,
                    CursorKind.FLOATING_LITERAL,
                    CursorKind.CHARACTER_LITERAL,
                    CursorKind.STRING_LITERAL,
                    CursorKind.CXX_BOOL_LITERAL_EXPR,
                    CursorKind.UNEXPOSED_EXPR,
                    CursorKind.DECL_REF_EXPR,
                }:
                    case_expr = child
                    break

            case_text = describe_expr(case_expr) if case_expr is not None else None

            if not case_text or case_text == "an expression":
                cursor = node.get("cursor")
                if cursor is not None:
                    tokens = [t.spelling for t in cursor.get_tokens()]
                    if tokens:
                        joined = " ".join(tokens)
                        if "case" in joined and ":" in joined:
                            start = joined.find("case") + len("case")
                            end = joined.rfind(":")
                            label = joined[start:end].strip()
                            if label:
                                case_text = label

            if case_text:
                return f"This is a case label on line {line} for {case_text}."

            return f"This is a case label on line {line}."

        if kind == CursorKind.DEFAULT_STMT:
            if line is None:
                return "This is a default label."
            return f"This is a default label on line {line}."

        return None
