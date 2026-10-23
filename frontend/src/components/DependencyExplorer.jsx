
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  FileCode2,
  GitBranch,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import "./DependencyExplorer.css";

function Metric({ label, value, icon: Icon }) {
  return (
    <div className="dep-metric">
      <span className="dep-metric-icon">
        <Icon size={18} />
      </span>
      <span className="dep-metric-label">{label}</span>
      <strong>{value ?? 0}</strong>
    </div>
  );
}

export default function DependencyExplorer({
  data,
  onRefresh,
  loading = false,
  onSelectFile,
}) {
  const [selectedFile, setSelectedFile] = useState("");
  const [search, setSearch] = useState("");
  const [view, setView] = useState("graph");

  function selectFile(file) {
    setSelectedFile(file);

    if (typeof onSelectFile === "function") {
      onSelectFile(file);
    }
  }

  const graph = useMemo(() => {
    const raw = data?.dependencies ?? data?.edges ?? {};
    const dependencies = {};
    const dependents = {};

    if (Array.isArray(raw)) {
      for (const edge of raw) {
        if (!edge || typeof edge !== "object") continue;

        const source = edge.source ?? edge.from ?? edge.file;
        const target = edge.target ?? edge.to ?? edge.dependency;

        if (
          typeof source !== "string" ||
          typeof target !== "string"
        ) {
          continue;
        }

        dependencies[source] ??= [];
        dependencies[source].push(target);
      }
    } else if (raw && typeof raw === "object") {
      for (const [file, items] of Object.entries(raw)) {
        dependencies[file] = Array.isArray(items)
          ? items.filter((item) => typeof item === "string")
          : [];
      }
    }

    for (const [file, items] of Object.entries(dependencies)) {
      dependents[file] ??= [];

      for (const dependency of items) {
        dependents[dependency] ??= [];
        dependents[dependency].push(file);
      }
    }

    // Prefer the backend's reverse dependency graph when provided.
    if (data?.dependents && typeof data.dependents === "object") {
      for (const [file, items] of Object.entries(data.dependents)) {
        dependents[file] = Array.isArray(items)
          ? items.filter((item) => typeof item === "string")
          : [];
      }
    }

    const files = [
      ...new Set([
        ...Object.keys(dependencies),
        ...Object.keys(dependents),
        ...Object.values(dependencies).flat(),
      ]),
    ].sort();

    for (const file of files) {
      dependencies[file] ??= [];
      dependents[file] ??= [];

      dependencies[file] = [...new Set(dependencies[file])].sort();
      dependents[file] = [...new Set(dependents[file])].sort();
    }

    return { files, dependencies, dependents };
  }, [data]);

  const selected =
    selectedFile && graph.files.includes(selectedFile)
      ? selectedFile
      : graph.files[0] ?? "";

  const summary = data?.summary ?? {};

  const cycles = Array.isArray(data?.circular_dependencies)
    ? data.circular_dependencies
    : [];

  const parseErrors = Array.isArray(data?.parse_errors)
    ? data.parse_errors
    : [];

  const edgeCount = Object.values(graph.dependencies).reduce(
    (total, items) => total + items.length,
    0,
  );

  const filteredFiles = graph.files.filter((file) =>
    file.toLowerCase().includes(search.toLowerCase()),
  );

  const mostDependedOn = Array.isArray(data?.most_depended_on)
    ? data.most_depended_on
    : graph.files
        .map((file) => ({
          file,
          dependent_count: graph.dependents[file]?.length ?? 0,
        }))
        .sort((a, b) => b.dependent_count - a.dependent_count);

  const graphNodes = useMemo(() => {
    const files = graph.files;
    const width = 640;
    const height = Math.max(280, files.length * 62);
    const centerX = width / 2;
    const centerY = height / 2;
    const radiusX = Math.max(150, width * 0.36);
    const radiusY = Math.max(95, height * 0.39);

    return {
      width,
      height,
      nodes: files.map((file, index) => {
        const angle =
          (2 * Math.PI * index) / Math.max(files.length, 1) -
          Math.PI / 2;

        return {
          file,
          x:
            files.length === 1
              ? centerX
              : centerX + radiusX * Math.cos(angle),
          y:
            files.length === 1
              ? centerY
              : centerY + radiusY * Math.sin(angle),
        };
      }),
    };
  }, [graph.files]);

  const nodeByFile = Object.fromEntries(
    graphNodes.nodes.map((node) => [node.file, node]),
  );

  return (
    <div className="dependency-explorer">
      <div className="dep-header">
        <div>
          <div className="dep-eyebrow">
            <Network size={14} />
            CODE RELATIONSHIPS
          </div>

          <h3>Dependency map</h3>

          <p>
            Explore internal imports and estimate which modules are connected.
          </p>
        </div>

        {onRefresh && (
          <button
            type="button"
            className="dep-refresh"
            onClick={onRefresh}
            disabled={loading}
          >
            <RefreshCw
              size={15}
              className={loading ? "dep-spin" : ""}
            />
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </div>

      <div className="dep-metrics">
        <Metric
          icon={FileCode2}
          label="Python files"
          value={summary.python_files ?? graph.files.length}
        />

        <Metric
          icon={GitBranch}
          label="Connections"
          value={summary.dependency_edges ?? edgeCount}
        />

        <Metric
          icon={ArrowDownRight}
          label="Files with dependencies"
          value={
            summary.files_with_dependencies ??
            Object.values(graph.dependencies).filter(
              (items) => items.length > 0,
            ).length
          }
        />

        <Metric
          icon={AlertTriangle}
          label="Circular cycles"
          value={summary.circular_dependencies ?? cycles.length}
        />
      </div>

      {cycles.length > 0 ? (
        <div className="dep-alert">
          <ShieldAlert size={19} />

          <div>
            <strong>Circular dependencies detected</strong>

            {cycles.map((cycle, index) => (
              <p key={`${index}-${JSON.stringify(cycle)}`}>
                {Array.isArray(cycle)
                  ? cycle.join(" → ")
                  : String(cycle)}
              </p>
            ))}
          </div>
        </div>
      ) : (
        <div className="dep-ok">
          <CheckCircle2 size={17} />
          No circular dependencies were reported by the analyzer.
        </div>
      )}

      {parseErrors.length > 0 && (
        <div className="dep-alert">
          <AlertTriangle size={18} />

          <div>
            <strong>
              {parseErrors.length} file(s) could not be parsed
            </strong>

            {parseErrors.map((item, index) => (
              <p key={`${item.file ?? "file"}-${index}`}>
                {item.file ?? "Unknown file"}
                {item.line ? `:${item.line}` : ""}
                {" — "}
                {item.message ?? "Unknown parsing error"}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="dep-toolbar">
        <div className="dep-search">
          <Search size={16} />

          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search project files..."
            aria-label="Search project files"
          />
        </div>

        <div className="dep-tabs">
          <button
            type="button"
            className={view === "graph" ? "selected" : ""}
            onClick={() => setView("graph")}
          >
            <Network size={15} />
            Graph
          </button>

          <button
            type="button"
            className={view === "files" ? "selected" : ""}
            onClick={() => setView("files")}
          >
            <FileCode2 size={15} />
            Files
          </button>
        </div>
      </div>

      {graph.files.length === 0 ? (
        <div className="dep-empty">
          <Network size={28} />
          <strong>No dependency data yet</strong>
          <p>
            Run dependency analysis to display Python file relationships.
          </p>
        </div>
      ) : (
        <div className="dep-layout">
          <div className="dep-main">
            {view === "graph" ? (
              <div className="dep-graph-wrap">
                <svg
                  className="dep-svg"
                  viewBox={`0 0 ${graphNodes.width} ${graphNodes.height}`}
                  role="img"
                  aria-label="Python file dependency graph. Arrows point from a file to its dependency."
                >
                  <defs>
                    <marker
                      id="dep-arrow"
                      markerWidth="8"
                      markerHeight="8"
                      refX="6"
                      refY="3"
                      orient="auto"
                    >
                      <path
                        d="M0,0 L0,6 L6,3 z"
                        fill="currentColor"
                      />
                    </marker>
                  </defs>

                  {graph.files.flatMap((source) =>
                    graph.dependencies[source].map((target) => {
                      const from = nodeByFile[source];
                      const to = nodeByFile[target];

                      if (!from || !to) return null;

                      return (
                        <line
                          key={`${source}-${target}`}
                          x1={from.x}
                          y1={from.y}
                          x2={to.x}
                          y2={to.y}
                          className="dep-edge"
                          markerEnd="url(#dep-arrow)"
                        />
                      );
                    }),
                  )}

                  {graphNodes.nodes.map((node) => {
                    const active = selected === node.file;

                    return (
                      <g
                        key={node.file}
                        className={`dep-node ${active ? "active" : ""}`}
                        role="button"
                        tabIndex={0}
                        aria-label={`Select ${node.file} for inspection and change-impact analysis`}
                        onClick={() => selectFile(node.file)}
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" ||
                            event.key === " "
                          ) {
                            event.preventDefault();
                            selectFile(node.file);
                          }
                        }}
                      >
                        <rect
                          x={node.x - 70}
                          y={node.y - 21}
                          width="140"
                          height="42"
                          rx="10"
                        />

                        <text
                          x={node.x}
                          y={node.y + 4}
                          textAnchor="middle"
                        >
                          {node.file.length > 19
                            ? `…${node.file.slice(-18)}`
                            : node.file}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                <div className="dep-graph-legend">
                  <span>
                    <i className="dep-legend-line" />
                    Imports / depends on
                  </span>

                  <span>
                    <i className="dep-legend-node" />
                    Select a file to inspect it
                  </span>
                </div>
              </div>
            ) : (
              <div className="dep-file-list">
                {filteredFiles.map((file) => (
                  <button
                    type="button"
                    key={file}
                    className={`dep-file-item ${
                      selected === file ? "active" : ""
                    }`}
                    onClick={() => selectFile(file)}
                  >
                    <FileCode2 size={16} />
                    <span>{file}</span>
                    <small>
                      {graph.dependencies[file].length} dependencies
                    </small>
                  </button>
                ))}

                {filteredFiles.length === 0 && (
                  <p className="dep-muted">No matching files.</p>
                )}
              </div>
            )}
          </div>

          <aside className="dep-details">
            <div className="dep-details-heading">
              <CircleDot size={17} />
              <span>SELECTED FILE</span>
            </div>

            <strong className="dep-selected-name">
              {selected || "No file selected"}
            </strong>

            <div className="dep-count-row">
              <span>Depends on</span>
              <strong>
                {graph.dependencies[selected]?.length ?? 0}
              </strong>
            </div>

            {graph.dependencies[selected]?.length ? (
              graph.dependencies[selected].map((file) => (
                <button
                  type="button"
                  key={file}
                  className="dep-related"
                  onClick={() => selectFile(file)}
                >
                  <ArrowRight size={14} />
                  {file}
                </button>
              ))
            ) : (
              <p className="dep-muted">
                No internal dependencies detected.
              </p>
            )}

            <div className="dep-count-row dep-count-spaced">
              <span>Used by</span>
              <strong>
                {graph.dependents[selected]?.length ?? 0}
              </strong>
            </div>

            {graph.dependents[selected]?.length ? (
              graph.dependents[selected].map((file) => (
                <button
                  type="button"
                  key={file}
                  className="dep-related"
                  onClick={() => selectFile(file)}
                >
                  <ArrowRight size={14} />
                  {file}
                </button>
              ))
            ) : (
              <p className="dep-muted">
                No dependent files detected.
              </p>
            )}

            <div className="dep-count-row dep-count-spaced">
              <span>Impact depth</span>
              <strong>
                {graph.dependents[selected]?.length ? "Direct" : "Low"}
              </strong>
            </div>

            <p className="dep-note">
              “Used by” shows direct reverse dependencies. It is not a
              guarantee of runtime impact.
            </p>

            {selected && (
              <button
                type="button"
                className="dep-refresh"
                onClick={() => selectFile(selected)}
                disabled={loading}
              >
                <ShieldAlert size={15} />
                Use for change impact
              </button>
            )}
          </aside>
        </div>
      )}

      <div className="dep-bottom-grid">
        <section className="dep-bottom-card">
          <h4>
            <GitBranch size={16} />
            Most depended-on files
          </h4>

          {mostDependedOn.slice(0, 5).map((item) => (
            <button
              type="button"
              key={item.file}
              className="dep-ranking-row"
              onClick={() => selectFile(item.file)}
            >
              <span>{item.file}</span>
              <strong>{item.dependent_count ?? 0}</strong>
            </button>
          ))}
        </section>

        <section className="dep-bottom-card">
          <h4>
            <AlertTriangle size={16} />
            Analysis notes
          </h4>

          <p>
            Only statically discovered internal Python imports are represented.
          </p>

          <p>
            Dynamic imports, runtime plugin loading, and conditional import
            behavior may not appear.
          </p>

          <p>
            Use Change Impact for a separate estimate of affected files.
          </p>
        </section>
      </div>

      <div className="dep-footer">
        <span>
          {graph.files.length} files · {edgeCount} directed connections
        </span>

        <span>Arrow direction: source → dependency</span>
      </div>
    </div>
  );
}
