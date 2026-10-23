
import { useState } from "react";
import {
  Clipboard,
  Eye,
  LoaderCircle,
  ShieldAlert,
  ShieldCheck,
  FileCode2,
} from "lucide-react";
import { previewBugFix } from "../services/api";
import "./FixPreview.css";

function CodePanel({ title, icon: Icon, children, variant = "original" }) {
  return (
    <section className={`fix-code-panel ${variant}`}>
      <div className="fix-code-panel-heading">
        <div className="fix-code-panel-title">
          <Icon size={16} />
          <strong>{title}</strong>
        </div>
        <span className="fix-code-label">
          {variant === "proposed" ? "PROPOSED" : "READ ONLY"}
        </span>
      </div>
      <div className="fix-code-panel-content">{children}</div>
    </section>
  );
}

export default function FixPreview({ projectPath, finding }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function handlePreview() {
    setLoading(true);
    setError("");
    setResult(null);
    setCopied(false);

    try {
      const data = await previewBugFix(projectPath, finding);
      setResult(data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Could not generate the fix preview."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    const replacement = result?.preview?.replacement;
    if (!result?.preview?.supported || replacement == null) return;

    try {
      await navigator.clipboard.writeText(replacement);
      setCopied(true);
      setError("");
    } catch {
      setError("Clipboard access failed. Select and copy the code manually.");
    }
  }

  const preview = result?.preview;
  const canShowReplacement =
    result?.available &&
    preview?.supported &&
    preview.replacement != null;

  return (
    <div className="fix-preview">
      <button
        type="button"
        className="fix-preview-trigger"
        onClick={handlePreview}
        disabled={loading}
      >
        {loading ? (
          <LoaderCircle className="bug-spin" size={16} />
        ) : (
          <Eye size={16} />
        )}
        {loading ? "Preparing preview..." : "Preview fix"}
      </button>

      {error && <p className="fix-preview-error">{error}</p>}

      {result?.available && (
        <div className="fix-preview-result">
          <div className="fix-preview-header">
            <div>
              <span className="fix-preview-eyebrow">CODE REVIEW</span>
              <h3>Proposed fix</h3>
              <p>Review the suggested change before applying it yourself.</p>
            </div>

            <span
              className={`fix-risk-badge ${(result.risk || "unknown").toLowerCase()}`}
            >
              <ShieldAlert size={14} />
              {result.risk || "Unknown"} risk
            </span>
          </div>

          <div className="fix-preview-notice">
            <ShieldCheck size={19} />
            <div>
              <strong>Manual review required</strong>
              <p>{result.why}</p>
              {result.review_note && <p>{result.review_note}</p>}
            </div>
          </div>

          <div className="fix-code-comparison">
            <CodePanel title="Original context" icon={FileCode2}>
              <pre className="fix-code">
                {result.context?.length ? (
                  result.context.map((item) => (
                    <div
                      className={
                        item.is_target
                          ? "fix-code-line target"
                          : "fix-code-line"
                      }
                      key={item.line}
                    >
                      <span className="fix-line-number">{item.line}</span>
                      <code>{item.code || " "}</code>
                    </div>
                  ))
                ) : (
                  <code>No source context available.</code>
                )}
              </pre>
            </CodePanel>

            <CodePanel
              title={canShowReplacement ? "Suggested replacement" : "Fix guidance"}
              icon={canShowReplacement ? ShieldCheck : ShieldAlert}
              variant="proposed"
            >
              {canShowReplacement ? (
                <>
                  <pre className="fix-code fix-code-proposed">
                    <code>{preview.replacement}</code>
                  </pre>
                  {preview.note && (
                    <p className="fix-preview-note">{preview.note}</p>
                  )}
                  <button
                    type="button"
                    className="fix-copy-button"
                    onClick={handleCopy}
                  >
                    <Clipboard size={15} />
                    {copied ? "Copied to clipboard" : "Copy proposed code"}
                  </button>
                </>
              ) : (
                <div className="fix-preview-guidance">
                  <strong>No automatic replacement available</strong>
                  <p>
                    {preview?.note ||
                      "Review the finding and update the code manually."}
                  </p>
                  <p>
                    Use the original context above to identify the affected
                    code. Do not apply a suggested change without testing it.
                  </p>
                </div>
              )}
            </CodePanel>
          </div>

          <div className="fix-preview-footer">
            <ShieldCheck size={15} />
            <span>
              Read-only preview. RepoMedic has not modified your project files.
            </span>
          </div>
        </div>
      )}

      {result && !result.available && (
        <p className="fix-preview-error">
          {result.error || "Preview unavailable."}
        </p>
      )}
    </div>
  );
}
