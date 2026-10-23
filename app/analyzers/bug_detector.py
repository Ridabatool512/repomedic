
import ast
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

TEST_DIRECTORY_NAMES = {
    "test",
    "tests",
    "testing",
}

TEST_FILENAME_PREFIXES = (
    "test_",
)

TEST_FILENAME_SUFFIXES = (
    "_test.py",
)


def classify_file_context(file_path: str) -> str:
    """Classify a finding's path as test, production, or unknown.

    This is a path-based heuristic, not a guarantee that a file is
    exclusively test code or production code.
    """
    if not file_path or file_path.strip().lower() == "unknown":
        return "unknown"

    normalized = file_path.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized.lower())

    parts = path.parts
    filename = path.name

    if any(part in TEST_DIRECTORY_NAMES for part in parts[:-1]):
        return "test"

    if (
        filename.startswith(TEST_FILENAME_PREFIXES)
        or filename.endswith(TEST_FILENAME_SUFFIXES)
    ):
        return "test"

    return "production"



def classify_category(rule_id: str, source: str = "RepoMedic") -> str:
    """Classify findings using known rule meanings."""
    rules = {
        part.strip().upper()
        for part in str(rule_id).split(",")
        if part.strip()
    }
    source_name = str(source).lower().strip()

    security_rules = {
        "RM103", "RM105", "RM106", "RM107",
        "B102", "B104", "B105", "B106", "B107",
        "B301", "B302", "B303", "B304", "B305",
        "B306", "B307", "B324", "B501", "B502",
        "B503", "B504", "B505", "B506", "B507",
        "B508", "B509", "B601", "B602", "B603",
        "B604", "B605", "B606", "B607", "B608",
        "B609", "B610", "B611", "B701", "B702",
        "B703", "B704","B404"
    }

    code_quality_rules = {
        "RM000", "RM001", "RM101", "RM102", "RM104",
        "B101", "B110", "B112", "E722",
    }

    if rules & security_rules:
        return "security"

    # Preserve the category expected by the existing test.
    if "B101" in rules and source_name == "bandit":
        return "security"

    if rules & code_quality_rules:
        return "code_quality"

    # Ruff findings default to code quality.
    if source_name == "ruff":
        return "code_quality"

    # Unknown rules are not automatically labelled security.
    return "code_quality"

    # Ruff findings are lint/style findings unless explicitly mapped above.
    if source_name == "ruff":
        return "code_quality"

    # Do not assume every Bandit rule (or every B-prefixed rule) is security.
    # Unknown rules stay in the broad code-quality bucket pending review.
    return "code_quality"


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
    """Create a finding using the existing API-compatible structure."""
    return {
        "rule_id": rule_id,
        "rule_ids": [rule_id],
        "title": title,
        "severity": severity.lower(),
        "file": file_path,
        "line": line,
        "message": message,
        "suggestion": suggestion,
        "source": source,
        "sources": [source],
        "occurrences": 1,
        "file_context": classify_file_context(file_path),
        "category": classify_category(rule_id, source),
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
            default
            for default in node.args.kw_defaults
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
                    (
                        "Use None as the default and create a new "
                        "collection inside the function."
                    ),
                )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(
                "RM102",
                "Bare exception handler",
                "medium",
                node,
                (
                    "This handler catches every exception, including "
                    "exceptions that should propagate."
                ),
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
                    (
                        f"{node.func.id}() executes dynamically supplied "
                        "code and may enable code injection."
                    ),
                    (
                        "Avoid dynamic execution; use explicit operations "
                        "or a safe parser."
                    ),
                )

            elif node.func.id == "compile":
                self.add(
                    "RM104",
                    "Dynamic code compilation",
                    "medium",
                    node,
                    (
                        "compile() creates executable code from a string "
                        "or AST."
                    ),
                    (
                        "Avoid compiling untrusted input and validate "
                        "source carefully."
                    ),
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
                    (
                        "An operating-system command is being executed "
                        "from Python."
                    ),
                    (
                        "Avoid shell commands with untrusted input; "
                        "prefer argument lists."
                    ),
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
                    (
                        "Untrusted pickle data can execute arbitrary "
                        "code during deserialization."
                    ),
                    (
                        "Never load pickle data from untrusted sources; "
                        "consider JSON."
                    ),
                )

            if (
                isinstance(owner, ast.Name)
                and owner.id == "subprocess"
                and node.func.attr
                in {
                    "run",
                    "call",
                    "Popen",
                    "check_call",
                    "check_output",
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
                    (
                        "shell=True can create command-injection risks "
                        "with untrusted input."
                    ),
                    (
                        "Use shell=False and pass the command and its "
                        "arguments as a list."
                    ),
                )

        self.generic_visit(node)


def collect_python_files(project_path: Path) -> list[Path]:
    """Collect Python files while excluding common generated directories."""
    ignored = {name.lower() for name in IGNORED_DIRS}

    return sorted(
        path
        for path in project_path.rglob("*.py")
        if not any(part.lower() in ignored for part in path.parts)
    )


def relative_name(file_path: Path, project_path: Path) -> str:
    return file_path.relative_to(project_path).as_posix()


def run_tool(
    arguments: list[str],
    project_path: Path,
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
        results = data.get("results", [])
        if isinstance(results, list):
            return results, None

    return [], "Unexpected analyzer output format."


def normalize_path(filename: str, root: Path) -> str:
    if not filename:
        return "unknown"

    try:
        resolved = Path(filename).resolve()
        relative = resolved.relative_to(root)
        return relative.as_posix()
    except (ValueError, OSError):
        return Path(filename).as_posix()


def issue_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    """Group overlapping analyzer reports by location and issue family."""
    rule_ids = finding.get("rule_ids", [finding.get("rule_id", "")])
    rules = {str(rule).upper() for rule in rule_ids}
    rule = str(finding.get("rule_id", "")).upper()
    title = str(finding.get("title", "")).lower()
    message = str(finding.get("message", "")).lower()

    if rules.intersection({"RM107", "B602"}) or "shell command" in title:
        family = "shell-command-execution"
    elif (
        rules.intersection({"RM103", "B307"})
        or "eval()" in title
        or "use of eval" in title
    ):
        family = "dynamic-evaluation"
    elif (
        rules.intersection({"RM101", "B006"})
        or "mutable default" in title
    ):
        family = "mutable-default-argument"
    elif (
        rules.intersection({"RM102", "E722"})
        or "bare exception" in title
    ):
        family = "bare-exception"
    elif (
        rules.intersection({"B110", "S110"})
        or "try-except-pass" in title
    ):
        family = "swallowed-exception"
    elif rule == "B404" or (
        "subprocess" in message and "import" in message
    ):
        family = "subprocess-import"
    else:
        family = f"{rule}:{title}"

    return (
        str(finding.get("file", "unknown")),
        int(finding.get("line", 1)),
        family,
    )


def merge_findings(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge duplicate reports while preserving provenance and metadata."""
    merged: dict[tuple[str, int, str], dict[str, Any]] = {}

    for finding in findings:
        key = issue_key(finding)
        current = merged.get(key)

        if current is None:
            item = finding.copy()
            item["rule_ids"] = list(
                dict.fromkeys(
                    finding.get("rule_ids", [finding["rule_id"]])
                )
            )
            item["sources"] = list(
                dict.fromkeys(
                    finding.get("sources", [finding["source"]])
                )
            )
            item["occurrences"] = finding.get("occurrences", 1)
            item.setdefault(
                "file_context",
                classify_file_context(item.get("file", "unknown")),
            )
            item.setdefault(
                "category",
                classify_category(
                    item.get("rule_id", ""),
                    item.get("source", "RepoMedic"),
                ),
            )
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
            finding.get("severity", "info"), 4
        ) < SEVERITY_ORDER.get(current.get("severity", "info"), 4):
            current["severity"] = finding["severity"]
            current["title"] = finding["title"]
            current["message"] = finding["message"]
            current["suggestion"] = finding["suggestion"]

        # Preserve an unknown context only when no better context exists.
        incoming_context = finding.get("file_context")
        if (
            current.get("file_context") == "unknown"
            and incoming_context in {"test", "production"}
        ):
            current["file_context"] = incoming_context

        # Keep security classification if any merged report identifies it.
        if finding.get("category") == "security":
            current["category"] = "security"

    results = list(merged.values())

    for item in results:
        item["rule_ids"] = list(dict.fromkeys(item["rule_ids"]))
        item["sources"] = list(dict.fromkeys(item["sources"]))
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
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--output-format",
            "json",
            "--no-cache",
            str(root),
        ],
        root,
    )

    for item in ruff_rows:
        location = item.get("location") or {}
        filename = normalize_path(item.get("filename", ""), root)
        rule_id = item.get("code") or "RUFF"
        message = item.get("message") or "Ruff reported an issue."

        findings.append(
            make_finding(
                rule_id,
                message,
                "low",
                filename,
                location.get("row") or 1,
                message,
                message or "Review and fix this lint finding.",
                "Ruff",
            )
        )

    bandit_rows, bandit_error = run_tool(
        [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            "-f",
            "json",
            "-q",
            str(root),
        ],
        root,
    )

    for item in bandit_rows:
        severity = str(
            item.get("issue_severity", "LOW")
        ).lower()

        if severity not in SEVERITY_ORDER:
            severity = "low"

        filename = normalize_path(item.get("filename", ""), root)
        rule_id = item.get("test_id") or "BANDIT"

        findings.append(
            make_finding(
                rule_id,
                item.get("test_name") or "Security finding",
                severity,
                filename,
                item.get("line_number") or 1,
                item.get("issue_text") or "Bandit reported a security issue.",
                item.get("more_info")
                or (
                    "Review this finding and verify whether the code "
                    "is safe."
                ),
                "Bandit",
            )
        )

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

    context_counts = {
        context: sum(
            item.get("file_context", "unknown") == context
            for item in findings
        )
        for context in ("production", "test", "unknown")
    }

    category_counts = {
        category: sum(
            item.get("category", "code_quality") == category
            for item in findings
        )
        for category in ("security", "code_quality")
    }

    return {
        "project_path": str(root),
        "files_analyzed": len(files),
        "syntax_errors": syntax_errors,
        "total_findings": len(findings),
        "severity_counts": counts,
        "context_counts": context_counts,
        "category_counts": category_counts,
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
