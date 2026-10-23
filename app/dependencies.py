
import argparse
import json

from app.analyzers.dependency_analyzer import build_dependency_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a RepoMedic Python dependency graph."
    )
    parser.add_argument("project_path", help="Project folder to scan")
    args = parser.parse_args()

    report = build_dependency_graph(args.project_path)

    output_path = "reports/dependency-report.json"
    from pathlib import Path

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("Dependency analysis completed.")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nFull report saved to: {output_path}")


if __name__ == "__main__":
    main()
