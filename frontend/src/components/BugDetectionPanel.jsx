
import { useState, useCallback, useEffect } from "react";
import {
  AlertTriangle,
  Bug,
  CheckCircle2,
  ChevronDown,
  FileCode2,
  LoaderCircle,
  ShieldCheck,
  WandSparkles,
  Copy,
  RotateCcw,
  Eye,
} from "lucide-react";

import {
  detectBugs,
  recommendFix,
  safePatchPreview,
  validatePatch,
  previewApplication,
  applyApprovedPatch,
  rollbackPatch,
} from "../services/api";

import FixPreview from "./FixPreview";
import PatchHistory from "./PatchHistory";
import "./BugDetectionPanel.css";

const DEFAULT_PROJECT =
  "C:\\Users\\Rida Batool\\repomedic\\workspace\\demo-project";

function getErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg ?? JSON.stringify(item))
      .join(", ");
  }

  return error?.message || fallback;
}

function SeverityCard({ label, count }) {
  return (
    <div className="bug-severity-card">
      <span>{label}</span>
      <strong>{count ?? 0}</strong>
    </div>
  );
}

function CodeSection({ title, code, className = "" }) {
  if (!code) return null;

  return (
    <div className={`bug-code-section ${className}`}>
      <div className="bug-code-section-heading">
        <strong>{title}</strong>

        <button
          type="button"
          className="bug-copy-button"
          onClick={() => navigator.clipboard?.writeText(code)}
          title={`Copy ${title.toLowerCase()}`}
        >
          <Copy size={14} />
          Copy
        </button>
      </div>

      <pre>
        <code>{code}</code>
      </pre>
    </div>
  );
}

function RecommendationPanel({ result }) {
  if (!result) return null;

  return (
    <div className="bug-ai-result">
      <div className="bug-ai-result-heading">
        <div className="bug-ai-icon">
          <WandSparkles size={18} />
        </div>

        <div>
          <strong>{result.title ?? "Suggested fix"}</strong>
          <p>
            Checked with local rules
            {result.confidence ? ` · ${result.confidence}` : ""}
          </p>
        </div>
      </div>

      {result.explanation && (
        <div className="bug-ai-section">
          <strong>What's wrong</strong>
          <p>{result.explanation}</p>
        </div>
      )}

      {result.recommendation && (
        <div className="bug-ai-section">
          <strong>One way to fix it</strong>
          <p>{result.recommendation}</p>
        </div>
      )}

      <CodeSection title="Original code" code={result.original_code} />

      {Array.isArray(result.context) && result.context.length > 0 && (
        <CodeSection
          title="Source context"
          code={result.context
            .map(
              (item) =>
                `${item.line}${item.is_target ? "  →" : "   "} ${item.code}`
            )
            .join("\n")}
        />
      )}

      <CodeSection title="Proposed code" code={result.proposed_code} />

      <div className="bug-ai-safety">
        <ShieldCheck size={17} />

        <div>
          <strong>
            {result.read_only
              ? "Your files haven't been changed"
              : "Check the changes before applying"}
          </strong>

          <p>
            {result.patch_available
              ? "There's a patch you can review."
              : "No patch was prepared. Review the suggestion and make the change yourself, then test it."}
          </p>

          {result.needs_manual_review && (
            <p>Manual review is required before changing the code.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function SafePatchPanel({ result }) {
  if (!result) return null;

  return (
    <div className="bug-safe-patch-result">
      <div className="bug-safe-patch-heading">
        <ShieldCheck size={19} />

        <div>
          <strong>
            {result.patch_available
              ? "Patch ready to review"
              : "Couldn't prepare a patch"}
          </strong>

          <p>
            {result.file ?? "File not specified"}
            {result.line != null ? ` · Line ${result.line}` : ""}
          </p>
        </div>
      </div>

      {result.note && (
        <p className="bug-safe-patch-note">{result.note}</p>
      )}

      <CodeSection title="Proposed diff" code={result.diff} />
      <CodeSection title="Proposed code" code={result.proposed_code} />

      <div className="bug-safe-patch-warning">
        <AlertTriangle size={17} />

        <span>
          This preview does not modify your source files. Review and validate
          proposed changes before applying them.
        </span>
      </div>
    </div>
  );
}

function PatchValidationPanel({
  findingKey,
  patch,
  result,
  error,
  loading,
  onValidate,
}) {
  if (!patch?.patch_available || !patch?.proposed_code || !patch?.file) {
    return null;
  }

  const validationPassed =
    result?.syntax_valid === true &&
    (!result?.tests_run || result?.tests_passed === true);

  return (
    <div className="bug-patch-validation">
      <div className="bug-section-heading">
        <div>
          <h4>Validation checks</h4>
          <p>Check this code before applying it.</p>
        </div>

        {result && (
          <span
            className={`bug-status-pill ${
              validationPassed ? "success" : "danger"
            }`}
          >
            {validationPassed ? "Checks passed" : "Needs a look"}
          </span>
        )}
      </div>

      <div className="bug-patch-validation-actions">
        <button
          type="button"
          disabled={loading}
          onClick={() => onValidate(findingKey, patch, false)}
        >
          {loading ? (
            <LoaderCircle className="bug-spin" size={17} />
          ) : (
            <CheckCircle2 size={17} />
          )}
          Check syntax
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => onValidate(findingKey, patch, true)}
        >
          {loading ? (
            <LoaderCircle className="bug-spin" size={17} />
          ) : (
            <ShieldCheck size={17} />
          )}
          Test a temporary copy
        </button>
      </div>

      {error && (
        <div className="bug-message bug-error">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="bug-validation-grid">
          <div className="bug-validation-item">
            <span>Python syntax</span>

            <strong
              className={result.syntax_valid ? "is-success" : "is-danger"}
            >
              {result.syntax_valid ? "Passed" : "Failed"}
            </strong>
          </div>

          <div className="bug-validation-item">
            <span>Test execution</span>

            <strong
              className={
                !result.tests_run
                  ? ""
                  : result.tests_passed
                    ? "is-success"
                    : "is-danger"
              }
            >
              {!result.tests_run
                ? "Not run"
                : result.tests_passed
                  ? "Passed"
                  : "Failed"}
            </strong>
          </div>
        </div>
      )}

      {result?.note && (
        <p className="bug-validation-note">{result.note}</p>
      )}

      {result?.error && (
        <CodeSection title="Validation error" code={result.error} />
      )}

      {result?.test_output && (
        <CodeSection title="Test output" code={result.test_output} />
      )}
    </div>
  );
}

function PatchManagementPanel({
  projectPath,
  patch,
  validation,
  onPatchHistoryChange,
}) {
  const [preview, setPreview] = useState(null);
  const [patchId, setPatchId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [approved, setApproved] = useState(false);



  const patchReady = Boolean(
    patch?.patch_available &&
      patch?.file &&
      typeof patch?.proposed_code === "string" &&
      patch.proposed_code.trim()
  );

  const validationPassed =
    validation?.syntax_valid === true &&
    (!validation?.tests_run || validation?.tests_passed === true);

  async function handlePreview() {
    if (!patchReady) {
      setError("Generate an available safe patch first.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");
    setPreview(null);
    setApproved(false);
    setPatchId("");

    try {
      const result = await previewApplication(
        projectPath,
        patch.file,
        patch.proposed_code
      );

      setPreview(result);

      setMessage(
        result.changed
          ? "Preview ready. Your source file has not been changed."
          : "The proposed code matches the current file. No changes are needed."
      );
    } catch (err) {
      setError(getErrorMessage(err, "Could not preview this patch."));
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    if (!preview?.changed) {
      setError("Generate a changed patch preview first.");
      return;
    }

    if (!validationPassed) {
      setError("Pass syntax validation before applying this patch.");
      return;
    }

    if (!approved) {
      setError("Review the changes and check the approval box first.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const result = await applyApprovedPatch(
        projectPath,
        patch.file,
        patch.proposed_code,
        approved
      );

      const appliedPatchId = result.patch_id ?? "";

      setPatchId(appliedPatchId);
      setMessage(
        `Patch applied successfully. Backup: ${
          result.backup_file ?? "Check the backend response."
        }`
      );

      setPreview(null);
      setApproved(false);

      await onPatchHistoryChange();
    } catch (err) {
      setError(getErrorMessage(err, "Could not apply the patch."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRollback() {
    if (!patchId) return;

    const confirmed = window.confirm(
      `Restore the original version of ${patch?.file ?? "this file"}?`
    );

    if (!confirmed) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const result = await rollbackPatch(projectPath, patchId);

      setMessage(result.message ?? "Rollback completed.");
      setPatchId("");
      setPreview(null);
      setApproved(false);

      await onPatchHistoryChange();
    } catch (err) {
      setError(getErrorMessage(err, "Rollback failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="bug-patch-management">
      <div className="bug-section-heading">
        <div className="bug-patch-title">
          <div className="bug-ai-icon">
            <ShieldCheck size={18} />
          </div>

          <div>
            <h4>Patch management</h4>
            <p>Preview, validate, approve, and safely manage changes.</p>
          </div>
        </div>

        <span className="bug-status-pill">
          {patchId ? "Patch applied" : "Approval required"}
        </span>
      </div>

      {!patchReady ? (
        <p className="bug-muted">
          Generate a safe patch for this finding to enable application preview,
          validation checks, and approved patch management.
        </p>
      ) : (
        <>
          <div className="bug-patch-file">
            <FileCode2 size={17} />
            <span>{patch.file}</span>
          </div>

          <div className="bug-patch-step">
            <span className="bug-step-number">1</span>

            <div>
              <strong>Review the application preview</strong>
              <p>
                Confirm exactly what will change. Previewing does not edit your
                source file.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="bug-action-button secondary"
            disabled={busy}
            onClick={handlePreview}
          >
            {busy ? (
              <LoaderCircle className="bug-spin" size={17} />
            ) : (
              <Eye size={17} />
            )}
            {busy ? "Preparing preview..." : "Preview Application"}
          </button>

          {preview && (
            <div className="bug-application-preview">
              <div className="bug-application-preview-heading">
                <div>
                  <strong>Application preview</strong>
                  <p>Review the diff before approving the change.</p>
                </div>

                <span
                  className={`bug-status-pill ${
                    preview.changed ? "warning" : "success"
                  }`}
                >
                  {preview.changed ? "Changes detected" : "No changes"}
                </span>
              </div>

              {preview.diff ? (
                <CodeSection
                  title="Before and after · Unified diff"
                  code={preview.diff}
                  className="bug-diff-code"
                />
              ) : (
                <p className="bug-muted">
                  No diff was returned by the server.
                </p>
              )}

              <div className="bug-preview-facts">
                <span>
                  <strong>Changed:</strong>{" "}
                  {preview.changed ? "Yes" : "No"}
                </span>

                <span>
                  <strong>Applied:</strong>{" "}
                  {preview.applied ? "Yes" : "No"}
                </span>

                <span>
                  <strong>Read-only:</strong>{" "}
                  {preview.read_only ? "Yes" : "No"}
                </span>
              </div>
            </div>
          )}

          <div className="bug-patch-step">
            <span className="bug-step-number">2</span>

            <div>
              <strong>Pass validation</strong>
              <p>
                Syntax must pass. If tests have been run, they must pass too.
              </p>
            </div>
          </div>

          <div
            className={`bug-validation-gate ${
              validationPassed ? "passed" : "pending"
            }`}
          >
            {validationPassed ? (
              <CheckCircle2 size={18} />
            ) : (
              <AlertTriangle size={18} />
            )}

            <span>
              {validationPassed
                ? "Required validation checks passed."
                : "Validation is incomplete or unsuccessful. Use the validation controls above."}
            </span>
          </div>

          <div className="bug-patch-step">
            <span className="bug-step-number">3</span>

            <div>
              <strong>Explicit approval</strong>
              <p>You must personally approve the exact proposed changes.</p>
            </div>
          </div>

          <label className="bug-approval-check">
            <input
              type="checkbox"
              checked={approved}
              disabled={
                busy ||
                !preview?.changed ||
                !validationPassed ||
                Boolean(patchId)
              }
              onChange={(event) => setApproved(event.target.checked)}
            />

            <span>
              <strong>I reviewed and approve this patch.</strong>
              <small>
                I understand that this will modify the source file. I have
                reviewed the diff and validation results.
              </small>
            </span>
          </label>

          <div className="bug-patch-validation-actions bug-patch-final-actions">
            <button
              type="button"
              className="bug-action-button primary"
              disabled={
                busy ||
                !preview?.changed ||
                !validationPassed ||
                !approved ||
                Boolean(patchId)
              }
              onClick={handleApply}
            >
              {busy ? (
                <LoaderCircle className="bug-spin" size={17} />
              ) : (
                <ShieldCheck size={17} />
              )}
              Apply Approved Patch
            </button>

            <button
              type="button"
              className="bug-action-button danger"
              disabled={busy || !patchId}
              onClick={handleRollback}
            >
              {busy ? (
                <LoaderCircle className="bug-spin" size={17} />
              ) : (
                <RotateCcw size={17} />
              )}
              Roll Back
            </button>
          </div>

          {patchId && (
            <div className="bug-patch-id">
              <div>
                <span>Patch ID</span>
                <code>{patchId}</code>
              </div>

              <button
                type="button"
                className="bug-copy-button"
                onClick={() => navigator.clipboard?.writeText(patchId)}
              >
                <Copy size={14} />
                Copy ID
              </button>
            </div>
          )}
        </>
      )}

      {message && (
        <div className="bug-message bug-success-message">
          <CheckCircle2 size={17} />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="bug-message bug-error">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}

export default function BugDetectionPanel({
  selectedProjectPath,
  onProjectPathChange,
}) {
  const [internalProjectPath, setInternalProjectPath] =
    useState(DEFAULT_PROJECT);

  const projectPath = selectedProjectPath ?? internalProjectPath;

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const [severityFilter, setSeverityFilter] = useState("all");
  const [contextFilter, setContextFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [findingSearch, setFindingSearch] = useState("");

  const [recommendations, setRecommendations] = useState({});
  const [recommendationErrors, setRecommendationErrors] = useState({});
  const [recommendationLoading, setRecommendationLoading] = useState({});

  const [safePatches, setSafePatches] = useState({});
  const [safePatchErrors, setSafePatchErrors] = useState({});
  const [safePatchLoading, setSafePatchLoading] = useState({});

  const [validationResults, setValidationResults] = useState({});
  const [validationErrors, setValidationErrors] = useState({});
  const [validationLoading, setValidationLoading] = useState({});

  useEffect(() => {
    setReport(null);
    setError("");
    setRecommendations({});
    setRecommendationErrors({});
    setRecommendationLoading({});
    setSafePatches({});
    setSafePatchErrors({});
    setSafePatchLoading({});
    setValidationResults({});
    setValidationErrors({});
    setValidationLoading({});
    setSeverityFilter("all");
    setContextFilter("all");
    setCategoryFilter("all");
    setFindingSearch("");
  }, [projectPath]);

  const refreshPatchHistory = useCallback(async () => {
    setHistoryRefreshKey((current) => current + 1);
  }, []);

  function handleProjectPathChange(value) {
    if (onProjectPathChange) {
      onProjectPathChange(value);
    } else {
      setInternalProjectPath(value);
    }
  }

  async function handleDetect() {
    if (!projectPath.trim()) {
      setError("Enter a project folder path first.");
      return;
    }

    setLoading(true);
    setError("");
    setReport(null);
    setRecommendations({});
    setRecommendationErrors({});
    setRecommendationLoading({});
    setSafePatches({});
    setSafePatchErrors({});
    setSafePatchLoading({});
    setValidationResults({});
    setValidationErrors({});
    setValidationLoading({});

    try {
      const result = await detectBugs(projectPath.trim());
      setReport(result);
    } catch (err) {
      setError(
        getErrorMessage(err, "Bug detection failed. Check the backend.")
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleRecommendFix(finding, findingKey) {
    setRecommendationLoading((current) => ({
      ...current,
      [findingKey]: true,
    }));

    setRecommendationErrors((current) => ({
      ...current,
      [findingKey]: "",
    }));

    try {
      const result = await recommendFix(projectPath.trim(), finding);

      setRecommendations((current) => ({
        ...current,
        [findingKey]: result,
      }));
    } catch (err) {
      setRecommendationErrors((current) => ({
        ...current,
        [findingKey]: getErrorMessage(
          err,
          "Could not generate a recommendation."
        ),
      }));
    } finally {
      setRecommendationLoading((current) => ({
        ...current,
        [findingKey]: false,
      }));
    }
  }

  async function handleSafePatch(finding, findingKey) {
    setSafePatchLoading((current) => ({
      ...current,
      [findingKey]: true,
    }));

    setSafePatchErrors((current) => ({
      ...current,
      [findingKey]: "",
    }));

    setValidationResults((current) => ({
      ...current,
      [findingKey]: undefined,
    }));

    setValidationErrors((current) => ({
      ...current,
      [findingKey]: "",
    }));

    try {
      const result = await safePatchPreview(projectPath.trim(), finding);

      setSafePatches((current) => ({
        ...current,
        [findingKey]: result,
      }));
    } catch (err) {
      setSafePatchErrors((current) => ({
        ...current,
        [findingKey]: getErrorMessage(
          err,
          "Could not generate a safe patch preview."
        ),
      }));
    } finally {
      setSafePatchLoading((current) => ({
        ...current,
        [findingKey]: false,
      }));
    }
  }

  async function handleValidatePatch(findingKey, patch, runTests = false) {
    if (!patch?.proposed_code || !patch?.file) {
      setValidationErrors((current) => ({
        ...current,
        [findingKey]: "Generate an available safe patch preview first.",
      }));
      return;
    }

    setValidationLoading((current) => ({
      ...current,
      [findingKey]: true,
    }));

    setValidationErrors((current) => ({
      ...current,
      [findingKey]: "",
    }));

    setValidationResults((current) => ({
      ...current,
      [findingKey]: undefined,
    }));

    try {
      const result = await validatePatch(
        projectPath.trim(),
        patch.file,
        patch.proposed_code,
        runTests
      );

      setValidationResults((current) => ({
        ...current,
        [findingKey]: result,
      }));
    } catch (err) {
      setValidationErrors((current) => ({
        ...current,
        [findingKey]: getErrorMessage(err, "Patch validation failed."),
      }));
    } finally {
      setValidationLoading((current) => ({
        ...current,
        [findingKey]: false,
      }));
    }
  }

  const counts = report?.severity_counts ?? {};
  const findings = report?.findings ?? [];
  const contextCounts = report?.context_counts ?? {};
  const categoryCounts = report?.category_counts ?? {};

  const filteredFindings = findings.filter((finding) => {
    const severity = String(finding.severity ?? "info").toLowerCase();
    const context = finding.file_context ?? "unknown";
    const category = finding.category ?? "unknown";

    const searchText = [
      finding.title,
      finding.message,
      finding.description,
      finding.rule_id,
      finding.rule,
      finding.file,
      finding.path,
      finding.suggestion,
      finding.recommendation,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return (
      (severityFilter === "all" || severity === severityFilter) &&
      (contextFilter === "all" || context === contextFilter) &&
      (categoryFilter === "all" || category === categoryFilter) &&
      searchText.includes(findingSearch.trim().toLowerCase())
    );
  });

  return (
    <section className="bug-panel" id="bug-detection">
      <div className="bug-panel-heading">
        <div className="bug-panel-icon">
          <Bug size={21} />
        </div>

        <div>
          <h2>Find bugs</h2>
          <p>
            Detect suspicious Python patterns, security risks, and syntax
            errors in your project.
          </p>
        </div>
      </div>

      <label className="bug-field-label" htmlFor="bug-project-path">
        PROJECT PATH
      </label>

      <div className="bug-input-row">
        <input
          id="bug-project-path"
          value={projectPath}
          onChange={(event) => handleProjectPathChange(event.target.value)}
          placeholder="Absolute path to your project folder"
        />

        <button
          type="button"
          onClick={handleDetect}
          disabled={loading || !projectPath.trim()}
        >
          {loading ? (
            <LoaderCircle className="bug-spin" size={17} />
          ) : (
            <ShieldCheck size={17} />
          )}
          {loading ? "Analyzing..." : "Detect bugs"}
        </button>
      </div>

      {error && (
        <div className="bug-message bug-error">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}

      {report && (
        <>
          <div className="bug-report-banner">
            <CheckCircle2 size={18} />
            <span>
              Analysis complete — {report.files_analyzed ?? 0} Python files
              analyzed.
            </span>
          </div>

          <div className="bug-summary-grid">
            <div className="bug-summary-card">
              <span>Total findings</span>
              <strong>{report.total_findings ?? findings.length}</strong>
            </div>

            <div className="bug-summary-card">
              <span>Syntax errors</span>
              <strong>{report.syntax_errors ?? 0}</strong>
            </div>
          </div>

          <h3 className="bug-subheading">Severity breakdown</h3>

          <div className="bug-severity-grid">
            <SeverityCard label="Critical" count={counts.critical} />
            <SeverityCard label="High" count={counts.high} />
            <SeverityCard label="Medium" count={counts.medium} />
            <SeverityCard label="Low" count={counts.low} />
          </div>

          <h3 className="bug-subheading">Finding context</h3>

          <div className="bug-summary-grid">
            <div className="bug-summary-card">
              <span>Production files</span>
              <strong>{contextCounts.production ?? 0}</strong>
            </div>

            <div className="bug-summary-card">
              <span>Test files</span>
              <strong>{contextCounts.test ?? 0}</strong>
            </div>

            <div className="bug-summary-card">
              <span>Security category</span>
              <strong>{categoryCounts.security ?? 0}</strong>
            </div>

            <div className="bug-summary-card">
              <span>Code quality</span>
              <strong>{categoryCounts.code_quality ?? 0}</strong>
            </div>
          </div>

          <p className="bug-muted">
            Categories are broad rule classifications, not confirmed
            vulnerability counts. Review each finding in context.
          </p>

          <div className="bug-findings-heading">
            <div>
              <h3 className="bug-subheading">Detected issues</h3>
              <p>
                Expand an issue to inspect its source, request recommendations,
                and preview and validate safe patches.
              </p>
            </div>

            <span className="bug-findings-count">{filteredFindings.length}</span>
          </div>

          <div className="bug-filters">
            <input
              type="search"
              value={findingSearch}
              onChange={(event) => setFindingSearch(event.target.value)}
              placeholder="Search rules, messages, or files..."
              aria-label="Search findings"
            />

            <select
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
              aria-label="Filter by severity"
            >
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>

            <select
              value={contextFilter}
              onChange={(event) => setContextFilter(event.target.value)}
              aria-label="Filter by file context"
            >
              <option value="all">All file contexts</option>
              <option value="production">Production</option>
              <option value="test">Tests</option>
              <option value="unknown">Unknown context</option>
            </select>

            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
              aria-label="Filter by category"
            >
              <option value="all">All categories</option>
              <option value="security">Security</option>
              <option value="code_quality">Code quality</option>
              <option value="unknown">Unknown category</option>
            </select>
          </div>

          <p className="bug-muted">
            Showing {filteredFindings.length} of {findings.length} findings.
          </p>

          {findings.length === 0 ? (
            <div className="bug-empty">
              <CheckCircle2 size={22} />
              <strong>No findings reported</strong>
              <p>No issues were detected by the configured analyzers.</p>
            </div>
          ) : filteredFindings.length === 0 ? (
            <div className="bug-empty">
              <CheckCircle2 size={22} />
              <strong>No matching findings</strong>
              <p>Try changing the filters or search text.</p>
            </div>
          ) : (
            <div className="bug-findings-list">
              {filteredFindings.map((finding, index) => {
                const severity = String(
                  finding.severity ?? "info"
                ).toLowerCase();

                const findingKey = [
                  finding.rule_id ?? finding.rule ?? "finding",
                  finding.file ?? finding.path ?? "",
                  finding.line ?? index,
                  index,
                ].join("-");

                return (
                  <details className="bug-finding" key={findingKey}>
                    <summary className="bug-finding-summary">
                      <span className="bug-finding-chevron">
                        <ChevronDown size={17} />
                      </span>

                      <span className="bug-finding-summary-content">
                        <span className="bug-finding-title-row">
                          <strong>
                            {finding.title ??
                              finding.message ??
                              finding.rule_id ??
                              "Potential issue"}
                          </strong>

                          <span
                            className={`bug-severity-badge ${severity}`}
                          >
                            {finding.severity ?? "Info"}
                          </span>
                        </span>

                        <span className="bug-finding-short-message">
                          {finding.message ??
                            finding.description ??
                            "No details provided."}
                        </span>

                        <span className="bug-finding-meta">
                          <span>
                            Rule: {finding.rule_id ?? finding.rule ?? "N/A"}
                          </span>

                          <span>
                            File: {finding.file ?? finding.path ?? "N/A"}
                          </span>

                          {finding.line != null && (
                            <span>Line: {finding.line}</span>
                          )}

                          <span>
                            Context: {finding.file_context ?? "unknown"}
                          </span>

                          <span>
                            Category: {finding.category ?? "unknown"}
                          </span>
                        </span>
                      </span>
                    </summary>

                    <div className="bug-finding-details">
                      {(finding.suggestion || finding.recommendation) && (
                        <div className="bug-recommendation">
                          <strong>Existing guidance</strong>
                          <p>
                            {finding.suggestion ?? finding.recommendation}
                          </p>
                        </div>
                      )}

                      <button
                        type="button"
                        className="bug-recommend-fix-button"
                        disabled={recommendationLoading[findingKey]}
                        onClick={() =>
                          handleRecommendFix(finding, findingKey)
                        }
                      >
                        {recommendationLoading[findingKey] ? (
                          <LoaderCircle
                            className="bug-spin"
                            size={17}
                          />
                        ) : (
                          <WandSparkles size={17} />
                        )}

                        {recommendationLoading[findingKey]
                          ? "Preparing recommendation..."
                          : recommendations[findingKey]
                            ? "Refresh recommendation"
                            : "Recommend fix"}
                      </button>

                      {recommendationErrors[findingKey] && (
                        <div className="bug-message bug-error">
                          <AlertTriangle size={17} />
                          <span>{recommendationErrors[findingKey]}</span>
                        </div>
                      )}

                      <RecommendationPanel
                        result={recommendations[findingKey]}
                      />

                      <button
                        type="button"
                        className="bug-safe-patch-button"
                        disabled={safePatchLoading[findingKey]}
                        onClick={() => handleSafePatch(finding, findingKey)}
                      >
                        {safePatchLoading[findingKey] ? (
                          <LoaderCircle
                            className="bug-spin"
                            size={17}
                          />
                        ) : (
                          <FileCode2 size={17} />
                        )}

                        {safePatchLoading[findingKey]
                          ? "Checking patch safety..."
                          : safePatches[findingKey]
                            ? "Refresh Safe Patch Preview"
                            : "Safe Patch Preview"}
                      </button>

                      {safePatchErrors[findingKey] && (
                        <div className="bug-message bug-error">
                          <AlertTriangle size={17} />
                          <span>{safePatchErrors[findingKey]}</span>
                        </div>
                      )}

                      <SafePatchPanel result={safePatches[findingKey]} />

                      <PatchValidationPanel
                        findingKey={findingKey}
                        patch={safePatches[findingKey]}
                        result={validationResults[findingKey]}
                        error={validationErrors[findingKey]}
                        loading={Boolean(validationLoading[findingKey])}
                        onValidate={handleValidatePatch}
                      />

                      <PatchManagementPanel
                        key={`${projectPath.trim()}-${findingKey}`}
                        projectPath={projectPath.trim()}
                        patch={safePatches[findingKey]}
                        validation={validationResults[findingKey]}
                        onPatchHistoryChange={refreshPatchHistory}
                      />

                      <FixPreview
                        projectPath={projectPath.trim()}
                        finding={finding}
                      />
                    </div>
                  </details>
                );
              })}
            </div>
          )}

          {report.tools && (
            <details className="bug-tools-details">
              <summary>Analyzer status</summary>
              <pre>{JSON.stringify(report.tools, null, 2)}</pre>
            </details>
          )}
        </>
      )}

      <PatchHistory
        key={`${projectPath.trim()}-${historyRefreshKey}`}
        projectPath={projectPath.trim()}
      />
    </section>
  );
}
