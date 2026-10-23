
import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Code2,
  FileCode2,
  GitBranch,
  Layers3,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import BugDetectionPanel from "./components/BugDetectionPanel";
import DependencyExplorer from "./components/DependencyExplorer";

import {
  analyzeDependencies,
  analyzeImpact,
  scanProject,
} from "./services/api";

import "./App.css";

const DEFAULT_PROJECT =
  "C:\\Users\\Rida Batool\\repomedic\\workspace\\demo-project";

function StatCard({ icon: Icon, label, value, detail }) {
  return (
    <article className="stat-card">
      <div className="stat-top">
        <span className="stat-icon">
          <Icon size={19} />
        </span>
        <span className="stat-label">{label}</span>
      </div>

      <div className="stat-value">{value ?? "—"}</div>
      <p className="stat-detail">{detail}</p>
    </article>
  );
}

function App() {
  const [projectPath, setProjectPath] = useState(DEFAULT_PROJECT);
  const [scan, setScan] = useState(null);
  const [dependencies, setDependencies] = useState(null);
  const [impact, setImpact] = useState(null);
  const [changedFile, setChangedFile] = useState("");
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function runAction(action, task) {
    setLoading(action);
    setError("");
    setNotice("");

    try {
      await task();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Something went wrong. Check that the API is running.",
      );
    } finally {
      setLoading("");
    }
  }

  async function handleScan() {
    if (!projectPath.trim()) {
      setError("Enter a project folder path first.");
      return;
    }

    return runAction("scan", async () => {
      const result = await scanProject(projectPath.trim());

      setScan(result);
      setDependencies(null);
      setImpact(null);
      setChangedFile("");

      setNotice("Project scan completed successfully.");
    });
  }

  async function handleDependencies() {
    if (!projectPath.trim()) {
      setError("Enter a project folder path first.");
      return;
    }

    return runAction("dependencies", async () => {
      const result = await analyzeDependencies(projectPath.trim());

      setDependencies(result);
      setNotice("Dependency analysis completed successfully.");
    });
  }

  async function handleImpact(fileToAnalyze = changedFile) {
    const file = fileToAnalyze.trim();

    if (!file) {
      setError(
        "Select a file in the dependency graph or enter a project-relative path.",
      );
      return;
    }

    if (!projectPath.trim()) {
      setError("Enter a project folder path first.");
      return;
    }

    setChangedFile(file);

    return runAction("impact", async () => {
      const result = await analyzeImpact(projectPath.trim(), file);

      setImpact(result);
      setNotice(`Change-impact analysis completed for ${file}.`);
    });
  }

  function handleFileSelection(file) {
    setChangedFile(file);
    setImpact(null);
    setError("");
    setNotice(
      `Selected ${file}. Click Analyze change impact to inspect its dependents.`,
    );
  }

  const summary = scan?.summary ?? {};

  const syntaxErrors = summary.syntax_errors ?? 0;
  const pythonFiles = summary.python_files ?? 0;

  const graphEdges = dependencies
    ? Object.values(dependencies.dependencies ?? {}).reduce(
        (total, items) =>
          total + (Array.isArray(items) ? items.length : 0),
        0,
      )
    : 0;

  const affectedFiles =
    impact?.affected_files ??
    impact?.impacted_files ??
    [];

  const riskScore = impact?.risk_score ?? impact?.score;

  const numericRisk = Number(riskScore);

  const hasRiskScore =
    riskScore !== undefined &&
    riskScore !== null &&
    Number.isFinite(numericRisk);

  const clampedRisk = hasRiskScore
    ? Math.min(100, Math.max(0, numericRisk))
    : 0;

  const riskLabel =
    impact?.risk_level ??
    impact?.risk ??
    "Analysis complete";

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview">
          <span className="brand-mark">
            <Code2 size={23} />
          </span>

          <span>
            Repo<span className="brand-accent">Medic</span>
          </span>
        </a>

        <div className="workspace-label">WORKSPACE</div>

        <a className="nav-link active" href="#overview">
          <Activity size={18} />
          Overview
        </a>

        <a className="nav-link" href="#bugs">
          <AlertTriangle size={18} />
          Smart Bug Detection
        </a>

        <a className="nav-link" href="#dependencies">
          <GitBranch size={18} />
          Dependencies
        </a>

        <a className="nav-link" href="#impact">
          <ShieldCheck size={18} />
          Change impact
        </a>

        <div className="sidebar-bottom">
          <div className="api-status">
            <span className="status-dot" />

            <div>
              <strong>Local API</strong>
              <small>127.0.0.1:8000</small>
            </div>
          </div>

          <div className="sidebar-note">
            <Sparkles size={16} />
            <span>
              Understand your codebase with confidence.
            </span>
          </div>
        </div>
      </aside>

      <section className="main-area" id="overview">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <span>/</span> Overview
          </div>

          <div className="topbar-badge">
            <span className="status-dot" />
            Local environment
          </div>
        </header>

        <div className="content">
          <section className="hero">
            <div>
              <div className="eyebrow">
                <Sparkles size={14} />
                CODEBASE INTELLIGENCE
              </div>

              <h1>
                Know your code.
                <br />
                <span>Change it with confidence.</span>
              </h1>

              <p>
                Scan Python projects, explore dependencies, and estimate
                the impact of code changes.
              </p>
            </div>

            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />

              <div className="hero-code">
                <Code2 size={52} strokeWidth={1.2} />
              </div>

              <span className="orbit-node node-one">
                <GitBranch size={17} />
              </span>

              <span className="orbit-node node-two">
                <Boxes size={17} />
              </span>

              <span className="orbit-node node-three">
                <ShieldCheck size={17} />
              </span>
            </div>
          </section>

          <section className="project-panel">
            <div className="panel-heading">
              <div className="section-icon">
                <Layers3 size={19} />
              </div>

              <div>
                <h2>Project workspace</h2>
                <p>
                  Choose a project folder inside your configured workspace.
                </p>
              </div>
            </div>

            <label className="field-label" htmlFor="project-path">
              PROJECT PATH
            </label>

            <div className="project-input-row">
              <input
                id="project-path"
                value={projectPath}
                onChange={(event) => setProjectPath(event.target.value)}
                placeholder="Absolute path to your project folder"
              />

              <button
                type="button"
                className="primary-button"
                onClick={handleScan}
                disabled={Boolean(loading) || !projectPath.trim()}
              >
                {loading === "scan" ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Play size={16} />
                )}

                {loading === "scan" ? "Scanning..." : "Run scan"}
              </button>
            </div>

            <div className="path-hint">
              <ShieldCheck size={14} />
              Local scanning is restricted to your workspace.
            </div>

            {error && (
              <div className="message error-message" role="alert">
                <AlertTriangle size={17} />
                <span>{error}</span>
              </div>
            )}

            {notice && (
              <div className="message success-message" role="status">
                <CheckCircle2 size={17} />
                <span>{notice}</span>
              </div>
            )}
          </section>

          <div className="section-title-row">
            <div>
              <h2>Project overview</h2>
              <p>Insights from your latest scan</p>
            </div>

            <span
              className={`scan-badge ${scan ? "scan-complete" : ""}`}
            >
              <span className="status-dot" />
              {scan ? "Scan complete" : "Awaiting scan"}
            </span>
          </div>

          <section className="stats-grid">
            <StatCard
              icon={FileCode2}
              label="Python files"
              value={scan ? pythonFiles : "—"}
              detail="Files discovered"
            />

            <StatCard
              icon={Code2}
              label="Functions"
              value={scan ? (summary.functions ?? "—") : "—"}
              detail="Functions detected"
            />

            <StatCard
              icon={GitBranch}
              label="Imports"
              value={scan ? (summary.imports ?? "—") : "—"}
              detail="Import statements"
            />

            <StatCard
              icon={AlertTriangle}
              label="Syntax errors"
              value={scan ? syntaxErrors : "—"}
              detail={
                scan
                  ? syntaxErrors
                    ? "Needs attention"
                    : "No syntax errors found"
                  : "Run a scan to check"
              }
            />
          </section>

          <section className="bug-detection-section" id="bugs">
            <BugDetectionPanel />
          </section>

          <section className="analysis-grid">
            <article className="panel" id="dependencies">
              <div className="panel-heading">
                <div className="section-icon purple">
                  <GitBranch size={19} />
                </div>

                <div>
                  <h2>Dependency explorer</h2>
                  <p>
                    Explore connections, dependency chains, and circular
                    imports between project files.
                  </p>
                </div>
              </div>

              <div className="result-row">
                <div>
                  <span className="result-number">
                    {dependencies ? graphEdges : "—"}
                  </span>

                  <span className="result-label">
                    Detected connections
                  </span>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleDependencies}
                  disabled={Boolean(loading) || !projectPath.trim()}
                >
                  {loading === "dependencies" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <GitBranch size={16} />
                  )}

                  {loading === "dependencies"
                    ? "Analyzing..."
                    : "Analyze dependencies"}

                  {loading !== "dependencies" && (
                    <ArrowRight size={15} />
                  )}
                </button>
              </div>

              {dependencies && (
                <DependencyExplorer
                  data={dependencies}
                  onRefresh={handleDependencies}
                  loading={loading === "dependencies"}
                  onSelectFile={handleFileSelection}
                />
              )}
            </article>

            <article className="panel" id="impact">
              <div className="panel-heading">
                <div className="section-icon green">
                  <ShieldCheck size={19} />
                </div>

                <div>
                  <h2>Change impact</h2>
                  <p>
                    Estimate which files may be affected by a code change.
                  </p>
                </div>
              </div>

              <label className="field-label" htmlFor="changed-file">
                CHANGED FILE
              </label>

              <input
                className="full-input"
                id="changed-file"
                value={changedFile}
                onChange={(event) => setChangedFile(event.target.value)}
                placeholder="e.g. bug_demo.py"
              />

              <p className="input-hint">
                Use a path relative to the selected project root. You can
                select a file in the dependency graph above.
              </p>

              <button
                type="button"
                className="impact-button"
                onClick={() => handleImpact(changedFile)}
                disabled={Boolean(loading) || !projectPath.trim()}
              >
                {loading === "impact" ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <ShieldCheck size={16} />
                )}

                {loading === "impact"
                  ? "Analyzing impact..."
                  : "Analyze change impact"}
              </button>

              {impact && (
                <div className="impact-results">
                  <div className="risk-heading">
                    <span>Estimated risk</span>

                    <strong>
                      {hasRiskScore ? numericRisk : "—"}
                      {hasRiskScore ? "/100" : ""}
                    </strong>
                  </div>

                  <div
                    className="risk-track"
                    role="progressbar"
                    aria-label="Estimated change risk"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={clampedRisk}
                  >
                    <div
                      style={{ width: `${clampedRisk}%` }}
                    />
                  </div>

                  <div className="risk-level">{riskLabel}</div>

                  <div className="affected-heading">
                    Potentially affected files ({affectedFiles.length})
                  </div>

                  {affectedFiles.length > 0 ? (
                    affectedFiles.map((file, index) => (
                      <div
                        className="file-row"
                        key={
                          typeof file === "string"
                            ? file
                            : file.path ?? file.file ?? index
                        }
                      >
                        <FileCode2 size={15} />

                        <span>
                          {typeof file === "string"
                            ? file
                            : file.path ??
                              file.file ??
                              JSON.stringify(file)}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="input-hint">
                      No affected-file list was returned. Check the
                      complete response below.
                    </p>
                  )}

                  <details className="result-details">
                    <summary>View complete impact report</summary>
                    <pre>{JSON.stringify(impact, null, 2)}</pre>
                  </details>
                </div>
              )}
            </article>
          </section>

          <footer className="footer">
            <span>
              <Code2 size={15} />
              RepoMedic <span className="footer-muted">v0.1.0</span>
            </span>

            <span>
              Built for developers who care about safe changes.
            </span>
          </footer>
        </div>
      </section>
    </main>
  );
}

export default App;
