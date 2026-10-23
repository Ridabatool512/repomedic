import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "https://repomedic-api-hyg8.onrender.com",
  // Allow large repository analyses (especially Bug Check) more time to finish.
  timeout: 180000,
  headers: {
    "Content-Type": "application/json",
  },
});

const REPOSITORIES_STORAGE_KEY = "repomedic-imported-repositories";
const MISSING_PROJECT_DETAIL = "Project directory does not exist.";

// If Render's free filesystem is reset, the browser still remembers the
// GitHub URL. Restore that repository once, then retry the original request.
// This shared helper covers scans, dependencies, impact, bug checks, and
// patch-related actions without weakening the backend's project-path checks.
async function postWithRepositoryRecovery(endpoint, payload) {
  try {
    const response = await api.post(endpoint, payload);
    return response.data;
  } catch (error) {
    const isMissingProject =
      error?.response?.status === 404 &&
      error?.response?.data?.detail === MISSING_PROJECT_DETAIL &&
      typeof payload?.project_path === "string";

    if (!isMissingProject) {
      throw error;
    }

    let savedRepositories = [];

    try {
      const parsed = JSON.parse(
        localStorage.getItem(REPOSITORIES_STORAGE_KEY) || "[]"
      );
      savedRepositories = Array.isArray(parsed) ? parsed : [];
    } catch {
      throw error;
    }

    const savedRepository = savedRepositories.find(
      (repo) =>
        repo &&
        repo.project_path === payload.project_path &&
        typeof repo.repository_url === "string" &&
        repo.repository_url.trim()
    );

    // Only imported GitHub repositories can be restored automatically.
    if (!savedRepository) {
      throw error;
    }

    // Call the import endpoint directly. Do not use this helper here, or
    // the recovery flow could recursively trigger itself.
    const importResponse = await api.post("/api/github/import", {
      repository_url: savedRepository.repository_url.trim(),
    });
    const restored = importResponse.data;

    if (!restored?.project_path) {
      throw error;
    }

    const updatedRepository = {
      ...savedRepository,
      ...restored,
    };

    const updatedRepositories = [
      updatedRepository,
      ...savedRepositories.filter(
        (repo) =>
          repo.project_path !== savedRepository.project_path &&
          repo.project_path !== restored.project_path
      ),
    ];

    try {
      localStorage.setItem(
        REPOSITORIES_STORAGE_KEY,
        JSON.stringify(updatedRepositories)
      );
    } catch {
      // The request can still be retried even if browser storage is full.
    }

    // Retry exactly once with the path returned by the backend importer.
    const retryPayload = {
      ...payload,
      project_path: restored.project_path,
    };
    const retryResponse = await api.post(endpoint, retryPayload);
    return retryResponse.data;
  }
}

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
  return postWithRepositoryRecovery("/api/scan", {
    project_path: projectPath,
  });
}

// ============================================================
// DEPENDENCY ANALYSIS
// ============================================================

export async function analyzeDependencies(projectPath) {
  return postWithRepositoryRecovery("/api/dependencies", {
    project_path: projectPath,
  });
}

// ============================================================
// CHANGE IMPACT ANALYSIS
// ============================================================

export async function analyzeImpact(projectPath, changedFile) {
  return postWithRepositoryRecovery("/api/impact", {
    project_path: projectPath,
    changed_file: changedFile,
  });
}

// ============================================================
// SMART BUG DETECTION
// ============================================================

export async function detectBugs(projectPath) {
  return postWithRepositoryRecovery("/api/bugs", {
    project_path: projectPath,
  });
}

// ============================================================
// BUG FIX PREVIEW
// ============================================================

export async function previewBugFix(projectPath, finding) {
  return postWithRepositoryRecovery("/api/bugs/fix-preview", {
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
}

// ============================================================
// FIX RECOMMENDATION
// ============================================================

export async function recommendFix(projectPath, finding) {
  return postWithRepositoryRecovery("/api/bugs/recommend-fix", {
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
}

// ============================================================
// SAFE PATCH PREVIEW
// ============================================================

export async function safePatchPreview(projectPath, finding) {
  return postWithRepositoryRecovery("/api/bugs/safe-patch", {
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
  return postWithRepositoryRecovery("/api/bugs/validate-patch", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
    run_tests: runTests,
  });
}

// ============================================================
// PATCH APPLICATION PREVIEW
// ============================================================

export async function previewApplication(
  projectPath,
  file,
  proposedCode
) {
  return postWithRepositoryRecovery("/api/bugs/patch-preview", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
  });
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
  return postWithRepositoryRecovery("/api/bugs/apply-patch", {
    project_path: projectPath,
    file,
    proposed_code: proposedCode,
    approved: approved === true,
  });
}

// ============================================================
// PATCH HISTORY
// ============================================================

export async function getPatchHistory(projectPath) {
  return postWithRepositoryRecovery("/api/bugs/patch-history", {
    project_path: projectPath,
  });
}

// ============================================================
// ROLL BACK AN APPLIED PATCH
// ============================================================

export async function rollbackPatch(projectPath, patchId) {
  return postWithRepositoryRecovery("/api/bugs/rollback-patch", {
    project_path: projectPath,
    patch_id: patchId,
  });
}
