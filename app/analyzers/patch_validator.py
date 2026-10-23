
import ast
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def validate_patch_candidate(
    project_root: Path,
    relative_file: str,
    candidate_code: str,
    run_tests: bool = False,
    test_timeout: int = 30,
) -> dict[str, Any]:
    """
    Validate proposed Python code without changing the project source.

    Optional tests run from a temporary copy of the project.
    Only use this feature with trusted code: temporary copies are
    not a security sandbox.
    """
    root = project_root.resolve()
    relative_path = Path(relative_file)

    if relative_path.is_absolute() or ".." in relative_path.parts:
        return {
            "valid": False,
            "syntax_valid": False,
            "tests_run": False,
            "error": "The file path must remain inside the project.",
            "read_only": True,
        }

    target = (root / relative_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        return {
            "valid": False,
            "syntax_valid": False,
            "tests_run": False,
            "error": "The file is outside the project.",
            "read_only": True,
        }

    if target.suffix.lower() != ".py":
        return {
            "valid": False,
            "syntax_valid": False,
            "tests_run": False,
            "error": "Only Python candidates are supported.",
            "read_only": True,
        }

    try:
        ast.parse(candidate_code, filename=relative_path.as_posix())
    except SyntaxError as exc:
        return {
            "valid": False,
            "syntax_valid": False,
            "tests_run": False,
            "error": (
                f"Syntax error: {exc.msg} "
                f"at line {exc.lineno}."
            ),
            "read_only": True,
        }

    result: dict[str, Any] = {
        "valid": True,
        "syntax_valid": True,
        "tests_run": False,
        "tests_passed": None,
        "test_output": None,
        "note": "Syntax validation passed.",
        "read_only": True,
    }

    if not run_tests:
        result["note"] = (
            "Syntax validation passed. Tests were not requested."
        )
        return result

    if not target.is_file():
        result.update(
            valid=False,
            note="The original target file does not exist.",
        )
        return result

    try:
        # Copy the project into a temporary directory and replace only
        # the candidate file in that copy. The real project is untouched.
        with tempfile.TemporaryDirectory(prefix="repomedic-validation-") as temp:
            temp_root = Path(temp) / "project"
            temp_root.mkdir()

            for item in root.rglob("*"):
                if not item.is_file():
                    continue

                relative = item.relative_to(root)

                # Avoid copying common generated folders and environments.
                if any(
                    part in {
                        ".git",
                        ".venv",
                        "venv",
                        "node_modules",
                        "__pycache__",
                    }
                    for part in relative.parts
                ):
                    continue

                destination = temp_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)

                try:
                    destination.write_bytes(item.read_bytes())
                except OSError:
                    continue

            copied_target = temp_root / relative_path
            copied_target.parent.mkdir(parents=True, exist_ok=True)
            copied_target.write_text(candidate_code, encoding="utf-8")

            tests_dir = temp_root / "tests"
            if not tests_dir.is_dir():
                result.update(
                    valid=True,
                    tests_run=False,
                    note=(
                        "Syntax validation passed, but no tests folder "
                        "was found in the temporary project copy."
                    ),
                )
                return result

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "tests",
                ],
                cwd=temp_root,
                capture_output=True,
                text=True,
                timeout=max(1, min(test_timeout, 120)),
                check=False,
            )

            output = (completed.stdout + "\n" + completed.stderr).strip()

            result.update(
                tests_run=True,
                tests_passed=completed.returncode == 0,
                test_return_code=completed.returncode,
                test_output=output[-12000:],
                valid=completed.returncode == 0,
                note=(
                    "Tests passed against the temporary candidate."
                    if completed.returncode == 0
                    else "Tests failed against the temporary candidate."
                ),
            )
            return result

    except subprocess.TimeoutExpired:
        result.update(
            valid=False,
            tests_run=True,
            tests_passed=False,
            note=f"Tests exceeded the {test_timeout}-second timeout.",
        )
        return result
    except OSError as exc:
        result.update(
            valid=False,
            tests_run=False,
            error=f"Could not run validation: {exc}",
        )
        return result
