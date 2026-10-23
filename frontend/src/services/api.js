
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "https://repomedic-api-hyg8.onrender.com",
  // Allow large repository analyses (especially Bug Check) more time to finish.
  timeout: 180000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ============================================================
// HEALTH CHECK
// ============================================================

export async function getHealth() {
  const response = await api.get("/health");
  return response.data;
}

// ============================================================
// GITHUB REPOSITORY IMPORT
// ============================================================

export async function importGitHubRepository(repositoryUrl) {
  const response = await api.post("/api/github/import", {
    repository_url: repositoryUrl.trim(),
  });

  return response.data;
}

// ============================================================
// PROJECT SCANNING
// ============================================================

export async function scanProject(projectPath) {
  const response = await api.post("/api/scan", {
    project_path: projectPath,
  });

  return response.data;
}

// ============================================================
// DEPENDENCY ANALYSIS
// ============================================================

export async function analyzeDependencies(projectPath) {
  const response = await api.post("/api/dependencies", {
    project_path: projectPath,
  });

  return response.data;
}

// ============================================================
// CHANGE IMPACT ANALYSIS
// ============================================================

export async function analyzeImpact(projectPath, changedFile) {
  const response = await api.post("/api/impact", {
    project_path: projectPath,
    changed_file: changedFile,
  });

  return response.data;
}

// ============================================================
// SMART BUG DETECTION
// ============================================================

export async function detectBugs(projectPath) {
  const response = await api.post("/api/bugs", {
    project_path: projectPath,
  });

  return response.data;
}

// ============================================================
// BUG FIX PREVIEW
// ============================================================

export async function previewBugFix(projectPath, finding) {
  const response = await api.post("/api/bugs/fix-preview", {
    project_path: projectPath,
    file: finding.file ?? finding.path,
    line: finding.line,
    rule_id: finding.rule_id ?? finding.rule ?? "UNKNOWN",
    rule_ids: finding.rule_ids ?? [],
    title: finding.title ?? "",
    severity: finding.severity ?? "low",
    message: finding.message ?? finding.description ?? "",
    suggestion: finding.suggestion ?? finding.recommendation ?? "",
  });

  return response.data;
}

// ============================================================
// FIX RECOMMENDATION
// ============================================================

export async function recommendFix(projectPath, finding) {
  const response = await api.post("/api/bugs/recommend-fix", {
    project_path: projectPath,
    file: finding.file ?? finding.path,
    line: finding.line,
    rule_id: finding.rule_id ?? finding.rule ?? "UNKNOWN",
    rule_ids: finding.rule_ids ?? [],
    title: finding.title ?? "",
    severity: finding.severity ?? "low",
    message: finding.message ?? finding.description ?? "",
    suggestion: finding.suggestion ?? finding.recommendation ?? "",
  });

  return response.data;
}

// ============================================================
// SAFE PATCH PREVIEW
// ============================================================

export async function safePatchPreview(projectPath, finding) {
  const response = await api.post("/api/bugs/safe-patch", {
    project_path: projectPath,
    file: finding.file ?? finding.path,
    line: finding.line,
    rule_id: finding.rule_id ?? finding.rule ?? "UNKNOWN",
    rule_ids: finding.rule_ids ?? [
      finding.rule_id ?? finding.rule ?? "UNKNOWN",
    ],
    title: finding.title ?? "",
    severity: finding.severity ?? "low",
    message: finding.message ?? finding.description ?? "",
    suggestion: finding.suggestion ?? finding.recommendation ?? "",
  });

  return response.data;
}

// ============================================================
// PATCH VALIDATION
// ============================================================

export async function validatePatch(
  projectPath,
  file,
  proposedCode,
  runTests = false
) {
  const response = await api.post("/api/bugs/validate-patch", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
    run_tests: runTests,
  });

  return response.data;
}

// ============================================================
// PATCH APPLICATION PREVIEW
// ============================================================

export async function previewApplication(
  projectPath,
  file,
  proposedCode
) {
  const response = await api.post("/api/bugs/patch-preview", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
  });

  return response.data;
}

// ============================================================
// APPLY AN EXPLICITLY APPROVED PATCH
// ============================================================

export async function applyApprovedPatch(
  projectPath,
  file,
  proposedCode,
  approved
) {
  const response = await api.post("/api/bugs/apply-patch", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
    approved: approved === true,
  });

  return response.data;
}

// ============================================================
// PATCH HISTORY
// ============================================================

export async function getPatchHistory(projectPath) {
  const response = await api.post("/api/bugs/patch-history", {
    project_path: projectPath,
  });

  return response.data;
}

// ============================================================
// ROLL BACK AN APPLIED PATCH
// ============================================================

export async function rollbackPatch(projectPath, patchId) {
  const response = await api.post("/api/bugs/rollback-patch", {
    project_path: projectPath,
    patch_id: patchId,
  });

  return response.data;
}
