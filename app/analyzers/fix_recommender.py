
import ast
from pathlib import Path
from typing import Any


RULE_ALIASES = {
    "RM101": "mutable_default",
    "B006": "mutable_default",
    "RM102": "bare_except",
    "E722": "bare_except",
    "RM103": "unsafe_eval",
    "B307": "unsafe_eval",
    "S602": "shell_execution",
    "B602": "shell_execution",
}


def _rule_ids(finding: dict[str, Any]) -> list[str]:
    values = finding.get("rule_ids") or [
        finding.get("rule_id", "")
    ]

    return [
        part.strip()
        for value in values
        for part in str(value).split(",")
        if part.strip()
    ]


def _result(
    *,
    rule: str,
    title: str,
    explanation: str,
    recommendation: str,
    confidence: str,
    original: str,
    replacement: str | None = None,
    needs_manual_review: bool = True,
) -> dict[str, Any]:
    return {
        "available": True,
        "engine": "local-rule-based",
        "rule": rule,
        "title": title,
        "explanation": explanation,
        "recommendation": recommendation,
        "confidence": confidence,
        "original_code": original,
        "proposed_code": replacement,
        "patch_available": replacement is not None,
        "needs_manual_review": needs_manual_review,
        "read_only": True,
    }


def _recommend(
    rule: str,
    source: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    """Create a deterministic recommendation without running source code."""
    lines = source.splitlines()
    line_number = int(finding.get("line") or 1)
    original = (
        lines[line_number - 1]
        if 1 <= line_number <= len(lines)
        else ""
    )

    if rule == "mutable_default":
        return _result(
            rule=rule,
            title="Replace the mutable default argument",
            explanation=(
                "A list, dictionary, or set used as a default can be "
                "shared across calls to the same function."
            ),
            recommendation=(
                "Use None as the default and create a fresh collection "
                "inside the function. Review the function's full body "
                "and callers before choosing the final patch."
            ),
            confidence="High for diagnosis; patch requires context",
            original=original,
        )

    if rule == "bare_except":
        return _result(
            rule=rule,
            title="Catch specific exceptions",
            explanation=(
                "A bare except handler can catch unexpected exceptions, "
                "including exceptions that should not be silently ignored."
            ),
            recommendation=(
                "Identify the expected failures in the try block, catch "
                "only those exception types, and handle or report them "
                "appropriately. The correct exception type cannot be "
                "determined reliably from this line alone."
            ),
            confidence="High for diagnosis; exception type unknown",
            original=original,
        )

    if rule == "unsafe_eval":
        return _result(
            rule=rule,
            title="Replace unrestricted eval()",
            explanation=(
                "eval() interprets a string as Python code. If that string "
                "contains untrusted input, it can execute unintended code."
            ),
            recommendation=(
                "Choose a parser that matches the expected input. "
                "ast.literal_eval() is appropriate only for Python literals; "
                "it does not evaluate arithmetic expressions such as "
                "'2 + 2'. If arithmetic is required, use a restricted "
                "expression evaluator with an explicit allowlist."
            ),
            confidence="High for diagnosis; replacement depends on input",
            original=original,
        )

    if rule == "shell_execution":
        return _result(
            rule=rule,
            title="Review shell command execution",
            explanation=(
                "Executing commands through a shell can introduce command "
                "injection risk when command strings contain untrusted data."
            ),
            recommendation=(
                "Prefer subprocess.run() with an argument list and "
                "shell=False. Validate arguments and avoid constructing "
                "commands by concatenating untrusted strings. Review the "
                "intended shell features before changing this call."
            ),
            confidence="High for diagnosis; patch requires context",
            original=original,
        )

    return _result(
        rule=rule,
        title="Manual review recommended",
        explanation=(
            finding.get("message")
            or "The analyzer reported a potential code issue."
        ),
        recommendation=(
            finding.get("suggestion")
            or "Inspect the finding and surrounding code before editing."
        ),
        confidence="Limited: no specialized rule template",
        original=original,
    )


def recommend_fix(
    project_root: Path,
    finding: dict[str, Any],
    context_lines: int = 5,
) -> dict[str, Any]:
    """Generate a local recommendation for a finding in a Python file."""
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

    try:
        line_number = int(finding.get("line") or 1)
    except (TypeError, ValueError):
        return {
            "available": False,
            "error": "The finding has an invalid source line number.",
        }

    lines = source.splitlines()

    if line_number < 1 or line_number > len(lines):
        return {
            "available": False,
            "error": "The finding line is outside the source file.",
        }

    try:
        ast.parse(source, filename=relative_file)
    except SyntaxError as exc:
        return {
            "available": False,
            "error": (
                "The file has a syntax error, so a reliable "
                f"recommendation cannot be generated: {exc.msg}"
            ),
        }

    rule_ids = _rule_ids(finding)
    rule = next(
        (RULE_ALIASES[item] for item in rule_ids if item in RULE_ALIASES),
        "general",
    )

    result = _recommend(rule, source, finding)

    context_lines = max(0, min(context_lines, 20))
    first = max(1, line_number - context_lines)
    last = min(len(lines), line_number + context_lines)

    result["file"] = relative_file
    result["line"] = line_number
    result["context"] = [
        {
            "line": number,
            "code": lines[number - 1],
            "is_target": number == line_number,
        }
        for number in range(first, last + 1)
    ]

    return result
