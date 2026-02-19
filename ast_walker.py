import os


def walk_ast(cursor, nodes, *, debug=False, parent=None, target_file=None, _realpath_cache=None):
    """
    Recursively walks a Clang AST cursor and collects all nodes
    into a flat list for the rule engine.

    Each node also keeps its children for rules that need structure.
    """

    if _realpath_cache is None:
        _realpath_cache = {}

    cursor_file = cursor.location.file.name if cursor.location.file else None
    if target_file and cursor_file:
        cached = _realpath_cache.get(cursor_file)
        if cached is None:
            cached = os.path.realpath(cursor_file)
            _realpath_cache[cursor_file] = cached
        if cached != target_file:
            return None

    node = {
        "kind": cursor.kind,
        "name": cursor.spelling,
        "line": cursor.location.line,
        "children": [],
        "cursor": cursor,
        "parent": parent,
        "file": cursor_file,
    }

    nodes.append(node)

    if debug:
        print("VISITING:", cursor.kind)

    for child in cursor.get_children():
        child_node = walk_ast(
            child,
            nodes,
            debug=debug,
            parent=node,
            target_file=target_file,
            _realpath_cache=_realpath_cache,
        )
        if child_node is not None:
            node["children"].append(child_node)

    return node
