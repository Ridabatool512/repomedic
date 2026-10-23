
import argparse
import json
from pathlib import Path

from app.analyzers.dependency_analyzer import build_dependency_graph
from app.analyzers.impact_analyzer import analyze_change_impact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate the impact of changing a Python file."
    )
    parser.add_argument(
        "project_path",
        help="Root folder of the Python project",
    )
    parser.add_argument(
        "changed_file",
        help="Project-relative file path, e.g. app/analyzers/python_analyzer.py",
    )
    args = parser.parse_args()

    graph = build_dependency_graph(args.project_path)
    report = analyze_change_impact(graph, args.changed_file)

    output_path = Path("reports/impact-report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("RepoMedic change-impact analysis completed.")
    print(json.dumps(report, indent=2))
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
