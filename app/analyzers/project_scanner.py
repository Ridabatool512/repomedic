
import json
from pathlib import Path

from app.analyzers.python_analyzer import analyze_python_file

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
}


def scan_project(project_path: str) -> dict:
    """Scan a project and return a structured code intelligence report."""

    root = Path(project_path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Project path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Expected a directory: {root}")

    files = []

    for path in sorted(root.rglob("*.py")):
        relative_path = path.relative_to(root)

        if any(
            part in IGNORED_DIRECTORIES
            for part in relative_path.parts
        ):
            continue

        result = analyze_python_file(str(path))
        result["file"] = relative_path.as_posix()
        files.append(result)

    successful_files = [
        item for item in files if item["status"] == "success"
    ]

    failed_files = [
        item for item in files if item["status"] == "error"
    ]

    total_functions = sum(
        len(item["functions"]) for item in successful_files
    )

    total_classes = sum(
        len(item["classes"]) for item in successful_files
    )

    total_imports = sum(
        len(item["imports"]) for item in successful_files
    )

    total_calls = sum(
        len(item["calls"]) for item in successful_files
    )

    syntax_errors = [
        {
            "file": item["file"],
            **error,
        }
        for item in failed_files
        for error in item["errors"]
        if error["type"] == "SyntaxError"
    ]

    return {
        "project_path": str(root),
        "summary": {
            "python_files": len(files),
            "successful_files": len(successful_files),
            "failed_files": len(failed_files),
            "functions": total_functions,
            "classes": total_classes,
            "imports": total_imports,
            "function_calls": total_calls,
            "syntax_errors": len(syntax_errors),
        },
        "files": files,
        "syntax_errors": syntax_errors,
    }


def save_report(report: dict, output_path: str) -> None:
    """Save the scan report as formatted JSON."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
