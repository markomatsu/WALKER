import json
import os
import re
import sys
import time

from clang.cindex import Diagnostic

from ast_parser import parse_cpp_file
from ast_walker import walk_ast
from engine_factory import ALL_RULE_GROUPS, build_engine


LINE_RE = re.compile(r"\bline (\d+)\b")
PASTED_FILE_NAMES = {"pasted.cpp", "pasted_input.cpp", "pasted_code.cpp"}


def _round_ms(value):
    return round(max(0.0, float(value)), 3)


def _line_from_message(message):
    m = LINE_RE.search(message or "")
    if not m:
        return None
    return int(m.group(1))


def _display_name(filename):
    name = os.path.basename(filename)
    if name in PASTED_FILE_NAMES:
        return "pasted code:"
    return name


def _clang_hint_for_message(text):
    if "expected ';'" in text:
        return None, "Add a semicolon to end the previous statement.", 0.96
    if "expected expression" in text:
        return None, "Complete the expression (for example: value, function call, or operation).", 0.94
    if "expected ')'" in text:
        return None, "Add the missing ')' to close the expression or condition.", 0.95
    if "expected '}'" in text:
        return None, "Add the missing '}' to close the block.", 0.95
    if "use of undeclared identifier" in text:
        return None, "Declare this identifier first, or fix a misspelled variable/function name.", 0.92
    if "unknown type name" in text or "no type named" in text:
        return "classes", "Include the correct header and verify the type name and namespace.", 0.9
    if "file not found" in text:
        return None, "Check include/file paths and ensure the referenced header/file exists.", 0.9
    if "no matching function for call" in text:
        return "functions", "Match the function arguments with an existing overload.", 0.88
    if "invalid operands to binary expression" in text:
        return None, "Use compatible operand types for this operator.", 0.88
    if "cannot initialize" in text and "with an rvalue of type" in text:
        return None, "Fix the type mismatch in this initialization or add a conversion.", 0.87
    if "redefinition of" in text:
        return "functions", "Keep only one definition, or rename one declaration/definition.", 0.9
    if "unterminated" in text:
        return None, "Close the unterminated string/comment/token.", 0.94
    if "unsupported" in text or "not supported" in text:
        return None, "Use a simpler/standard C++ construct that this analyzer currently supports.", 0.8
    return None


def _metadata_for_message(message, severity, source):
    text = (message or "").lower()

    if severity == "info":
        if "for-loop" in text or "while-loop" in text or "do-while loop" in text or "range-based for-loop" in text:
            return "loops", None, None
        if "if-statement" in text or "switch statement" in text or "case label" in text or "default label" in text:
            return "conditionals", None, None
        if "function" in text:
            return "functions", None, None
        if "class" in text or "field" in text:
            return "classes", None, None
        return None, None, None

    # Loops
    if "empty while-loop body" in text or "empty for-loop body" in text or "empty do-while loop body" in text:
        return (
            "loops",
            "Add statements inside the loop body, or remove the loop if it is unnecessary.",
            0.92,
        )
    if "may not update condition variable" in text:
        return (
            "loops",
            "Update the loop variable each iteration (e.g., i++, --i, or assignment in the loop body).",
            0.76,
        )
    if "condition in for-loop" in text or "condition in while-loop" in text or "condition in do-while loop" in text:
        return (
            "loops",
            "Replace constant loop conditions with runtime checks tied to real program state.",
            0.88,
        )

    # Conditionals
    if "condition in if-statement" in text:
        return (
            "conditionals",
            "Use a runtime condition or remove the dead branch if the condition is intentionally constant.",
            0.9,
        )
    if "contradictory condition" in text:
        return (
            "conditionals",
            "Fix conflicting comparisons so the condition can become true for at least one input.",
            0.95,
        )
    if "duplicates an earlier condition" in text:
        return (
            "conditionals",
            "Change duplicated else-if checks into distinct conditions or merge equivalent branches.",
            0.92,
        )
    if "possible assignment used as condition" in text or "using the result of an assignment as a condition" in text:
        return (
            "conditionals",
            "Use '==' for comparison if assignment was accidental, or wrap assignment in parentheses if intentional.",
            0.91,
        )
    if "self-comparison" in text:
        return (
            "conditionals",
            "Compare against a different variable/value; comparing a value to itself is constant.",
            0.94,
        )
    if "switch statement" in text and "no default case" in text:
        return (
            "conditionals",
            "Add a default case to handle unexpected values.",
            0.82,
        )
    if "switch case" in text and "fall through" in text:
        return (
            "conditionals",
            "Add 'break;' or an explicit [[fallthrough]] annotation when fallthrough is intentional.",
            0.86,
        )
    if "else-if branch" in text and "is unreachable" in text:
        return (
            "conditionals",
            "Remove or rewrite unreachable else-if conditions after always-true branches.",
            0.88,
        )

    # Functions
    if "may exit without returning a value" in text or "non-void function does not return a value" in text:
        return (
            "functions",
            "Ensure every execution path in non-void functions returns a value.",
            0.9,
        )
    if "is unreachable" in text:
        return (
            "functions",
            "Move or remove code after control-flow terminators like return/break/continue.",
            0.87,
        )
    if "parameter '" in text and "is never used" in text:
        return (
            "functions",
            "Remove unused parameters or use them in function logic.",
            0.86,
        )
    if "function '" in text and "is never called" in text:
        return (
            "functions",
            "Call the function from program flow, or remove it if unnecessary.",
            0.85,
        )
    if "is not defined in this file" in text and "function '" in text:
        return (
            "functions",
            "Add a matching function definition in this file, or remove the unused declaration.",
            0.83,
        )
    if "used on line" in text and "before it is initialized" in text:
        return (
            "functions",
            "Initialize the variable before first use, for example at declaration.",
            0.8,
        )
    if "variable '" in text and "is never used" in text:
        return (
            "functions",
            "Remove unused variables or use them in meaningful logic.",
            0.82,
        )

    # Classes
    if "field '" in text and "is never used" in text:
        return (
            "classes",
            "Use this field in class behavior or remove it.",
            0.84,
        )
    if "field '" in text and "may be uninitialized" in text:
        return (
            "classes",
            "Initialize the field in every constructor or with an inline initializer.",
            0.78,
        )
    if "no member named" in text:
        return (
            "classes",
            "Check the class definition and member spelling; verify the object type is correct.",
            0.9,
        )
    if "incomplete type" in text:
        return (
            "classes",
            "Include the full class definition before use (a forward declaration alone is not enough).",
            0.86,
        )
    if "private" in text and "member" in text:
        return (
            "classes",
            "Access the member through public APIs or adjust access modifiers if appropriate.",
            0.82,
        )
    if "unknown type name" in text or "no type named" in text:
        return (
            "classes",
            "Include the correct header and namespace for this type.",
            0.88,
        )

    # Expressions / runtime
    if "possible division by zero" in text:
        return (
            "functions",
            "Validate the divisor before division (e.g., if (d != 0) ...).",
            0.98,
        )

    if source == "clang":
        hinted = _clang_hint_for_message(text)
        if hinted is not None:
            return hinted

    # Generic fallback.
    fallback_confidence = {
        "error": 0.9 if source == "rule" else 0.88,
        "warning": 0.75 if source == "rule" else 0.72,
    }.get(severity)
    fallback_suggestion = "Review this diagnostic and adjust the code logic or structure to handle it safely."
    return None, fallback_suggestion, fallback_confidence


def _classify_rule_message(message):
    if message.startswith("[ERROR]") or message.startswith("❌"):
        severity = "error"
    elif message.startswith("[WARN]") or message.startswith("⚠"):
        severity = "warning"
    else:
        severity = "info"

    cleaned = message
    for prefix in ("[ERROR] ", "[WARN] ", "❌ ", "⚠️ ", "⚠ "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break

    topic, suggestion, confidence = _metadata_for_message(cleaned, severity, source="rule")
    return {
        "severity": severity,
        "source": "rule",
        "line": _line_from_message(cleaned),
        "message": cleaned,
        "topic": topic,
        "suggestion": suggestion,
        "confidence": confidence,
    }


def _clang_items(translation_unit, target_file):
    severity_map = {
        Diagnostic.Ignored: "info",
        Diagnostic.Note: "info",
        Diagnostic.Warning: "warning",
        Diagnostic.Error: "error",
        Diagnostic.Fatal: "error",
    }
    items = []

    for diag in translation_unit.diagnostics:
        loc = diag.location
        loc_file = loc.file.name if loc and loc.file else None
        if loc_file and os.path.realpath(loc_file) != target_file:
            continue

        severity = severity_map.get(diag.severity, "info")
        topic, suggestion, confidence = _metadata_for_message(diag.spelling, severity, source="clang")
        items.append(
            {
                "severity": severity,
                "source": "clang",
                "line": loc.line if loc else None,
                "column": loc.column if loc else None,
                "message": diag.spelling,
                "topic": topic,
                "suggestion": suggestion,
                "confidence": confidence,
            }
        )

    return items


def _has_blocking_parse_errors(clang_items):
    return any(item.get("severity") == "error" for item in clang_items)


def _limited_analysis_item(first_error_line=None):
    return {
        "severity": "warning",
        "source": "runtime",
        "line": first_error_line if isinstance(first_error_line, int) else None,
        "column": None,
        "message": (
            "Rule-based checks were limited because parser errors were found. "
            "Fix parser errors first, then run analysis again for deeper warnings."
        ),
        "topic": None,
        "suggestion": "Resolve syntax/parse errors first; secondary warnings become more reliable afterward.",
        "confidence": 0.97,
    }


def _summary(items):
    out = {"error": 0, "warning": 0, "info": 0}
    by_topic = {}
    for item in items:
        sev = item.get("severity", "info")
        if sev not in out:
            sev = "info"
        out[sev] += 1

        topic = item.get("topic")
        if topic:
            by_topic[topic] = by_topic.get(topic, 0) + 1

    out["total"] = out["error"] + out["warning"] + out["info"]
    out["by_topic"] = by_topic
    return out


def _sort_items(items):
    severity_rank = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        items,
        key=lambda i: (
            i.get("line") if isinstance(i.get("line"), int) else 10**9,
            severity_rank.get(i.get("severity", "info"), 3),
            i.get("source", ""),
        ),
    )


def _timing_ms(parse_ms, traversal_ms, interpretation_ms):
    total = parse_ms + traversal_ms + interpretation_ms
    return {
        "parse": _round_ms(parse_ms),
        "traversal": _round_ms(traversal_ms),
        "interpretation": _round_ms(interpretation_ms),
        "total": _round_ms(total),
    }


def main():
    args = sys.argv[1:]
    json_mode = True
    if "--text" in args:
        json_mode = False
        args = [a for a in args if a != "--text"]

    enabled_groups = None
    if "--groups" in args:
        idx = args.index("--groups")
        if idx + 1 >= len(args):
            error = "Missing value after --groups (expected comma-separated group names)."
            if json_mode:
                print(json.dumps({"ok": False, "error": error}))
            else:
                print(error)
            return

        raw_groups = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]
        enabled_groups = [g.strip().lower() for g in raw_groups.split(",") if g.strip()]
        unknown = sorted({g for g in enabled_groups if g not in ALL_RULE_GROUPS})
        if unknown:
            error = (
                "Unknown rule group(s): "
                + ", ".join(unknown)
                + ". Valid groups: "
                + ", ".join(sorted(ALL_RULE_GROUPS))
                + "."
            )
            if json_mode:
                print(json.dumps({"ok": False, "error": error}))
            else:
                print(error)
            return

    selected_groups = sorted(set(enabled_groups) if enabled_groups is not None else ALL_RULE_GROUPS)

    files = args
    if not files:
        if json_mode:
            print(json.dumps({"ok": False, "error": "No files provided."}))
            return
        entry = input("Enter one or more .cpp files (space-separated): ").strip()
        if not entry:
            print("No files provided.")
            return
        files = entry.split()

    overall_start = time.perf_counter()
    if json_mode:
        results = []

    for idx, filename in enumerate(files):
        display_name = _display_name(filename)
        target_file = os.path.realpath(filename)
        is_pasted = display_name == "pasted code:"

        parse_start = time.perf_counter()
        translation_unit = None
        try:
            translation_unit = parse_cpp_file(filename)
        except Exception as exc:
            parse_ms = (time.perf_counter() - parse_start) * 1000.0
            timing = _timing_ms(parse_ms, 0.0, 0.0)

            if len(files) > 1:
                print(f"=== {display_name} ===")
            print(f"Failed to parse {display_name}: {exc}")
            if not json_mode:
                print(
                    f"[timing] parse: {timing['parse']} ms, traversal: 0.0 ms, "
                    f"interpretation: 0.0 ms, total: {timing['total']} ms."
                )
            if idx < len(files) - 1:
                print()

            if json_mode:
                parse_message = f"Failed to parse {display_name}: {exc}"
                results.append(
                    {
                        "file": display_name,
                        "path": None if is_pasted else target_file,
                        "is_pasted": is_pasted,
                        "ok": False,
                        "error": parse_message,
                        "explanations": [],
                        "items": [
                            {
                                "severity": "error",
                                "source": "runtime",
                                "line": None,
                                "message": parse_message,
                                "topic": "runtime",
                                "suggestion": (
                                    "Check that the file exists, then run "
                                    "clang++ -std=gnu++17 -fsyntax-only <file> for detailed syntax diagnostics."
                                ),
                                "confidence": 1.0,
                            }
                        ],
                        "summary": {"error": 1, "warning": 0, "info": 0, "total": 1, "by_topic": {"runtime": 1}},
                        "timing_ms": timing,
                    }
                )
            continue

        parse_ms = (time.perf_counter() - parse_start) * 1000.0

        traversal_start = time.perf_counter()
        nodes = []
        walk_ast(translation_unit.cursor, nodes, target_file=target_file)
        traversal_ms = (time.perf_counter() - traversal_start) * 1000.0

        clang_items = _clang_items(translation_unit, target_file)
        blocking_parse_errors = _has_blocking_parse_errors(clang_items)

        interpretation_ms = 0.0
        explanations = []
        rule_items = []
        if not blocking_parse_errors:
            interpretation_start = time.perf_counter()
            engine = build_engine(selected_groups)
            explanations = engine.run(nodes)
            interpretation_ms = (time.perf_counter() - interpretation_start) * 1000.0
            rule_items = [_classify_rule_message(e) for e in explanations]

        combined_items = list(clang_items) + list(rule_items)
        if blocking_parse_errors:
            error_lines = [item.get("line") for item in clang_items if item.get("severity") == "error"]
            first_error_line = min((ln for ln in error_lines if isinstance(ln, int)), default=None)
            combined_items.append(_limited_analysis_item(first_error_line))

        items = _sort_items(combined_items)
        timing = _timing_ms(parse_ms, traversal_ms, interpretation_ms)

        if json_mode:
            results.append(
                {
                    "file": display_name,
                    "path": None if is_pasted else target_file,
                    "is_pasted": is_pasted,
                    "ok": True,
                    "error": None,
                    "explanations": explanations,
                    "items": items,
                    "summary": _summary(items),
                    "timing_ms": timing,
                    "rule_groups": selected_groups,
                }
            )
            continue

        if len(files) > 1:
            print(f"=== {display_name} ===")

        if explanations:
            for explanation in explanations:
                print(explanation)
        elif blocking_parse_errors:
            for item in items:
                severity = item.get("severity")
                if severity not in {"error", "warning"}:
                    continue
                if item.get("source") not in {"clang", "runtime"}:
                    continue
                prefix = "[ERROR]" if severity == "error" else "[WARN]"
                line = item.get("line")
                column = item.get("column")
                location_parts = []
                if isinstance(line, int):
                    location_parts.append(f"line {line}")
                if isinstance(column, int):
                    location_parts.append(f"column {column}")
                location = f" ({', '.join(location_parts)})" if location_parts else ""
                print(f"{prefix} {item.get('message', '').strip()}{location}")

        print(
            f"[timing] parse: {timing['parse']} ms, traversal: {timing['traversal']} ms, "
            f"interpretation: {timing['interpretation']} ms, total: {timing['total']} ms."
        )

        if idx < len(files) - 1:
            print()

    if json_mode:
        total_ms = _round_ms((time.perf_counter() - overall_start) * 1000.0)
        print(
            json.dumps(
                {
                    "ok": True,
                    "results": results,
                    "timing_ms": {"total": total_ms},
                    "rule_groups": selected_groups,
                }
            )
        )


if __name__ == "__main__":
    main()
