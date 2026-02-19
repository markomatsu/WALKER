import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "test_engine.py"
VENV_PY = ROOT / ".venv" / "bin" / "python"
PYTHON = VENV_PY if VENV_PY.exists() else Path("python3")


def run_engine(code, filename="fixture.cpp", groups=None):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / filename
        src.write_text(textwrap.dedent(code), encoding="utf-8")

        cmd = [str(PYTHON), str(ENGINE)]
        if groups is not None:
            cmd.extend(["--groups", ",".join(groups)])
        cmd.append(str(src))

        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Engine failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

        payload = json.loads(proc.stdout)
        if payload.get("ok") is not True:
            raise RuntimeError(f"Unexpected payload: {payload}")

        results = payload.get("results", [])
        if len(results) != 1:
            raise RuntimeError(f"Expected one result entry, got {len(results)}")

        return payload, results[0]


class RegressionRulesTest(unittest.TestCase):
    def test_void_function_does_not_trigger_missing_return(self):
        _payload, result = run_engine(
            """
            #include <iostream>
            using namespace std;

            void logIfPositive(int x) {
                if (x > 0) {
                    cout << "positive";
                }
            }

            int main() {
                logIfPositive(1);
                return 0;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertFalse(
            any("may exit without returning a value" in msg for msg in messages),
            "void functions should not receive missing-return warnings",
        )

    def test_condition_rendering_is_readable(self):
        _payload, result = run_engine(
            """
            int main() {
                int x = 10;
                if (x > 10 && x < 5) {
                    return 1;
                }
                return 0;
            }
            """
        )

        explanations = result.get("explanations", [])
        self.assertTrue(
            any("x is greater than 10 and x is less than 5" in text for text in explanations),
            "Expected readable nested condition rendering",
        )
        self.assertTrue(
            any("Contradictory condition" in text for text in explanations),
            "Expected contradictory condition warning",
        )

    def test_iostream_is_reported_once(self):
        _payload, result = run_engine(
            """
            #include <iostream>
            using namespace std;

            int main() {
                int x;
                cout << "Grade: ";
                cin >> x;

                if (x >= 75) {
                    cout << "passed.";
                } else {
                    cout << "failed.";
                }
                return 0;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertEqual(sum('outputs "Grade: "' in msg for msg in messages), 1)
        self.assertEqual(sum("reads input into x from standard input" in msg for msg in messages), 1)

    def test_output_metadata_and_stage_timing_exist(self):
        payload, result = run_engine(
            """
            int main() {
                int x = 10 / 0;
                return x;
            }
            """
        )

        warning_or_error = [
            item for item in result.get("items", []) if item.get("severity") in {"warning", "error"}
        ]
        self.assertTrue(warning_or_error, "Expected at least one warning/error item")

        for item in warning_or_error:
            self.assertIn("suggestion", item)
            self.assertIn("confidence", item)
            self.assertIsNotNone(item.get("suggestion"))
            self.assertIsNotNone(item.get("confidence"))

        timing = result.get("timing_ms", {})
        for key in ("parse", "traversal", "interpretation", "total"):
            self.assertIn(key, timing)
            self.assertIsInstance(timing[key], (int, float))
            self.assertGreaterEqual(timing[key], 0)

        top_timing = payload.get("timing_ms", {})
        self.assertIn("total", top_timing)
        self.assertIsInstance(top_timing["total"], (int, float))
        self.assertGreaterEqual(top_timing["total"], 0)

    def test_function_declared_and_called_but_not_defined(self):
        _payload, result = run_engine(
            """
            int helper(int x);

            int main() {
                return helper(42);
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertTrue(
            any("declared on line" in msg and "called but not defined in this file" in msg for msg in messages),
            "Expected declared-but-not-defined warning",
        )

    def test_external_declaration_without_call_does_not_warn(self):
        _payload, result = run_engine(
            """
            extern int helper(int x);

            int main() {
                return 0;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertFalse(
            any("called but not defined in this file" in msg for msg in messages),
            "External declaration without call should not trigger missing-definition warning",
        )

    def test_local_used_before_initialization(self):
        _payload, result = run_engine(
            """
            int main() {
                int value;
                int out = value + 1;
                return out;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertTrue(
            any("used on line" in msg and "before it is initialized" in msg for msg in messages),
            "Expected uninitialized local variable warning",
        )

    def test_unreachable_else_if_after_true_branch(self):
        _payload, result = run_engine(
            """
            int main() {
                if (true) {
                    return 1;
                } else if (1) {
                    return 2;
                }
                return 0;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertTrue(
            any("Else-if branch" in msg and "is unreachable" in msg for msg in messages),
            "Expected unreachable else-if warning",
        )

    def test_duplicate_condition_with_function_calls_is_not_flagged(self):
        _payload, result = run_engine(
            """
            int nextValue() {
                static int x = 0;
                return x++;
            }

            int main() {
                if (nextValue() > 0) {
                    return 1;
                } else if (nextValue() > 0) {
                    return 2;
                }
                return 0;
            }
            """
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertFalse(
            any("duplicates an earlier condition" in msg for msg in messages),
            "Side-effecting conditions should not be flagged as duplicate branches",
        )

    def test_parse_errors_have_actionable_hints_and_limit_rule_checks(self):
        _payload, result = run_engine(
            """
            int main() {
                int x = ;
                if (x > 0) {
                    return 1;
                }
                return 0;
            }
            """
        )

        items = result.get("items", [])
        clang_errors = [i for i in items if i.get("source") == "clang" and i.get("severity") == "error"]
        self.assertTrue(clang_errors, "Expected clang syntax errors")
        self.assertTrue(
            any(isinstance(i.get("column"), int) and i.get("column", 0) > 0 for i in clang_errors),
            "Expected parse diagnostics with column information",
        )
        self.assertTrue(
            any("Complete the expression" in (i.get("suggestion") or "") for i in clang_errors),
            "Expected actionable parse hint for expected-expression diagnostics",
        )

        self.assertTrue(
            any(
                i.get("source") == "runtime"
                and "Rule-based checks were limited because parser errors were found." in (i.get("message") or "")
                for i in items
            ),
            "Expected analysis-limited runtime warning when parse errors are present",
        )
        self.assertFalse(
            any(i.get("source") == "rule" for i in items),
            "Rule diagnostics should be suppressed while parser errors are unresolved",
        )

    def test_rule_groups_filter_output(self):
        _payload, result = run_engine(
            """
            int main() {
                int i = 0;
                while (i < 2) {
                    i++;
                }
                if (i > 0) {
                    return 1;
                }
                return 0;
            }
            """,
            groups=["loops"],
        )

        messages = [item.get("message", "") for item in result.get("items", [])]
        self.assertTrue(any("while-loop" in msg for msg in messages))
        self.assertFalse(any("if-statement" in msg for msg in messages))


if __name__ == "__main__":
    unittest.main()
