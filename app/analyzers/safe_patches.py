
import ast
import difflib
from pathlib import Path
from typing import Any


SUPPORTED_RULES = {
    "RM101", "B006", "RM102", "E722",
    "RM103", "B307", "RM107", "B602",
}


def _get_rule_ids(finding: dict[str, Any]) -> set[str]:
    values = finding.get("rule_ids") or [finding.get("rule_id", "")]
    result = set()

    for value in values:
        result.update(
            part.strip()
            for part in str(value).split(",")
            if part.strip()
        )

    return result


def _find_function(source: str, line_number: int):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    matches = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        if node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno):
            defaults = node.args.defaults + [
                item for item in node.args.kw_defaults if item is not None
            ]

            if any(isinstance(item, (ast.List, ast.Dict, ast.Set)) for item in defaults):
                matches.append(node)

    if not matches:
        return None

    return min(
        matches,
        key=lambda node: getattr(node, "end_lineno", node.lineno) - node.lineno,
    )


def _replace_empty_list_defaults(
    source: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
):
    lines = source.splitlines(keepends=True)
    args = function.args
    positional_args = args.posonlyargs + args.args
    positional_defaults = args.defaults
    positional_start = len(positional_args) - len(positional_defaults)

    defaults_to_replace = []
    parameter_names = []

    for index, default in enumerate(positional_defaults):
        if not isinstance(default, (ast.List, ast.Dict, ast.Set)):
            continue

        argument = positional_args[positional_start + index]

        if not isinstance(default, ast.List) or default.elts:
            return None, (
                "Only empty list defaults are supported automatically. "
                "Dictionary, set, and non-empty defaults need manual review."
            )

        defaults_to_replace.append((default, "None"))
        parameter_names.append(argument.arg)

    for argument, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None or not isinstance(default, (ast.List, ast.Dict, ast.Set)):
            continue

        if not isinstance(default, ast.List) or default.elts:
            return None, (
                "Only empty list defaults are supported automatically. "
                "Review this keyword-only argument manually."
            )

        defaults_to_replace.append((default, "None"))
        parameter_names.append(argument.arg)

    if not parameter_names:
        return None, "No supported empty list default was found."

    if function.decorator_list:
        return None, "Decorated functions require manual review."

    for node, replacement in sorted(
        defaults_to_replace,
        key=lambda pair: (pair[0].lineno, pair[0].col_offset),
        reverse=True,
    ):
        if node.lineno != node.end_lineno:
            return None, "Multi-line default expressions require manual review."

        line_index = node.lineno - 1
        encoded = lines[line_index].encode("utf-8")
        prefix = encoded[:node.col_offset].decode("utf-8")
        suffix = encoded[node.end_col_offset:].decode("utf-8")
        lines[line_index] = prefix + replacement + suffix

    body = function.body
    insertion_node = body[0]

    if (
        isinstance(insertion_node, ast.Expr)
        and isinstance(insertion_node.value, ast.Constant)
        and isinstance(insertion_node.value.value, str)
    ):
        if len(body) == 1:
            return None, "The function contains only a docstring."

        insertion_node = body[1]

    indentation = " " * insertion_node.col_offset
    insertion_index = insertion_node.lineno - 1

    initialization = "".join(
        f"{indentation}if {name} is None:\n"
        f"{indentation}    {name} = []\n"
        for name in parameter_names
    )

    lines.insert(insertion_index, initialization)
    candidate = "".join(lines)

    try:
        ast.parse(candidate)
    except SyntaxError as exc:
        return None, (
            f"Candidate syntax validation failed: {exc.msg} at line {exc.lineno}."
        )

    return candidate, (
        "Generated a candidate for empty list defaults. Review callers and tests."
    )


def _build_syntax_candidate(source: str, line_number: int, finding: dict[str, Any]):
    """Build narrowly-scoped, read-only candidates for known syntax patterns."""
    lines = source.splitlines(keepends=True)
    index = line_number - 1
    line = lines[index]
    stripped = line.strip()
    message = str(finding.get("message") or "").lower()

    # Python does not allow starred iterable unpacking in a set comprehension.
    # This pattern is only proposed when the source clearly expresses the
    # common Sudoku peers operation; other starred comprehensions stay manual.
    sudoku_pattern = (
        "iterable unpacking cannot be used in comprehension" in message
        and stripped.startswith("peers =")
        and "{*u for u in units[s]} - {s}" in stripped
    )
    if sudoku_pattern:
        indent = line[: len(line) - len(line.lstrip())]
        lines[index] = (
            f"{indent}peers = {{s: {{cell for unit in units[s] "
            f"for cell in unit if cell != s}} for s in squares}}"
            + ("\n" if line.endswith("\n") else "")
        )
        candidate = "".join(lines)
        try:
            ast.parse(candidate)
        except SyntaxError as exc:
            return None, f"Candidate failed syntax validation: {exc.msg} at line {exc.lineno}."
        return candidate, (
            "Proposed a targeted fix for the known nested set-comprehension pattern. "
            "Syntax validation passed; review the behavior and run the project's tests."
        )

    # In this known Huffman implementation, traverse_tree returns Letter
    # objects with .letter and .bitstring attributes. Build the intended
    # character-to-code mapping explicitly instead of unpacking a string.
    huffman_pattern = (
        "dict unpacking cannot be used in dict comprehension" in message
        and stripped.startswith("letters =")
        and "{**letter.bitstring for letter in traverse_tree(root, \"\")}" in stripped
    )
    if huffman_pattern:
        indent = line[: len(line) - len(line.lstrip())]
        lines[index] = (
            f'{indent}letters = {{letter.letter: letter.bitstring '
            f'for letter in traverse_tree(root, "")}}'
            + ("\n" if line.endswith("\n") else "")
        )
        candidate = "".join(lines)
        try:
            ast.parse(candidate)
        except SyntaxError as exc:
            return None, f"Candidate failed syntax validation: {exc.msg} at line {exc.lineno}."
        return candidate, (
            "Generated a targeted Huffman mapping fix using each Letter's character "
            "and bitstring. Syntax validation passed; review behavior and run tests."
        )

    if "dict unpacking cannot be used in dict comprehension" in message:
        return None, (
            "Manual review required: the dictionary key/value expression is ambiguous. "
            "No replacement was generated because the source does not match the known Huffman pattern."
        )

    return None, (
        "No narrowly verified automatic strategy matches this syntax error. "
        "Review the source manually; no replacement was generated."
    )


def _build_candidate(
    source: str,
    line_number: int,
    rule_ids: set[str],
):
    if rule_ids.intersection({"RM101", "B006"}):
        function = _find_function(source, line_number)

        if function is not None:
            return _replace_empty_list_defaults(source, function)

    if rule_ids.intersection({"RM102", "E722"}):
        return None, (
            "Manual review required: inspect the try block and catch only "
            "the specific exception types the code expects."
        )

    if rule_ids.intersection({"RM103", "B307"}):
        return None, (
            "Manual review required: eval() replacement depends on the "
            "expected input format. For a Python literal, ast.literal_eval() "
            "may be suitable; for arithmetic, use a restricted expression "
            "parser. Do not replace eval() blindly."
        )

    if rule_ids.intersection({"RM107", "B602"}):
        return None, (
            "Manual review required: shell=True may allow command injection. "
            "Inspect how the command is constructed. Prefer an argument list "
            "with shell=False when compatible with the intended command. "
            "No automatic replacement was generated."
        )

    return None, (
        "No automatic patch strategy is available for this finding. "
        "Review the surrounding source manually."
    )


def generate_safe_patch(
    project_root: Path,
    finding: dict[str, Any],
) -> dict[str, Any]:
    root = project_root.resolve()
    relative_file = str(
        finding.get("file") or finding.get("path") or ""
    ).replace("\\", "/")

    if not relative_file:
        return {
            "available": False,
            "patch_available": False,
            "error": "The finding does not specify a source file.",
            "read_only": True,
        }

    target = (root / relative_file).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        return {
            "available": False,
            "patch_available": False,
            "error": "The source file is outside the selected project.",
            "read_only": True,
        }

    if not target.is_file() or target.suffix.lower() != ".py":
        return {
            "available": False,
            "patch_available": False,
            "error": "The target must be an existing Python file.",
            "read_only": True,
        }

    try:
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {
            "available": False,
            "patch_available": False,
            "error": "The source file could not be read as UTF-8.",
            "read_only": True,
        }

    try:
        line_number = int(finding.get("line") or 0)
    except (TypeError, ValueError):
        line_number = 0

    if line_number < 1 or line_number > len(source.splitlines()):
        return {
            "available": False,
            "patch_available": False,
            "error": "The finding has an invalid line number.",
            "read_only": True,
        }

    rule_ids = _get_rule_ids(finding)

    if "RM001" in rule_ids:
        candidate, note = _build_syntax_candidate(source, line_number, finding)
        if candidate is None:
            return {
                "available": False,
                "patch_available": False,
                "note": note,
                "file": relative_file,
                "line": line_number,
                "read_only": True,
                "needs_manual_review": True,
            }
        # Syntax candidates are preview-only and always require human review.
        diff = "".join(
            difflib.unified_diff(
                source.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=f"a/{relative_file}",
                tofile=f"b/{relative_file}",
            )
        )
        return {
            "available": True,
            "patch_available": True,
            "file": relative_file,
            "line": line_number,
            "original_code": source,
            "proposed_code": candidate,
            "diff": diff,
            "syntax_valid": True,
            "read_only": True,
            "needs_manual_review": True,
            "note": note,
        }

    if not rule_ids.intersection(SUPPORTED_RULES):
        return {
            "available": False,
            "patch_available": False,
            "error": "No safe patch strategy is available for this rule.",
            "file": relative_file,
            "line": line_number,
            "read_only": True,
            "needs_manual_review": True,
        }

    candidate, note = _build_candidate(source, line_number, rule_ids)

    if candidate is None:
        return {
            "available": False,
            "patch_available": False,
            "note": note,
            "file": relative_file,
            "line": line_number,
            "read_only": True,
            "needs_manual_review": True,
        }

    try:
        ast.parse(candidate, filename=relative_file)
    except SyntaxError as exc:
        return {
            "available": False,
            "patch_available": False,
            "error": (
                f"Proposed code failed syntax validation: {exc.msg} "
                f"at line {exc.lineno}."
            ),
            "read_only": True,
        }

    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            candidate.splitlines(keepends=True),
            fromfile=f"a/{relative_file}",
            tofile=f"b/{relative_file}",
        )
    )

    return {
        "available": True,
        "patch_available": True,
        "file": relative_file,
        "line": line_number,
        "original_code": source,
        "proposed_code": candidate,
        "diff": diff,
        "syntax_valid": True,
        "read_only": True,
        "needs_manual_review": True,
        "note": note,
    }
