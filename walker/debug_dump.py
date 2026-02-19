import sys

from ast_parser import parse_cpp_file
from ast_walker import walk_ast


def _tokens(node):
    cursor = node.get("cursor")
    if cursor is None:
        return []
    return [t.spelling for t in cursor.get_tokens()]


def _parent_chain(node, limit=3):
    chain = []
    cur = node.get("parent")
    while cur is not None and len(chain) < limit:
        chain.append(str(cur.get("kind")))
        cur = cur.get("parent")
    return " -> ".join(chain)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 debug_dump.py <file> [line_start] [line_end]")
        sys.exit(1)

    filename = sys.argv[1]
    line_start = int(sys.argv[2]) if len(sys.argv) > 2 else None
    line_end = int(sys.argv[3]) if len(sys.argv) > 3 else None

    tu = parse_cpp_file(filename)
    nodes = []
    walk_ast(tu.cursor, nodes)

    for n in nodes:
        line = n.get("line")
        if line_start is not None and line_end is not None:
            if line is None or line < line_start or line > line_end:
                continue

        toks = _tokens(n)
        name = n.get("name")

        if line_start is None and line_end is None:
            if not (("cout" in toks) or ("cin" in toks) or ("<<" in toks) or (">>" in toks) or name in {"cout", "cin"}):
                continue

        print(
            f"line={line} kind={n.get('kind')} name={name} "
            f"tokens={' '.join(toks)} parents={_parent_chain(n)}"
        )


if __name__ == "__main__":
    main()
