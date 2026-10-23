
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException


WORKSPACE_ROOT = (
    Path(__file__).resolve().parent.parent / "workspace"
).resolve()


def parse_github_url(repository_url: str) -> tuple[str, str]:
    """Validate a public GitHub repository URL."""

    value = repository_url.strip()

    if not value:
        raise HTTPException(
            status_code=400,
            detail="Please enter a GitHub repository URL.",
        )

    # Accept owner/repository shorthand.
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        owner, repository = value.split("/", 1)

    else:
        parsed = urlparse(value)

        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Use a public GitHub URL such as "
                    "https://github.com/owner/repository."
                ),
            )

        parts = parsed.path.strip("/").split("/")

        if len(parts) != 2 or not all(parts):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Enter a repository URL, "
                    "not a profile or subpage."
                ),
            )

        owner, repository = parts

        if repository.endswith(".git"):
            repository = repository[:-4]

    # Validate repository owner and name.
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository)
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise HTTPException(
            status_code=400,
            detail="The GitHub owner or repository name is invalid.",
        )

    return owner, repository


def import_public_repository(repository_url: str) -> dict:
    """Import a public GitHub repository into RepoMedic's workspace."""

    owner, repository = parse_github_url(repository_url)

    destination = (
        WORKSPACE_ROOT / "github" / owner / repository
    ).resolve()

    # Ensure the destination remains inside the workspace.
    try:
        destination.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository destination.",
        ) from exc

    normalized_url = (
        f"https://github.com/{owner}/{repository}"
    )

    # Reuse an existing valid Git clone rather than reporting
    # a duplicate-import error.
    if destination.exists():

        if not destination.is_dir():
            raise HTTPException(
                status_code=409,
                detail=(
                    "The repository destination exists "
                    "but is not a directory."
                ),
            )

        git_directory = destination / ".git"

        if not git_directory.exists():
            raise HTTPException(
                status_code=409,
                detail=(
                    "A folder already exists at this repository path, "
                    "but it is not a Git repository. Rename or remove "
                    "that folder before importing again."
                ),
            )

        return {
            "message": "Repository is already imported.",
            "owner": owner,
            "repository": repository,
            "repository_url": normalized_url,
            "project_path": str(destination),
        }

    # Create the parent directory only when necessary.
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    clone_url = f"{normalized_url}.git"

    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=NUL",
                "clone",
                "--depth",
                "1",
                "--no-recurse-submodules",
                "--",
                clone_url,
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Git was not found. Install Git "
                "and restart RepoMedic."
            ),
        ) from exc

    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(destination, ignore_errors=True)

        raise HTTPException(
            status_code=504,
            detail=(
                "Import timed out. Try a smaller repository."
            ),
        ) from exc

    # Remove an incomplete clone after a failed Git command.
    if result.returncode != 0:
        shutil.rmtree(destination, ignore_errors=True)

        raise HTTPException(
            status_code=400,
            detail=(
                "Could not import this repository. Check that "
                "the URL is correct and the repository is public."
            ),
        )

    return {
        "message": "Repository imported successfully.",
        "owner": owner,
        "repository": repository,
        "repository_url": normalized_url,
        "project_path": str(destination),
    }
