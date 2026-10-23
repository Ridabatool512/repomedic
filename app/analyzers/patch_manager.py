
import ast
import difflib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _diff_lines(code: str) -> list[str]:
    return [line + "\n" for line in code.splitlines()]


def _backup_root() -> Path:
    return Path(__file__).resolve().parents[2] / "backups" / "patches"


def _metadata_path(patch_id: str) -> Path:
    if (
        not patch_id
        or len(patch_id) != 32
        or not all(
            character in "0123456789abcdef"
            for character in patch_id.lower()
        )
    ):
        raise ValueError("Invalid patch ID.")

    return _backup_root() / f"{patch_id}.json"


def _safe_target(project_root: Path, relative_file: str) -> Path:
    root = project_root.resolve()
    relative = Path(relative_file)

    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("File path must remain inside the project.")

    target = (root / relative).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("File is outside the project.") from exc

    if target.suffix.lower() != ".py":
        raise ValueError("Only Python files are supported.")

    if not target.is_file():
        raise ValueError("Target file does not exist.")

    return target


def _atomic_write(target: Path, content: str) -> None:
    """Write text through a temporary file to avoid partial writes."""
    temp_name = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            delete=False,
            suffix=".repomedic-tmp",
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_name = temp_file.name

        os.replace(temp_name, target)
        temp_name = None

    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _atomic_write_json(target: Path, data: dict) -> None:
    """Persist metadata atomically."""
    _atomic_write(target, json.dumps(data, indent=2))


def preview_application(
    project_root: Path,
    relative_file: str,
    proposed_code: str,
) -> dict:
    target = _safe_target(project_root, relative_file)
    original = target.read_text(encoding="utf-8")

    ast.parse(proposed_code, filename=relative_file)

    diff = "".join(
        difflib.unified_diff(
            _diff_lines(original),
            _diff_lines(proposed_code),
            fromfile=f"original/{relative_file}",
            tofile=f"proposed/{relative_file}",
        )
    )

    return {
        "file": relative_file,
        "changed": original != proposed_code,
        "diff": diff,
        "requires_approval": True,
        "applied": False,
        "read_only": True,
    }


def apply_approved_patch(
    project_root: Path,
    relative_file: str,
    proposed_code: str,
    approved: bool,
) -> dict:
    if approved is not True:
        raise ValueError("Explicit user approval is required.")

    target = _safe_target(project_root, relative_file)
    original = target.read_text(encoding="utf-8")

    ast.parse(proposed_code, filename=relative_file)

    if original == proposed_code:
        return {
            "applied": False,
            "message": "The file already matches the proposed code.",
        }

    backup_root = _backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)

    patch_id = uuid.uuid4().hex
    backup_file = backup_root / f"{patch_id}.bak"
    metadata_file = backup_root / f"{patch_id}.json"

    metadata = {
        "patch_id": patch_id,
        "project_root": str(project_root.resolve()),
        "file": relative_file,
        "backup_file": str(backup_file.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "applied",
        "rolled_back_at": None,
    }

    backup_file.write_text(original, encoding="utf-8")

    try:
        _atomic_write_json(metadata_file, metadata)
        _atomic_write(target, proposed_code)

    except OSError:
        # Restore the original if applying the proposed code fails.
        try:
            if target.is_file():
                _atomic_write(target, original)
        finally:
            metadata_file.unlink(missing_ok=True)
            backup_file.unlink(missing_ok=True)
        raise

    return {
        "applied": True,
        "patch_id": patch_id,
        "file": relative_file,
        "backup_created": True,
        "backup_file": str(backup_file.resolve()),
        "status": "applied",
        "message": (
            "Patch applied with a backup. Keep the patch ID for rollback."
        ),
    }


def list_patch_history(project_root: Path | None = None) -> dict:
    """Return persistent patch metadata, newest first."""
    backup_root = _backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)

    requested_root = project_root.resolve() if project_root else None
    records = []

    for metadata_file in backup_root.glob("*.json"):
        try:
            metadata = json.loads(
                metadata_file.read_text(encoding="utf-8")
            )

            patch_id = metadata.get("patch_id", metadata_file.stem)
            record_root = Path(metadata["project_root"]).resolve()

            if requested_root and record_root != requested_root:
                continue

            backup_file = Path(metadata["backup_file"]).resolve()

            try:
                backup_file.relative_to(backup_root.resolve())
                backup_valid = backup_file.is_file()
            except ValueError:
                backup_valid = False

            records.append({
                "patch_id": patch_id,
                "project_root": str(record_root),
                "file": metadata.get("file", "Unknown file"),
                "created_at": metadata.get("created_at"),
                "status": metadata.get("status", "applied"),
                "rolled_back_at": metadata.get("rolled_back_at"),
                "backup_file": str(backup_file),
                "backup_exists": backup_valid,
            })

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ):
            # Ignore malformed records so one bad file cannot break history.
            continue

    records.sort(
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )

    return {
        "total": len(records),
        "patches": records,
    }


def rollback_patch(project_root: Path, patch_id: str) -> dict:
    """Restore a patch backup and persist its rolled-back status."""
    metadata_file = _metadata_path(patch_id)

    if not metadata_file.is_file():
        raise ValueError("Patch backup record was not found.")

    metadata = json.loads(
        metadata_file.read_text(encoding="utf-8")
    )

    root = project_root.resolve()

    if Path(metadata["project_root"]).resolve() != root:
        raise ValueError("This patch belongs to a different project.")

    if metadata.get("status") == "rolled_back":
        raise ValueError("This patch has already been rolled back.")

    target = _safe_target(root, metadata["file"])
    backup_root = _backup_root().resolve()
    backup_file = Path(metadata["backup_file"]).resolve()

    try:
        backup_file.relative_to(backup_root)
    except ValueError as exc:
        raise ValueError("Backup path is invalid.") from exc

    if not backup_file.is_file():
        raise ValueError("Backup file is missing.")

    previous_code = backup_file.read_text(encoding="utf-8")

    # Validate the saved original before restoring it.
    ast.parse(previous_code, filename=metadata["file"])

    # Restore the source first. If restoration fails, status stays unchanged.
    _atomic_write(target, previous_code)

    # Persist rollback history only after the source restoration succeeds.
    metadata["status"] = "rolled_back"
    metadata["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

    _atomic_write_json(metadata_file, metadata)

    return {
        "rolled_back": True,
        "patch_id": patch_id,
        "file": metadata["file"],
        "status": "rolled_back",
        "rolled_back_at": metadata["rolled_back_at"],
        "message": "Original file content restored from backup.",
    }
