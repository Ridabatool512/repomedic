
import ast
from pathlib import Path
from typing import Any


# These rules have specialized preview guidance.
# A supported preview must be a replacement we can justify from the source.
# Preview generation never modifies project files.
SUPPORTED_RULES = {"RM101", "B006", "RM102", "E722", "RM103", "B307"}

RULE_DETAILS = {
    "RM101": {
        "risk": "Medium",
        "why": "A mutable default object can be shared between function calls.",
        "review": (
            "Check whether each call should receive a fresh collection. "
            "Changing the signature and function body may both be necessary."
        ),
    },
    "B006": {
        "risk": "Medium",
        "why": "A mutable default object can retain state across function calls.",
        "review": (
            "Check whether each call should receive a fresh collection. "
            "Changing the signature and function body may both be necessary."
        ),
    },
    "RM102": {
        "risk": "Medium",
        "why": "A bare except handler catches exceptions the code may not be able to handle.",
        "review": (
            "Inspect the protected operation and catch only the exceptions "
            "the code can handle appropriately."
        ),
    },
    "E722": {
        "risk": "Medium",
        "why": "A bare except handler catches exceptions the code may not be able to handle.",
        "review": (
            "Inspect the protected operation and catch only the exceptions "
            "the code can handle appropriately."
        ),
    },
    "RM103": {
        "risk": "High",
        "why": "eval() executes Python expressions and can be dangerous with untrusted input.",
        "review": (
            "Avoid evaluating untrusted input as Python code. Choose a safer "
            "parser or a restricted expression language that matches the "
            "application's actual requirements."
        ),
    },
    "B307": {
        "risk": "High",
        "why": "eval() can execute expressions supplied at runtime.",
        "review": (
            "Avoid evaluating untrusted input as Python code. Choose a safer "
            "parser or a restricted expression language that matches the "
            "application's actual requirements."
        ),
    },
}


def _rule_ids(finding: dict[str, Any]) -> list[str]:
    values = finding.get("rule_ids") or [finding.get("rule_id", "")]
    result = []

    for value in values:
        # Merged rule_id strings can contain comma-separated IDs.
        result.extend(
            part.strip()
            for part in str(value).split(",")
            if part.strip()
        )

    return result


def _find_node(
    tree: ast.AST,
    rule_ids: list[str],
    target_line: int,
) -> ast.AST | None:
    candidates = []

    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != target_line:
            continue

        if "RM101" in rule_ids or "B006" in rule_ids:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = node.args.defaults + [
                    value
                    for value in node.args.kw_defaults
                    if value is not None
                ]
                if any(
                    isinstance(value, (ast.List, ast.Dict, ast.Set))
                    for value in defaults
                ):
                    candidates.append(node)

        elif "RM102" in rule_ids or "E722" in rule_ids:
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                candidates.append(node)

        elif "RM103" in rule_ids or "B307" in rule_ids:
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "eval"
                ):
                    candidates.append(node)

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda node: (
            getattr(node, "end_lineno", target_line)
            - getattr(node, "lineno", target_line),
            getattr(node, "col_offset", 0),
        ),
    )


def _guidance(note: str) -> dict[str, Any]:
    """Return a guidance-only result instead of implying a fix is safe."""
    return {
        "supported": False,
        "replacement": None,
        "note": note,
    }


def _preview_for_node(
    node: ast.AST,
    lines: list[str],
    rule_ids: list[str],
) -> dict[str, Any] | None:
    if "RM101" in rule_ids or "B006" in rule_ids:
        return _guidance(
            "A safe fix must replace the mutable default and initialize "
            "a fresh collection inside the function. The correct change "
            "depends on how the function is called, so review the function "
            "signature and body together."
        )

    if "RM102" in rule_ids or "E722" in rule_ids:
        return _guidance(
            "No exception type can be selected reliably from the bare "
            "except line alone. Inspect the try block, identify expected "
            "failure cases, and catch only the appropriate exception types."
        )

    if "RM103" in rule_ids or "B307" in rule_ids:
        if not isinstance(node, ast.Call):
            return _guidance(
                "The detected eval() call could not be analyzed safely. "
                "Review its source manually."
            )

        if len(node.args) != 1 or node.keywords:
            return _guidance(
                "This eval() call uses an argument pattern that this preview "
                "does not support. Review its arguments and replace dynamic "
                "evaluation with a safer, requirement-specific approach."
            )

        argument = node.args[0]

        # Even a simple argument does not prove that literal_eval is correct:
        # the value could be the string '2 + 2', which literal_eval rejects.
        # Therefore do not generate ast.literal_eval as an automatic fix.
        try:
            argument_text = ast.get_source_segment(
                "\n".join(lines),
                argument,
            )
        except (IndexError, TypeError, ValueError):
            argument_text = None

        if not argument_text:
            return _guidance(
                "The eval() argument could not be extracted reliably. "
                "Review the call manually and avoid evaluating untrusted input."
            )

        return _guidance(
            "No automatic replacement was generated because the expected "
            "input format is unknown. ast.literal_eval() accepts Python "
            "literals, but it does not evaluate expressions such as '2 + 2'. "
            "Use a purpose-built parser or a restricted expression evaluator "
            "if arithmetic expressions are required. Never evaluate untrusted "
            "input as unrestricted Python code."
        )

    return None


def build_fix_preview(
    project_root: Path,
    finding: dict[str, Any],
    context_lines: int = 3,
) -> dict[str, Any]:
    """Build a read-only code context and optional replacement preview."""
    root = project_root.resolve()
    relative_file = str(finding.get("file", "")).replace("\\", "/")

    if not relative_file:
        return {
            "available": False,
            "error": "The finding does not specify a source file.",
        }

    target = (root / relative_file).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        return {
            "available": False,
            "error": "The finding points outside the selected project.",
        }

    if not target.is_file() or target.suffix.lower() != ".py":
        return {
            "available": False,
            "error": "The source file is not an available Python file.",
        }

    try:
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {
            "available": False,
            "error": "The source file could not be read as UTF-8 text.",
        }

    lines = source.splitlines()

    try:
        line_number = int(finding.get("line") or 1)
    except (TypeError, ValueError):
        return {
            "available": False,
            "error": "The finding has an invalid source line number.",
        }

    if line_number < 1 or line_number > len(lines):
        return {
            "available": False,
            "error": "The finding line is outside the source file.",
        }

    context_lines = max(0, context_lines)
    first = max(1, line_number - context_lines)
    last = min(len(lines), line_number + context_lines)

    context = [
        {
            "line": number,
            "code": lines[number - 1],
            "is_target": number == line_number,
        }
        for number in range(first, last + 1)
    ]

    rule_ids = _rule_ids(finding)
    details = next(
        (RULE_DETAILS[rule] for rule in rule_ids if rule in RULE_DETAILS),
        None,
    )

    preview = None

    try:
        tree = ast.parse(source, filename=relative_file)
        node = _find_node(tree, rule_ids, line_number)

        if node is not None:
            preview = _preview_for_node(node, lines, rule_ids)
    except SyntaxError:
        # Preserve the source context even when the source cannot be parsed.
        preview = None

    if preview is None:
        preview = _guidance(
            "No specialized replacement is available for this finding. "
            "Review the recommendation and surrounding source code manually."
        )

    return {
        "available": True,
        "file": relative_file,
        "line": line_number,
        "context": context,
        "original_line": lines[line_number - 1],
        "preview": preview,
        "risk": details["risk"] if details else finding.get("severity", "Unknown"),
        "why": details["why"] if details else finding.get("message", ""),
        "review_note": details["review"] if details else finding.get("suggestion", ""),
        "read_only": True,
    }
