
import argparse
import json
import sys

from app.analyzers.project_scanner import save_report, scan_project


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan a Python project with RepoMedic."
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory you want to analyze.",
    )

    parser.add_argument(
        "--output",
        default="reports/scan-report.json",
        help="Path for the JSON report.",
    )

    args = parser.parse_args()

    try:
        report = scan_project(args.project_path)
        save_report(report, args.output)
    except (OSError, ValueError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 1

    print("RepoMedic scan completed.\n")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nFull report saved to: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
