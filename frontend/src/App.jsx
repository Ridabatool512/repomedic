
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
  FolderGit2,
} from "lucide-react";

import BugDetectionPanel from "./components/BugDetectionPanel";
import DependencyExplorer from "./components/DependencyExplorer";

import {
  analyzeDependencies,
  analyzeImpact,
  scanProject,
  importGitHubRepository,
} from "./services/api";

import "./App.css";

const DEFAULT_PROJECT =
  "C:\\Users\\Rida Batool\\repomedic\\workspace\\demo-project";

const STORAGE_KEY = "repomedic-imported-repositories";

function getSavedRepositories() {
  try {
    const saved = JSON.parse(
      localStorage.getItem(STORAGE_KEY) || "[]"
    );

    return Array.isArray(saved)
      ? saved.filter(
          (repo) =>
            repo &&
            typeof repo.project_path === "string" &&
            typeof repo.repository_url === "string"
        )
      : [];
  } catch {
    return [];
  }
}

function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || JSON.stringify(item))
      .join(", ");
  }

  if (error?.code === "ECONNABORTED") {
    return "The request timed out. Try again with a smaller project.";
  }

  if (!error?.response) {
    return "Could not connect to the RepoMedic API. Make sure the backend is running at http://127.0.0.1:8000.";
  }

  return error?.message || "Something went wrong. Try again.";
}

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
  const [repositories, setRepositories] = useState(getSavedRepositories);
  const [githubUrl, setGithubUrl] = useState("");

  const [scan, setScan] = useState(null);
  const [dependencies, setDependencies] = useState(null);
  const [impact, setImpact] = useState(null);
  const [changedFile, setChangedFile] = useState("");

  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function resetAnalysis() {
    setScan(null);
    setDependencies(null);
    setImpact(null);
    setChangedFile("");
  }

  function selectProject(path) {
    if (!path || path === projectPath) {
      return;
    }

    setProjectPath(path);
    resetAnalysis();
    setError("");
    setNotice(
      "Project selected. Run a scan when you're ready."
    );
  }

  function handleProjectPathInput(value) {
    setProjectPath(value);
    resetAnalysis();
    setError("");
    setNotice("");
  }

  async function runAction(action, task) {
    setLoading(action);
    setError("");
    setNotice("");

    try {
      await task();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function handleImportGitHub() {
    const url = githubUrl.trim();

    if (!url) {
      setError("Enter a public GitHub repository URL first.");
      return;
    }

    return runAction("github", async () => {
      const result = await importGitHubRepository(url);

      const imported = {
        owner: result.owner,
        repository: result.repository,
        repository_url: result.repository_url,
        project_path: result.project_path,
      };

      const updated = [
        imported,
        ...repositories.filter(
          (repo) =>
            repo.project_path !== imported.project_path
        ),
      ];

      setRepositories(updated);

      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify(updated)
        );
      } catch {
        // The imported repository remains available this session.
      }

      setGithubUrl("");
      setProjectPath(imported.project_path);
      resetAnalysis();

      setNotice(
        `Successfully imported ${imported.owner}/${imported.repository}. Run a scan to analyze it.`
      );
    });
  }

  async function handleScan() {
    const path = projectPath.trim();

    if (!path) {
      setError("Enter a project folder path first.");
      return;
    }

    return runAction("scan", async () => {
      const result = await scanProject(path);

      setScan(result);
      setDependencies(null);
      setImpact(null);
      setChangedFile("");

      setNotice("Scan finished.");
    });
  }

  async function handleDependencies() {
    const path = projectPath.trim();

    if (!path) {
      setError("Enter a project folder path first.");
      return;
    }

    return runAction("dependencies", async () => {
      const result = await analyzeDependencies(path);

      setDependencies(result);
      setNotice(
        "Dependency check finished."
      );
    });
  }

  async function handleImpact(fileToAnalyze = changedFile) {
    const file = fileToAnalyze.trim();
    const path = projectPath.trim();

    if (!file) {
      setError(
        "Select a file in the dependency graph or enter a project-relative path."
      );
      return;
    }

    if (!path) {
      setError("Enter a project folder path first.");
      return;
    }

    setChangedFile(file);

    return runAction("impact", async () => {
      const result = await analyzeImpact(path, file);

      setImpact(result);
      setNotice(
        `Checked what may be affected by ${file}.`
      );
    });
  }

  function handleFileSelection(file) {
    setChangedFile(file);
    setImpact(null);
    setError("");

    setNotice(
      `Selected ${file}. Click Analyze change impact to inspect its dependents.`
    );
  }

  const summary = scan?.summary ?? {};
  const syntaxErrors = summary.syntax_errors ?? 0;
  const pythonFiles = summary.python_files ?? 0;

  const graphEdges = dependencies
    ? Object.values(dependencies.dependencies ?? {}).reduce(
        (total, items) =>
          total + (Array.isArray(items) ? items.length : 0),
        0
      )
    : 0;

  const affectedFiles =
    impact?.affected_files ?? impact?.impacted_files ?? [];

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
    impact?.risk_level ?? impact?.risk ?? "Analysis complete";

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
          Find bugs
        </a>

        <a className="nav-link" href="#dependencies">
          <GitBranch size={18} />
          Dependencies
        </a>

        <a className="nav-link" href="#impact">
          <ShieldCheck size={18} />
          Change effects
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
              Tools for your project
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
            <div className="hero-copy">
              <div className="eyebrow">
                <span className="hero-live-dot" />
                REPO OVERVIEW
              </div>

              <h1>
                Check your code
              </h1>

              <p>
                Scan Python files, check imports, and see which files may be affected by a change.
              </p>
              <div className="hero-meta">
                <span><Code2 size={14} /> Python files</span>
                <span><GitBranch size={14} /> File connections</span>
                <span><ShieldCheck size={14} /> Change impact</span>
              </div>
            </div>
            <div className="hero-visual" aria-label="Illustration of connected project files">
              <div className="hero-visual-top">
                <span><span className="hero-live-dot" /> DEPENDENCY MAP</span>
                <span className="hero-visual-count">03 FILES</span>
              </div>
              <div className="dependency-mini-map">
                <svg className="dependency-lines" viewBox="0 0 250 148" fill="none" aria-hidden="true">
                  <path className="dependency-line line-a" d="M125 42 V65 H57 V86" />
                  <path className="dependency-line line-b" d="M125 65 H193 V86" />
                  <circle cx="125" cy="65" r="3" fill="#f07a88" />
                </svg>
                <div className="mini-file mini-file-main">
                  <FileCode2 size={16} />
                  <span><strong>main.py</strong><small>entry point</small></span>
                  <i />
                </div>
                <div className="mini-file mini-file-left">
                  <Code2 size={15} />
                  <span><strong>parser.py</strong><small>dependency</small></span>
                </div>
                <div className="mini-file mini-file-right">
                  <ShieldCheck size={15} />
                  <span><strong>checks.py</strong><small>dependent</small></span>
                </div>
              </div>
              <div className="hero-visual-footer">
                <span className="hero-scan-bar"><i /></span>
                <span>Following imports<span className="hero-ellipsis">...</span></span>
              </div>
            </div>
          </section>

          <section className="project-panel">
            <div className="panel-heading">
              <div className="section-icon">
                <Layers3 size={19} />
              </div>

              <div>
                <h2>Select a project</h2>
                <p>
                  Choose the demo project or import a GitHub repository.
                </p>
              </div>
            </div>

            <label
              className="field-label"
              htmlFor="project-selector"
            >
              PROJECT
            </label>

            <select
              id="project-selector"
              className="full-input"
              value={projectPath}
              onChange={(event) =>
                selectProject(event.target.value)
              }
              disabled={Boolean(loading)}
            >
              <option value={DEFAULT_PROJECT}>
                Demo project
              </option>

              {repositories.map((repo) => (
                <option
                  key={repo.project_path}
                  value={repo.project_path}
                >
                  {repo.owner}/{repo.repository}
                </option>
              ))}
            </select>

            <label
              className="field-label"
              htmlFor="project-path"
            >
              PROJECT FOLDER
            </label>

            <div className="project-input-row">
              <input
                id="project-path"
                value={projectPath}
                onChange={(event) =>
                  handleProjectPathInput(event.target.value)
                }
                placeholder="Absolute path to your project folder"
                disabled={Boolean(loading)}
              />

              <button
                type="button"
                className="primary-button"
                onClick={handleScan}
                disabled={
                  Boolean(loading) || !projectPath.trim()
                }
              >
                {loading === "scan" ? (
                  <LoaderCircle
                    className="spin"
                    size={17}
                  />
                ) : (
                  <Play size={16} />
                )}

                {loading === "scan" ? "Scanning..." : "Run scan"}
              </button>
            </div>

            <div className="path-hint">
              <ShieldCheck size={14} />
              Scans run against the project folder you select.
            </div>

            <div className="github-import-section">
              <div className="github-import-heading">
                <GitBranch size={20} />

                <div>
                  <h3>Import from GitHub</h3>
                  <p>
                    Enter a public repository link.
                  </p>
                </div>
              </div>

              <label
                className="field-label"
                htmlFor="github-repository-url"
              >
                GITHUB URL
              </label>

              <div className="project-input-row">
                <input
                  id="github-repository-url"
                  type="url"
                  value={githubUrl}
                  onChange={(event) =>
                    setGithubUrl(event.target.value)
                  }
                  placeholder="https://github.com/owner/repository"
                  disabled={Boolean(loading)}
                />

                <button
                  type="button"
                  className="primary-button"
                  onClick={handleImportGitHub}
                  disabled={
                    Boolean(loading) || !githubUrl.trim()
                  }
                >
                  {loading === "github" ? (
                    <LoaderCircle
                      className="spin"
                      size={17}
                    />
                  ) : (
                    <FolderGit2 size={17} />
                  )}

                  {loading === "github"
                    ? "Importing..."
                    : "Import repository"}
                </button>
              </div>

              <p className="input-hint">
                Public repositories only. The code is copied locally; import does not run its scripts.
              </p>

              {repositories.length > 0 && (
                <div className="imported-repositories">
                  <strong>Imported repositories</strong>

                  {repositories.map((repo) => (
                    <div
                      className="file-row"
                      key={repo.project_path}
                    >
                      <GitBranch size={15} />

                      <span>
                        {repo.owner}/{repo.repository}
                      </span>

                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          selectProject(repo.project_path)
                        }
                        disabled={Boolean(loading)}
                      >
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {error && (
              <div
                className="message error-message"
                role="alert"
              >
                <AlertTriangle size={17} />
                <span>{error}</span>
              </div>
            )}

            {notice && (
              <div
                className="message success-message"
                role="status"
              >
                <CheckCircle2 size={17} />
                <span>{notice}</span>
              </div>
            )}
          </section>

          <div className="section-title-row">
            <div>
              <h2>Overview</h2>
              <p>Results from your last scan</p>
            </div>

            <span
              className={`scan-badge ${
                scan ? "scan-complete" : ""
              }`}
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
              value={
                scan ? (summary.functions ?? "—") : "—"
              }
              detail="Functions detected"
            />

            <StatCard
              icon={GitBranch}
              label="Imports"
              value={
                scan ? (summary.imports ?? "—") : "—"
              }
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

          <section
            className="bug-detection-section"
            id="bugs"
          >
            <BugDetectionPanel
              selectedProjectPath={projectPath}
              onProjectPathChange={handleProjectPathInput}
            />
          </section>

          <section className="analysis-grid">
            <article className="panel" id="dependencies">
              <div className="panel-heading">
                <div className="section-icon purple">
                  <GitBranch size={19} />
                </div>

                <div>
                  <h2>File dependencies</h2>
                  <p>
                    See which files import other files and check for circular imports.
                  </p>
                </div>
              </div>

              <div className="result-row">
                <div>
                  <span className="result-number">
                    {dependencies ? graphEdges : "—"}
                  </span>

                  <span className="result-label">
                    Connections
                  </span>
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleDependencies}
                  disabled={
                    Boolean(loading) || !projectPath.trim()
                  }
                >
                  {loading === "dependencies" ? (
                    <LoaderCircle
                      className="spin"
                      size={16}
                    />
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
                    Estimate which files may be affected by a
                    code change.
                  </p>
                </div>
              </div>

              <label
                className="field-label"
                htmlFor="changed-file"
              >
                CHANGED FILE
              </label>

              <input
                className="full-input"
                id="changed-file"
                value={changedFile}
                onChange={(event) =>
                  setChangedFile(event.target.value)
                }
                placeholder="e.g. bug_demo.py"
              />

              <p className="input-hint">
                Use a path relative to the selected project root.
                You can select a file in the dependency graph above.
              </p>

              <button
                type="button"
                className="impact-button"
                onClick={() => handleImpact(changedFile)}
                disabled={
                  Boolean(loading) || !projectPath.trim()
                }
              >
                {loading === "impact" ? (
                  <LoaderCircle
                    className="spin"
                    size={16}
                  />
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

                  <div className="risk-level">
                    {riskLabel}
                  </div>

                  <div className="affected-heading">
                    Potentially affected files (
                    {affectedFiles.length})
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
                      No affected-file list was returned. Check
                      the complete response below.
                    </p>
                  )}

                  <details className="result-details">
                    <summary>
                      View complete impact report
                    </summary>

                    <pre>
                      {JSON.stringify(impact, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </article>
          </section>

          <footer className="footer">
            <span>
              <Code2 size={15} />
              RepoMedic{" "}
              <span className="footer-muted">v0.2.0</span>
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
