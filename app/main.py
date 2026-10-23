
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.analyzers.bug_detector import analyze_project as analyze_bugs
from app.analyzers.dependency_analyzer import build_dependency_graph
from app.analyzers.fix_preview import build_fix_preview
from app.analyzers.fix_recommender import recommend_fix
from app.analyzers.impact_analyzer import analyze_change_impact
from app.analyzers.patch_manager import (
    preview_application,
    apply_approved_patch,
    rollback_patch,
    list_patch_history,
)
from app.analyzers.patch_validator import validate_patch_candidate
from app.analyzers.project_scanner import save_report, scan_project
from app.analyzers.safe_patches import generate_safe_patch
from app.github_importer import import_public_repository


app = FastAPI(
    title="RepoMedic API",
    description=(
        "Codebase intelligence, dependency analysis, "
        "change-impact assessment, and GitHub repository importing."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://repomedic-delta.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Workspace configuration
# --------------------------------------------------

WORKSPACE_ROOT = Path(
    os.getenv(
        "REPOMEDIC_WORKSPACE_ROOT",
        str(Path(__file__).resolve().parent.parent / "workspace"),
    )
).resolve()


def validate_project_path(project_path: str) -> Path:
    path = Path(project_path).resolve()

    try:
        path.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="Scanning is restricted to the workspace directory.",
        ) from exc

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Project directory does not exist.",
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="The supplied path is not a directory.",
        )

    return path


# --------------------------------------------------
# Request models
# --------------------------------------------------

class ScanRequest(BaseModel):
    project_path: str = Field(min_length=1)


class ImpactRequest(BaseModel):
    project_path: str = Field(min_length=1)
    changed_file: str = Field(min_length=1)


class FixPreviewRequest(BaseModel):
    project_path: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    rule_id: str = Field(min_length=1)
    rule_ids: list[str] = Field(default_factory=list)
    title: str = ""
    severity: str = "low"
    message: str = ""
    suggestion: str = ""


class PatchValidationRequest(BaseModel):
    project_path: str = Field(min_length=1)
    file: str = Field(min_length=1)
    proposed_code: str
    run_tests: bool = False


class PatchApplicationRequest(BaseModel):
    project_path: str = Field(min_length=1)
    file: str = Field(min_length=1)
    proposed_code: str


class PatchApprovalRequest(PatchApplicationRequest):
    approved: bool = False


class PatchRollbackRequest(BaseModel):
    project_path: str = Field(min_length=1)
    patch_id: str = Field(min_length=1)


class PatchHistoryRequest(BaseModel):
    project_path: str = Field(min_length=1)


class GitHubImportRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=500)


# --------------------------------------------------
# Basic endpoints
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "RepoMedic API",
        "version": app.version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------
# GitHub repository importing
# --------------------------------------------------

@app.post("/api/github/import")
def import_github_repository(request: GitHubImportRequest):
    return import_public_repository(request.repository_url)


# --------------------------------------------------
# Project scanning
# --------------------------------------------------

@app.post("/api/scan")
def scan(request: ScanRequest):
    project_path = validate_project_path(request.project_path)

    try:
        report = scan_project(str(project_path))
        save_report(report, "reports/api-scan-report.json")
        return report
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/api/dependencies")
def dependencies(request: ScanRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return build_dependency_graph(str(project_path))
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/api/impact")
def impact(request: ImpactRequest):
    project_path = validate_project_path(request.project_path)

    try:
        graph = build_dependency_graph(str(project_path))

        return analyze_change_impact(
            graph,
            request.changed_file.replace("\\", "/"),
        )
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# Bug detection and fix recommendations
# --------------------------------------------------

@app.post("/api/bugs")
def detect_project_bugs(payload: dict[str, str]):
    project_path = validate_project_path(
        payload.get("project_path", "")
    )
    return analyze_bugs(project_path)


@app.post("/api/bugs/fix-preview")
def preview_bug_fix(request: FixPreviewRequest):
    project_path = validate_project_path(request.project_path)

    finding = {
        "file": request.file,
        "line": request.line,
        "rule_id": request.rule_id,
        "rule_ids": request.rule_ids or [request.rule_id],
        "title": request.title,
        "severity": request.severity,
        "message": request.message,
        "suggestion": request.suggestion,
    }

    return build_fix_preview(project_path, finding)


@app.post("/api/bugs/recommend-fix")
def recommend_bug_fix(request: FixPreviewRequest):
    project_path = validate_project_path(request.project_path)

    finding = {
        "file": request.file,
        "line": request.line,
        "rule_id": request.rule_id,
        "rule_ids": request.rule_ids or [request.rule_id],
        "title": request.title,
        "severity": request.severity,
        "message": request.message,
        "suggestion": request.suggestion,
    }

    return recommend_fix(project_path, finding)


@app.post("/api/bugs/safe-patch")
def safe_patch_preview(request: FixPreviewRequest):
    project_path = validate_project_path(request.project_path)

    finding = {
        "file": request.file,
        "line": request.line,
        "rule_id": request.rule_id,
        "rule_ids": request.rule_ids or [request.rule_id],
        "title": request.title,
        "severity": request.severity,
        "message": request.message,
        "suggestion": request.suggestion,
    }

    return generate_safe_patch(project_path, finding)


# --------------------------------------------------
# Patch validation and preview
# --------------------------------------------------

@app.post("/api/bugs/validate-patch")
def validate_bug_patch(request: PatchValidationRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return validate_patch_candidate(
            project_root=project_path,
            relative_file=request.file,
            candidate_code=request.proposed_code,
            run_tests=request.run_tests,
        )
    except (ValueError, OSError, SyntaxError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/api/bugs/patch-preview")
def preview_patch_application(request: PatchApplicationRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return preview_application(
            project_root=project_path,
            relative_file=request.file,
            proposed_code=request.proposed_code,
        )
    except (ValueError, OSError, SyntaxError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# Apply an approved patch
# --------------------------------------------------

@app.post("/api/bugs/apply-patch")
def apply_patch(request: PatchApprovalRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return apply_approved_patch(
            project_root=project_path,
            relative_file=request.file,
            proposed_code=request.proposed_code,
            approved=request.approved,
        )
    except (ValueError, OSError, SyntaxError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# Patch history
# --------------------------------------------------

@app.post("/api/bugs/patch-history")
def get_patch_history(request: PatchHistoryRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return list_patch_history(project_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# Roll back a previously applied patch
# --------------------------------------------------

@app.post("/api/bugs/rollback-patch")
def rollback_applied_patch(request: PatchRollbackRequest):
    project_path = validate_project_path(request.project_path)

    try:
        return rollback_patch(
            project_root=project_path,
            patch_id=request.patch_id,
        )
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
