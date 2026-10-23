
from collections import deque


def analyze_change_impact(
    dependency_report: dict,
    changed_file: str,
) -> dict:
    """Estimate the impact of changing a file in a dependency graph."""

    dependencies = dependency_report.get("dependencies", {})
    dependents = dependency_report.get("dependents", {})

    if changed_file not in dependencies:
        raise ValueError(
            f"File not found in dependency graph: {changed_file}"
        )

    impacted = []
    visited = {changed_file}
    queue = deque([(changed_file, 0)])

    while queue:
        current, depth = queue.popleft()

        if depth > 0:
            impacted.append(
                {
                    "file": current,
                    "distance": depth,
                }
            )

        for dependent in dependents.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                queue.append((dependent, depth + 1))

    impacted.sort(key=lambda item: (item["distance"], item["file"]))

    direct_count = sum(
        item["distance"] == 1 for item in impacted
    )
    indirect_count = sum(
        item["distance"] > 1 for item in impacted
    )

    # This is a heuristic, not a prediction of actual defects.
    risk_score = min(
        100,
        direct_count * 20 + indirect_count * 10,
    )

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "changed_file": changed_file,
        "directly_impacted_files": direct_count,
        "indirectly_impacted_files": indirect_count,
        "total_impacted_files": len(impacted),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "impacted_files": impacted,
    }
