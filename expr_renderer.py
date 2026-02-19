from clang.cindex import CursorKind


_WRAPPER_KINDS = {CursorKind.UNEXPOSED_EXPR, CursorKind.PAREN_EXPR}
_NULLPTR_KIND = getattr(CursorKind, "CXX_NULL_PTR_LITERAL_EXPR", None)

_BINARY_OP_WORDS = {
    "==": "is equal to",
    "!=": "is not equal to",
    ">": "is greater than",
    ">=": "is at least",
    "<": "is less than",
    "<=": "is at most",
    "&&": "and",
    "||": "or",
    "+": "plus",
    "-": "minus",
    "*": "multiplied by",
    "/": "divided by",
    "%": "modulo",
    "<<": "shifted left by",
    ">>": "shifted right by",
    "&": "bitwise and",
    "|": "bitwise or",
    "^": "bitwise xor",
    "=": "is assigned",
    "+=": "is increased by",
    "-=": "is decreased by",
}


def _tokens(node):
    cursor = node.get("cursor")
    if cursor is None:
        return []
    return [t.spelling for t in cursor.get_tokens()]


def _token_spelling(node):
    toks = _tokens(node)
    if not toks:
        return None
    return " ".join(toks)


def _unwrap(node):
    cur = node
    while cur is not None and cur.get("kind") in _WRAPPER_KINDS:
        children = cur.get("children", [])
        if len(children) != 1:
            break
        cur = children[0]
    return cur


def _extract_operator(node, operators):
    for tok in _tokens(node):
        if tok in operators:
            return tok
    return None


def _extract_binary_operator(node, operators):
    children = node.get("children", [])
    tokens = _tokens(node)
    if not tokens:
        return None

    if len(children) >= 2:
        left_tokens = _tokens(children[0])
        right_tokens = _tokens(children[1])

        middle = list(tokens)
        if left_tokens and middle[: len(left_tokens)] == left_tokens:
            middle = middle[len(left_tokens) :]
        if right_tokens and len(middle) >= len(right_tokens) and middle[-len(right_tokens) :] == right_tokens:
            middle = middle[: -len(right_tokens)]

        for tok in middle:
            if tok in operators:
                return tok

    return _extract_operator(node, operators)


def _describe_binary(op, left_text, right_text):
    phrase = _BINARY_OP_WORDS.get(op, "compared to")
    return f"{left_text} {phrase} {right_text}"


def _describe_call(node):
    name = node.get("name")
    children = [_unwrap(c) for c in node.get("children", [])]
    children = [c for c in children if c is not None]

    if not name:
        return _token_spelling(node) or "a function call"

    if not children:
        return f"{name}()"

    arg_texts = []
    for child in children:
        text = describe_expr(child)
        if text and text != "an expression":
            arg_texts.append(text)
        if len(arg_texts) >= 2:
            break

    if not arg_texts:
        return f"{name}()"
    return f"{name} called with {', '.join(arg_texts)}"


def _cxx_operator_operands(node):
    children = [_unwrap(c) for c in node.get("children", [])]
    children = [c for c in children if c is not None]

    filtered = []
    for child in children:
        kind = child.get("kind")
        name = child.get("name") or ""
        if kind == CursorKind.OVERLOADED_DECL_REF:
            continue
        if kind == CursorKind.DECL_REF_EXPR and name.startswith("operator"):
            continue
        filtered.append(child)

    if len(filtered) >= 2:
        return filtered[-2], filtered[-1]
    if len(children) >= 2:
        return children[-2], children[-1]
    return None, None


def describe_expr(node):
    if node is None:
        return "a condition"

    node = _unwrap(node)
    if node is None:
        return "an expression"

    kind = node.get("kind")
    children = node.get("children", [])

    if kind == CursorKind.BINARY_OPERATOR:
        operators = {
            "==",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
            "&&",
            "||",
            "+",
            "-",
            "*",
            "/",
            "%",
            "&",
            "|",
            "^",
            "<<",
            ">>",
            "=",
            "+=",
            "-=",
        }
        op = _extract_binary_operator(
            node,
            operators,
        )
        left = describe_expr(children[0]) if len(children) > 0 else "the left side"
        right = describe_expr(children[1]) if len(children) > 1 else "the right side"
        if op is None:
            return _token_spelling(node) or "an expression"
        return _describe_binary(op, left, right)

    cxx_operator_call = getattr(CursorKind, "CXX_OPERATOR_CALL_EXPR", None)
    if cxx_operator_call is not None and kind == cxx_operator_call:
        operators = {
            "==",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
            "&&",
            "||",
            "+",
            "-",
            "*",
            "/",
            "%",
            "&",
            "|",
            "^",
            "<<",
            ">>",
            "=",
            "+=",
            "-=",
        }
        op = _extract_binary_operator(
            node,
            operators,
        )
        left_node, right_node = _cxx_operator_operands(node)
        if op and left_node is not None and right_node is not None:
            left = describe_expr(left_node)
            right = describe_expr(right_node)
            return _describe_binary(op, left, right)
        return _token_spelling(node) or "an expression"

    if kind == CursorKind.UNARY_OPERATOR:
        op = _extract_operator(node, {"!", "-", "+", "++", "--"})
        operand = describe_expr(children[0]) if children else "a value"
        if op == "!":
            return f"not {operand}"
        if op == "-":
            return f"negative {operand}"
        if op == "++":
            return f"incremented {operand}"
        if op == "--":
            return f"decremented {operand}"
        return operand

    if kind == CursorKind.DECL_REF_EXPR:
        return node.get("name") or "a variable"

    literal_kinds = {
        CursorKind.INTEGER_LITERAL,
        CursorKind.FLOATING_LITERAL,
        CursorKind.STRING_LITERAL,
        CursorKind.CHARACTER_LITERAL,
        CursorKind.CXX_BOOL_LITERAL_EXPR,
    }
    if _NULLPTR_KIND is not None:
        literal_kinds.add(_NULLPTR_KIND)

    if kind in literal_kinds:
        return _token_spelling(node) or "a literal"

    if kind == CursorKind.CALL_EXPR:
        return _describe_call(node)

    if kind == CursorKind.CONDITIONAL_OPERATOR and len(children) >= 3:
        cond = describe_expr(children[0])
        when_true = describe_expr(children[1])
        when_false = describe_expr(children[2])
        return f"{cond} ? {when_true} : {when_false}"

    if children:
        # Fallback for wrappers/other expression nodes.
        return describe_expr(children[0])

    return node.get("name") or _token_spelling(node) or "an expression"


def find_condition_node(node):
    children = node.get("children", [])

    expr_kinds = {
        CursorKind.BINARY_OPERATOR,
        CursorKind.UNARY_OPERATOR,
        CursorKind.PAREN_EXPR,
        CursorKind.UNEXPOSED_EXPR,
        CursorKind.DECL_REF_EXPR,
        CursorKind.INTEGER_LITERAL,
        CursorKind.FLOATING_LITERAL,
        CursorKind.STRING_LITERAL,
        CursorKind.CHARACTER_LITERAL,
        CursorKind.CXX_BOOL_LITERAL_EXPR,
        CursorKind.CALL_EXPR,
        CursorKind.CONDITIONAL_OPERATOR,
    }
    if _NULLPTR_KIND is not None:
        expr_kinds.add(_NULLPTR_KIND)

    cxx_operator_call = getattr(CursorKind, "CXX_OPERATOR_CALL_EXPR", None)
    if cxx_operator_call is not None:
        expr_kinds.add(cxx_operator_call)

    for child in children:
        if child.get("kind") in expr_kinds:
            return child

    return children[0] if children else None
