import os
import sys
import subprocess
from clang import cindex


def _find_libclang():
    env_path = os.environ.get("LIBCLANG_FILE") or os.environ.get("LIBCLANG_PATH")
    if env_path:
        if os.path.isdir(env_path):
            candidate = os.path.join(env_path, "libclang.dylib")
            if os.path.exists(candidate):
                return candidate
        if os.path.exists(env_path):
            return env_path

    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            for rel in ("libclang.dylib", os.path.join("lib", "libclang.dylib")):
                candidate = os.path.join(base, rel)
                if os.path.exists(candidate):
                    return candidate

    here = os.path.abspath(os.path.dirname(__file__))
    for rel in ("libclang.dylib", os.path.join("lib", "libclang.dylib")):
        candidate = os.path.join(here, rel)
        if os.path.exists(candidate):
            return candidate

    for candidate in (
        "/opt/homebrew/opt/llvm/lib/libclang.dylib",
        "/usr/local/opt/llvm/lib/libclang.dylib",
    ):
        if os.path.exists(candidate):
            return candidate

    return None


libclang_path = _find_libclang()
if libclang_path:
    cindex.Config.set_library_file(libclang_path)


class ParseCppError(RuntimeError):
    pass


def _translation_unit_failure_hint(filename):
    base = os.path.basename(filename)
    return (
        f"Could not parse '{base}'. "
        "This usually means severe syntax errors or missing C++ headers/toolchain paths. "
        "Try: clang++ -std=gnu++17 -fsyntax-only <file> to see compiler diagnostics."
    )


def parse_cpp_file(filename, extra_args=None):
    if not os.path.exists(filename):
        raise ParseCppError(f"Input file does not exist: {filename}")
    if not os.path.isfile(filename):
        raise ParseCppError(f"Input path is not a file: {filename}")

    index = cindex.Index.create()
    sdk_args = []
    try:
        sdk_path = subprocess.check_output(
            ["xcrun", "--show-sdk-path"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if sdk_path:
            sdk_args = [
                "-isysroot",
                sdk_path,
                "-I",
                os.path.join(sdk_path, "usr/include/c++/v1"),
            ]
    except Exception:
        sdk_args = []

    default_args = [
        "-x", "c++",
        "-std=gnu++17",
    ] + sdk_args
    args = default_args + (extra_args or [])
    options = cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD

    try:
        return index.parse(filename, args=args, options=options)
    except cindex.TranslationUnitLoadError as exc:
        raise ParseCppError(_translation_unit_failure_hint(filename)) from exc
