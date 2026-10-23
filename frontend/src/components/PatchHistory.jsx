
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileCode2,
  History,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

import {
  getPatchHistory,
  rollbackPatch,
} from "../services/api";

import "./PatchHistory.css";

const DEFAULT_PROJECT =
  "C:\\Users\\Rida Batool\\repomedic\\workspace\\demo-project";

function errorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? "").join(", ");
  }

  return error?.message || "Something went wrong.";
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString();
}

function StatusBadge({ status }) {
  const normalized = (status || "unknown").toLowerCase();
  const rolledBack = normalized === "rolled_back";

  return (
    <span
      className={`patch-history-status ${
        rolledBack ? "is-rolled-back" : normalized === "applied"
          ? "is-applied"
          : "is-unknown"
      }`}
    >
      {rolledBack ? (
        <RotateCcw size={14} />
      ) : normalized === "applied" ? (
        <CheckCircle2 size={14} />
      ) : (
        <Clock3 size={14} />
      )}

      {normalized === "rolled_back"
        ? "Rolled back"
        : normalized === "applied"
          ? "Applied"
          : normalized.replaceAll("_", " ")}
    </span>
  );
}

export default function PatchHistory({
  projectPath = DEFAULT_PROJECT,
}) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadHistory = useCallback(async () => {
    if (!projectPath?.trim()) {
      setError("Enter a project path to view patch history.");
      return;
    }

    setLoading(true);
    setError("");
    setNotice("");

    try {
      const result = await getPatchHistory(projectPath.trim());
      setHistory(Array.isArray(result.patches) ? result.patches : []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [projectPath]);

  useEffect(() => {
    let cancelled = false;

    Promise.resolve().then(() => {
      if (!cancelled) {
        loadHistory();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loadHistory]);

  async function handleRollback(patch) {
    if (patch.status === "rolled_back") {
      setNotice("This patch was already rolled back.");
      return;
    }

    if (!patch.backup_exists) {
      setError("The backup file is missing, so this patch can't be rolled back.");
      return;
    }

    const confirmed = window.confirm(
      `Restore the original file?\n\n` +
      `File: ${patch.file}\n` +
      `Patch ID: ${patch.patch_id}\n\n` +
      "This restores the saved original file contents. Any later edits to " +
      "that file may be overwritten."
    );

    if (!confirmed) return;

    setRollingBack(patch.patch_id);
    setError("");
    setNotice("");

    try {
      const result = await rollbackPatch(
        projectPath.trim(),
        patch.patch_id
      );

      setNotice(
        result.message ||
        `Restored ${patch.file}.`
      );

      await loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRollingBack("");
    }
  }

  const appliedCount = history.filter(
    (patch) => patch.status === "applied"
  ).length;

  const rolledBackCount = history.filter(
    (patch) => patch.status === "rolled_back"
  ).length;

  return (
    <section className="patch-history-panel">
      <div className="patch-history-header">
        <div className="patch-history-heading">
          <div className="patch-history-icon">
            <History size={21} />
          </div>

          <div>
            <h2>Patch History</h2>
            <p>See earlier patches or restore a saved backup.</p>
          </div>
        </div>

        <button
          type="button"
          className="patch-history-refresh"
          onClick={loadHistory}
          disabled={loading || Boolean(rollingBack)}
        >
          {loading ? (
            <LoaderCircle className="patch-history-spin" size={16} />
          ) : (
            <RefreshCw size={16} />
          )}
          Refresh
        </button>
      </div>

      <div className="patch-history-project">
        <span>PROJECT</span>
        <code>{projectPath}</code>
      </div>

      <div className="patch-history-stats">
        <div>
          <span>Total patches</span>
          <strong>{history.length}</strong>
        </div>

        <div>
          <span>Applied</span>
          <strong>{appliedCount}</strong>
        </div>

        <div>
          <span>Rolled back</span>
          <strong>{rolledBackCount}</strong>
        </div>
      </div>

      {error && (
        <div className="patch-history-message is-error">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="patch-history-message is-success">
          <CheckCircle2 size={17} />
          <span>{notice}</span>
        </div>
      )}

      {loading && history.length === 0 ? (
        <div className="patch-history-empty">
          <LoaderCircle
            className="patch-history-spin"
            size={25}
          />
          <p>Loading patch history...</p>
        </div>
      ) : history.length === 0 ? (
        <div className="patch-history-empty">
          <History size={30} />
          <strong>No patches yet</strong>
          <p>
            Patch records will show up here after you apply a patch.
          </p>
        </div>
      ) : (
        <div className="patch-history-list">
          {history.map((patch) => (
            <article
              className="patch-history-item"
              key={patch.patch_id}
            >
              <div className="patch-history-item-top">
                <div className="patch-history-file">
                  <div className="patch-history-file-icon">
                    <FileCode2 size={19} />
                  </div>

                  <div>
                    <h3>{patch.file}</h3>
                    <p>{formatDate(patch.created_at)}</p>
                  </div>
                </div>

                <StatusBadge status={patch.status} />
              </div>

              <div className="patch-history-id">
                <span>PATCH ID</span>
                <code>{patch.patch_id}</code>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard
                      ?.writeText(patch.patch_id)
                      .catch(() => {
                        setError("Could not copy the patch ID.");
                      });
                  }}
                >
                  Copy ID
                </button>
              </div>

              <div className="patch-history-backup">
                <ShieldCheck size={17} />
                <div>
                  <strong>
                    {patch.backup_exists
                      ? "Backup saved"
                      : "Backup not found"}
                  </strong>
                  <p>{patch.backup_file || "No backup path recorded"}</p>
                </div>
              </div>

              {patch.rolled_back_at && (
                <p className="patch-history-rollback-date">
                  Restored: {formatDate(patch.rolled_back_at)}
                </p>
              )}

              <div className="patch-history-actions">
                <button
                  type="button"
                  className="patch-history-rollback"
                  disabled={
                    patch.status === "rolled_back" ||
                    !patch.backup_exists ||
                    Boolean(rollingBack)
                  }
                  onClick={() => handleRollback(patch)}
                >
                  {rollingBack === patch.patch_id ? (
                    <LoaderCircle
                      className="patch-history-spin"
                      size={16}
                    />
                  ) : (
                    <RotateCcw size={16} />
                  )}

                  {rollingBack === patch.patch_id
                    ? "Restoring..."
                    : patch.status === "rolled_back"
                      ? "Already rolled back"
                      : "Restore original"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
