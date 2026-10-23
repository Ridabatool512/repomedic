
import ast
from pathlib import Path
from collections import defaultdict, deque

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
}


def build_dependency_graph(project_path: str) -> dict:
    """Build a local Python import graph and analyze its relationships."""

    root = Path(project_path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Project path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Expected a directory: {root}")

    python_files = {}

    for path in root.rglob("*.py"):
        relative = path.relative_to(root)

        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue

        if any(part.startswith(".") for part in relative.parts):
            continue

        module = _path_to_module(relative)

        if module:
            python_files[module] = relative.as_posix()

    module_to_path = {
        module: path
        for module, path in python_files.items()
        if not path.endswith("/__init__.py")
        and path != "__init__.py"
    }

    graph = {path: [] for path in sorted(module_to_path.values())}
    parse_errors = []
    unresolved_imports = []

    for module, relative_path in module_to_path.items():
        source_path = root / relative_path

        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(source_path))
        except SyntaxError as exc:
            parse_errors.append({
                "file": relative_path,
                "line": exc.lineno,
                "message": exc.msg,
            })
            continue
        except (OSError, UnicodeError) as exc:
            parse_errors.append({
                "file": relative_path,
                "line": None,
                "message": str(exc),
            })
            continue

        imported_modules = set()
        package = _package_for_module(module, relative_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import_from(
                    package=package,
                    module=node.module,
                    level=node.level,
                )

                if base:
                    imported_modules.add(base)

                    # `from package import module` can refer to a
                    # submodule even when the imported name is not
                    # explicitly present in node.module.
                    for alias in node.names:
                        if alias.name != "*":
                            imported_modules.add(f"{base}.{alias.name}")

        dependencies = set()

        for imported in imported_modules:
            matched = False

            for candidate_module, candidate_path in module_to_path.items():
                if candidate_path == relative_path:
                    continue

                if (
                    imported == candidate_module
                    or imported.startswith(candidate_module + ".")
                    or candidate_module.startswith(imported + ".")
                ):
                    dependencies.add(candidate_path)
                    matched = True

            if not matched and not _is_relative_or_local_import(
                imported, module_to_path
            ):
                # External or standard-library imports are intentionally
                # not treated as internal file dependencies.
                pass

        graph[relative_path] = sorted(dependencies)

    dependents = {path: [] for path in graph}

    for source, dependencies in graph.items():
        for dependency in dependencies:
            dependents[dependency].append(source)

    for paths in dependents.values():
        paths.sort()

    cycles = _find_cycles(graph)
    dependency_chains = {
        path: _dependency_chain(path, graph)
        for path in graph
    }

    files_with_dependencies = sum(bool(items) for items in graph.values())
    files_with_dependents = sum(bool(items) for items in dependents.values())
    edge_count = sum(len(items) for items in graph.values())

    most_depended_on = sorted(
        (
            {"file": path, "dependent_count": len(items)}
            for path, items in dependents.items()
        ),
        key=lambda item: (-item["dependent_count"], item["file"]),
    )

    most_dependencies = sorted(
        (
            {"file": path, "dependency_count": len(items)}
            for path, items in graph.items()
        ),
        key=lambda item: (-item["dependency_count"], item["file"]),
    )

    return {
        "project_path": str(root),
        "summary": {
            "python_files": len(graph),
            "dependency_edges": edge_count,
            "files_with_dependencies": files_with_dependencies,
            "files_with_dependents": files_with_dependents,
            "circular_dependencies": len(cycles),
            "files_with_parse_errors": len(parse_errors),
        },
        # Preserve these original fields for the current frontend.
        "dependencies": graph,
        "dependents": dependents,
        # Additional analysis for future UI improvements.
        "circular_dependencies": cycles,
        "dependency_chains": dependency_chains,
        "most_depended_on": most_depended_on,
        "most_dependencies": most_dependencies,
        "parse_errors": parse_errors,
        "unresolved_imports": unresolved_imports,
    }


def _path_to_module(relative_path: Path) -> str | None:
    """Convert a Python file path into a likely module name."""

    if relative_path.suffix != ".py":
        return None

    parts = list(relative_path.with_suffix("").parts)

    if parts[-1] == "__init__":
        parts.pop()

    if not parts or not all(part.isidentifier() for part in parts):
        return None

    return ".".join(parts)


def _package_for_module(module: str, relative_path: str) -> str:
    """Return the package context used to resolve relative imports."""

    if relative_path.endswith("/__init__.py") or relative_path == "__init__.py":
        return module

    return module.rpartition(".")[0]


def _resolve_import_from(package: str, module: str | None, level: int) -> str:
    """Resolve absolute and relative imports to a module name."""

    if level == 0:
        return module or ""

    parts = package.split(".") if package else []

    # One leading dot means the current package. Two means its parent.
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]

    if module:
        parts.extend(module.split("."))

    return ".".join(part for part in parts if part)


def _is_relative_or_local_import(
    imported: str,
    module_to_path: dict[str, str],
) -> bool:
    """Check whether an import appears to refer to a project module."""

    return any(
        imported == module
        or imported.startswith(module + ".")
        or module.startswith(imported + ".")
        for module in module_to_path
    )



def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Find cyclic groups of files using Tarjan's SCC algorithm.

    Each returned group represents one strongly connected component.
    A component is cyclic if it contains multiple nodes or a self-loop.
    The existing API response format remains a list of file paths.
    """

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def strong_connect(node: str) -> None:
        nonlocal index

        indices[node] = index
        lowlinks[node] = index
        index += 1

        stack.append(node)
        on_stack.add(node)

        for neighbor in sorted(graph.get(node, [])):
            if neighbor not in graph:
                continue

            if neighbor not in indices:
                strong_connect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            component = []

            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)

                if member == node:
                    break

            component.sort()

            has_self_loop = (
                len(component) == 1
                and component[0] in graph.get(component[0], [])
            )

            if len(component) > 1 or has_self_loop:
                cycles.append(component + [component[0]])

    for node in sorted(graph):
        if node not in indices:
            strong_connect(node)

    return sorted(cycles)


def _dependency_chain(
    start: str,
    graph: dict[str, list[str]],
    max_depth: int = 5,
) -> list[str]:
    """Return a simple breadth-first traversal of downstream dependencies."""

    queue = deque([(start, 0)])
    visited = {start}
    result = []

    while queue:
        node, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for dependency in graph.get(node, []):
            if dependency not in visited:
                visited.add(dependency)
                result.append(dependency)
                queue.append((dependency, depth + 1))

    return result
