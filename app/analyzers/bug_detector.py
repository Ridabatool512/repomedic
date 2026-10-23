
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", ".mypy_cache", ".pytest_cache",
}

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def make_finding(
    rule_id: str,
    title: str,
    severity: str,
    file_path: str,
    line: int,
    message: str,
    suggestion: str,
    source: str = "RepoMedic",
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_ids": [rule_id],
        "title": title,
        "severity": severity,
        "file": file_path,
        "line": line,
        "message": message,
        "suggestion": suggestion,
        "source": source,
        "sources": [source],
        "occurrences": 1,
    }


class BugRuleVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.findings: list[dict[str, Any]] = []

    def add(
        self,
        rule_id: str,
        title: str,
        severity: str,
        node: ast.AST,
        message: str,
        suggestion: str,
    ) -> None:
        self.findings.append(
            make_finding(
                rule_id,
                title,
                severity,
                self.file_path,
                getattr(node, "lineno", 1),
                message,
                suggestion,
            )
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def _check_mutable_defaults(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        defaults = node.args.defaults + [
            default for default in node.args.kw_defaults
            if default is not None
        ]

        for default in defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.add(
                    "RM101",
                    "Mutable default argument",
                    "medium",
                    default,
                    f"Function '{node.name}' uses a mutable default argument.",
                    "Use None as the default and create a new collection inside the function.",
                )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(
                "RM102",
                "Bare exception handler",
                "medium",
                node,
                "This handler catches every exception, including exceptions that should propagate.",
                "Catch the specific exception types your code can handle.",
            )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec"}:
                self.add(
                    "RM103",
                    f"Use of {node.func.id}()",
                    "high",
                    node,
                    f"{node.func.id}() executes dynamically supplied code and may enable code injection.",
                    "Avoid dynamic execution; use explicit operations or a safe parser.",
                )

            elif node.func.id == "compile":
                self.add(
                    "RM104",
                    "Dynamic code compilation",
                    "medium",
                    node,
                    "compile() creates executable code from a string or AST.",
                    "Avoid compiling untrusted input and validate source carefully.",
                )

        if isinstance(node.func, ast.Attribute):
            owner = node.func.value

            if (
                isinstance(owner, ast.Name)
                and owner.id == "os"
                and node.func.attr in {"system", "popen"}
            ):
                self.add(
                    "RM105",
                    "OS command execution",
                    "medium",
                    node,
                    "An operating-system command is being executed from Python.",
                    "Avoid shell commands with untrusted input; prefer argument lists.",
                )

            if (
                isinstance(owner, ast.Name)
                and owner.id == "pickle"
                and node.func.attr in {"load", "loads"}
            ):
                self.add(
                    "RM106",
                    "Unsafe pickle deserialization",
                    "high",
                    node,
                    "Untrusted pickle data can execute arbitrary code during deserialization.",
                    "Never load pickle data from untrusted sources; consider JSON.",
                )

            if (
                isinstance(owner, ast.Name)
                and owner.id == "subprocess"
                and node.func.attr in {
                    "run", "call", "Popen", "check_call", "check_output"
                }
                and any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                )
            ):
                self.add(
                    "RM107",
                    "Shell command execution",
                    "high",
                    node,
                    "shell=True can create command-injection risks with untrusted input.",
                    "Use shell=False and pass the command and its arguments as a list.",
                )

        self.generic_visit(node)


def collect_python_files(project_path: Path) -> list[Path]:
    return sorted(
        path for path in project_path.rglob("*.py")
        if not any(part in IGNORED_DIRS for part in path.parts)
    )


def relative_name(file_path: Path, project_path: Path) -> str:
    return file_path.relative_to(project_path).as_posix()


def run_tool(
    arguments: list[str], project_path: Path
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = subprocess.run(
            arguments,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        name = arguments[1] if len(arguments) > 1 else arguments[0]
        return [], f"Tool unavailable: {name}"
    except subprocess.TimeoutExpired:
        name = arguments[1] if len(arguments) > 1 else arguments[0]
        return [], f"Tool timed out: {name}"

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        detail = (result.stderr or result.stdout or "").strip()
        return [], f"Could not parse analyzer output: {detail[:300]}"

    if isinstance(data, list):
        return data, None

    if isinstance(data, dict):
        return data.get("results", []), None

    return [], "Unexpected analyzer output format."


def normalize_path(filename: str, root: Path) -> str:
    if not filename:
        return "unknown"

    try:
        return Path(filename).resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return Path(filename).as_posix()


def issue_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    """Group overlapping analyzer reports by location and issue family."""
    rule = finding["rule_id"].upper()
    title = finding["title"].lower()
    message = finding["message"].lower()

    if rule in {"RM107", "B602"} or "shell command" in title:
        family = "shell-command-execution"
    elif rule in {"RM103", "B307"} or "eval()" in title:
        family = "dynamic-evaluation"
    elif rule in {"RM101", "B006"} or "mutable default" in title:
        family = "mutable-default-argument"
    elif rule in {"RM102", "E722"} or "bare exception" in title:
        family = "bare-exception"
    elif rule in {"B110", "S110"} or "try-except-pass" in title:
        family = "swallowed-exception"
    elif rule == "B404" or (
        "subprocess" in message and "import" in message
    ):
        family = "subprocess-import"
    else:
        family = f"{rule}:{title}"

    return finding["file"], finding["line"], family


def merge_findings(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge duplicate reports while preserving analyzer provenance."""
    merged: dict[tuple[str, int, str], dict[str, Any]] = {}

    for finding in findings:
        key = issue_key(finding)
        current = merged.get(key)

        if current is None:
            item = finding.copy()
            item["rule_ids"] = list(
                finding.get("rule_ids", [finding["rule_id"]])
            )
            item["sources"] = list(
                finding.get("sources", [finding["source"]])
            )
            item["occurrences"] = finding.get("occurrences", 1)
            merged[key] = item
            continue

        current["occurrences"] += finding.get("occurrences", 1)

        for rule_id in finding.get(
            "rule_ids", [finding["rule_id"]]
        ):
            if rule_id not in current["rule_ids"]:
                current["rule_ids"].append(rule_id)

        for source in finding.get(
            "sources", [finding["source"]]
        ):
            if source not in current["sources"]:
                current["sources"].append(source)

        if SEVERITY_ORDER.get(
            finding["severity"], 4
        ) < SEVERITY_ORDER.get(current["severity"], 4):
            current["severity"] = finding["severity"]
            current["title"] = finding["title"]
            current["message"] = finding["message"]
            current["suggestion"] = finding["suggestion"]

    results = list(merged.values())

    for item in results:
        item["rule_id"] = ", ".join(item["rule_ids"])
        item["source"] = ", ".join(item["sources"])

    return results


FIX_RECOMMENDATIONS = {
    "RM107": (
        "Avoid shell=True when commands contain untrusted input. "
        "Pass the executable and its arguments as a list with shell=False. "
        "Review the required arguments before changing the command."
    ),
    "B602": (
        "Review shell=True for command-injection risks. Prefer an argument "
        "list with shell=False when shell features are not required."
    ),
    "RM103": (
        "Avoid eval() on user-controlled input. For Python literals, consider "
        "ast.literal_eval(); for structured data, prefer json.loads()."
    ),
    "B307": (
        "Avoid eval() on untrusted input. Use ast.literal_eval() for supported "
        "Python literals or a parser designed for your input format."
    ),
    "RM101": (
        "Replace the mutable default with None, then create a new collection "
        "inside the function. This prevents state leaking between calls."
    ),
    "B006": (
        "Avoid mutable default arguments. Use None as the default and create "
        "a fresh list, dictionary, or set inside the function."
    ),
    "RM102": (
        "Catch specific exception types that the function can handle. "
        "Allow unexpected exceptions to propagate or handle them explicitly."
    ),
    "E722": (
        "Replace the bare except with an appropriate exception type, such as "
        "ValueError or OSError, based on the operation being handled."
    ),
    "RM106": (
        "Never deserialize pickle data from an untrusted source. Prefer JSON "
        "or another non-executable data format when appropriate."
    ),
    "RM105": (
        "Avoid constructing shell commands from untrusted input. Prefer "
        "subprocess with an argument list and shell=False."
    ),
    "RM104": (
        "Avoid compiling untrusted source into executable code. Validate "
        "inputs and use a safer data representation where possible."
    ),
}


def improve_recommendations(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add actionable guidance while preserving analyzer information."""
    for finding in findings:
        rule_ids = finding.get(
            "rule_ids", [finding.get("rule_id", "")]
        )

        recommendation = next(
            (
                FIX_RECOMMENDATIONS[rule_id]
                for rule_id in rule_ids
                if rule_id in FIX_RECOMMENDATIONS
            ),
            None,
        )

        if recommendation:
            finding["suggestion"] = recommendation

    return findings


def analyze_project(project_path: str | Path) -> dict[str, Any]:
    root = Path(project_path).resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError(
            "The project path must point to an existing directory."
        )

    findings: list[dict[str, Any]] = []
    files = collect_python_files(root)
    syntax_errors = 0

    for file_path in files:
        relative_path = relative_name(file_path, root)

        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append(
                make_finding(
                    "RM000",
                    "File could not be read",
                    "low",
                    relative_path,
                    1,
                    "The file could not be read as UTF-8 text.",
                    "Check the file encoding and permissions.",
                )
            )
            continue

        try:
            tree = ast.parse(source, filename=relative_path)
        except SyntaxError as error:
            syntax_errors += 1
            findings.append(
                make_finding(
                    "RM001",
                    "Python syntax error",
                    "high",
                    relative_path,
                    error.lineno or 1,
                    error.msg,
                    "Fix the syntax error before running this module.",
                )
            )
            continue

        visitor = BugRuleVisitor(relative_path)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    ruff_rows, ruff_error = run_tool(
        [
            sys.executable, "-m", "ruff", "check",
            "--output-format", "json", "--no-cache", str(root),
        ],
        root,
    )

    for item in ruff_rows:
        location = item.get("location") or {}

        findings.append(
            make_finding(
                item.get("code") or "RUFF",
                item.get("message") or "Code quality issue",
                "low",
                normalize_path(item.get("filename", ""), root),
                location.get("row") or 1,
                item.get("message") or "Ruff reported an issue.",
                item.get("message") or "Review and fix this lint finding.",
                "Ruff",
            )
        )

    bandit_rows, bandit_error = run_tool(
        [
            sys.executable, "-m", "bandit", "-r", "-f", "json",
            "-q", str(root),
        ],
        root,
    )

    for item in bandit_rows:
        severity = str(
            item.get("issue_severity", "LOW")
        ).lower()

        if severity not in SEVERITY_ORDER:
            severity = "low"

        findings.append(
            make_finding(
                item.get("test_id") or "BANDIT",
                item.get("test_name") or "Security finding",
                severity,
                normalize_path(item.get("filename", ""), root),
                item.get("line_number") or 1,
                item.get("issue_text") or "Bandit reported a security issue.",
                item.get("more_info")
                or "Review this finding and verify whether the code is safe.",
                "Bandit",
            )
        )

    # Keep both calls inside analyze_project().
    findings = merge_findings(findings)
    findings = improve_recommendations(findings)

    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 4),
            item["file"],
            item["line"],
            item["rule_id"],
        )
    )

    counts = {
        severity: sum(
            item["severity"] == severity for item in findings
        )
        for severity in SEVERITY_ORDER
    }

    return {
        "project_path": str(root),
        "files_analyzed": len(files),
        "syntax_errors": syntax_errors,
        "total_findings": len(findings),
        "severity_counts": counts,
        "findings": findings,
        "tools": {
            "custom_ast": "completed",
            "ruff": (
                "completed" if ruff_error is None else ruff_error
            ),
            "bandit": (
                "completed" if bandit_error is None else bandit_error
            ),
        },
    }
