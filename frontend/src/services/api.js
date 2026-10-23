
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Health check
export async function getHealth() {
  const response = await api.get("/health");
  return response.data;
}

// Project scanning
export async function scanProject(projectPath) {
  const response = await api.post("/api/scan", {
    project_path: projectPath,
  });

  return response.data;
}

// Dependency analysis
export async function analyzeDependencies(projectPath) {
  const response = await api.post("/api/dependencies", {
    project_path: projectPath,
  });

  return response.data;
}

// Change impact analysis
export async function analyzeImpact(projectPath, changedFile) {
  const response = await api.post("/api/impact", {
    project_path: projectPath,
    changed_file: changedFile,
  });

  return response.data;
}

// Bug detection
export async function detectBugs(projectPath) {
  const response = await api.post("/api/bugs", {
    project_path: projectPath,
  });

  return response.data;
}

// Preview a recommended bug fix
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

// Generate a fix recommendation
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

// Generate a safe, read-only patch candidate
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

// Validate proposed code syntax and optionally run tests
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

// Preview patch application without modifying the source file
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

// Apply a patch only when the user explicitly approves it
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

// Roll back an applied patch using its patch ID
export async function rollbackPatch(projectPath, patchId) {
  const response = await api.post("/api/bugs/rollback-patch", {
    project_path: projectPath,
    patch_id: patchId,
  });

  return response.data;
}

// Retrieve patch history for a project
export async function getPatchHistory(projectPath) {
  const response = await api.post("/api/bugs/patch-history", {
    project_path: projectPath,
  });

  return response.data;
}
