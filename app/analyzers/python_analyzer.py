
import ast
from pathlib import Path


def analyze_python_file(file_path: str) -> dict:
    """Extract basic code intelligence from one Python source file."""

    path = Path(file_path)

    result = {
        "file": str(path),
        "status": "success",
        "functions": [],
        "classes": [],
        "imports": [],
        "calls": [],
        "errors": [],
    }

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

    except SyntaxError as exc:
        result["status"] = "error"
        result["errors"].append(
            {
                "type": "SyntaxError",
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.offset,
            }
        )
        return result

    except (OSError, UnicodeError) as exc:
        result["status"] = "error"
        result["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return result

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "is_async": isinstance(
                        node, ast.AsyncFunctionDef
                    ),
                }
            )

        elif isinstance(node, ast.ClassDef):
            result["classes"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(
                    {
                        "module": alias.name,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.ImportFrom):
            result["imports"].append(
                {
                    "module": node.module or "",
                    "line": node.lineno,
                }
            )

        elif isinstance(node, ast.Call):
            name = _get_call_name(node.func)

            if name:
                result["calls"].append(
                    {
                        "name": name,
                        "line": node.lineno,
                    }
                )

    return result


def _get_call_name(node: ast.expr) -> str | None:
    """Convert a function call expression into a readable name."""

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _get_call_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None
