
import ast

from app.analyzers.bug_detector import (
    BugRuleVisitor,
    analyze_project,
    classify_file_context,
    make_finding,
    merge_findings,
)


def analyze_source(source: str) -> list[dict]:
    tree = ast.parse(source)
    visitor = BugRuleVisitor("example.py")
    visitor.visit(tree)
    return visitor.findings


def test_detects_mutable_default_argument():
    findings = analyze_source(
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n"
    )

    assert any(f["rule_id"] == "RM101" for f in findings)


def test_detects_bare_except():
    findings = analyze_source(
        "try:\n"
        "    risky_operation()\n"
        "except:\n"
        "    pass\n"
    )

    assert any(f["rule_id"] == "RM102" for f in findings)


def test_detects_eval():
    findings = analyze_source("result = eval(user_input)\n")

    assert any(f["rule_id"] == "RM103" for f in findings)


def test_detects_shell_true():
    findings = analyze_source(
        "import subprocess\n"
        "subprocess.run(command, shell=True)\n"
    )

    assert any(f["rule_id"] == "RM107" for f in findings)


def test_clean_code_has_no_custom_findings():
    findings = analyze_source(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    assert findings == []


def test_project_scan_reports_syntax_errors(tmp_path):
    (tmp_path / "broken.py").write_text(
        "def broken(\n",
        encoding="utf-8",
    )

    report = analyze_project(tmp_path)

    assert report["files_analyzed"] == 1
    assert report["syntax_errors"] == 1
    assert any(
        finding["rule_id"] == "RM001"
        for finding in report["findings"]
    )


def test_merges_duplicate_shell_command_findings():
    findings = [
        make_finding(
            "RM107",
            "Shell command execution",
            "high",
            "bug_demo.py",
            8,
            "shell=True can create command-injection risks.",
            "Use shell=False and pass arguments as a list.",
            "RepoMedic",
        ),
        make_finding(
            "B602",
            "subprocess_popen_with_shell_equals_true",
            "high",
            "bug_demo.py",
            8,
            "Possible shell injection.",
            "Review shell usage.",
            "Bandit",
        ),
    ]

    merged = merge_findings(findings)

    assert len(merged) == 1
    assert set(merged[0]["rule_ids"]) == {"RM107", "B602"}
    assert set(merged[0]["sources"]) == {"RepoMedic", "Bandit"}
    assert merged[0]["occurrences"] == 2
    assert merged[0]["severity"] == "high"


def test_does_not_merge_different_lines():
    findings = [
        make_finding(
            "RM107",
            "Shell command execution",
            "high",
            "bug_demo.py",
            8,
            "Shell execution detected.",
            "Use shell=False.",
            "RepoMedic",
        ),
        make_finding(
            "B602",
            "subprocess_popen_with_shell_equals_true",
            "high",
            "bug_demo.py",
            12,
            "Possible shell injection.",
            "Review shell usage.",
            "Bandit",
        ),
    ]

    merged = merge_findings(findings)

    assert len(merged) == 2


def test_merge_preserves_highest_severity():
    findings = [
        make_finding(
            "RM107",
            "Shell command execution",
            "medium",
            "bug_demo.py",
            8,
            "Shell execution detected.",
            "Avoid shell commands.",
            "RepoMedic",
        ),
        make_finding(
            "B602",
            "subprocess_popen_with_shell_equals_true",
            "high",
            "bug_demo.py",
            8,
            "Possible shell injection.",
            "Review shell usage.",
            "Bandit",
        ),
    ]

    merged = merge_findings(findings)

    assert len(merged) == 1
    assert merged[0]["severity"] == "high"


def test_classifies_test_file_context():
    assert classify_file_context("tests/test_auth.py") == "test"
    assert classify_file_context("src/test_helpers.py") == "test"
    assert classify_file_context("src/auth_test.py") == "test"


def test_classifies_production_file_context():
    assert classify_file_context("src/app.py") == "production"
    assert classify_file_context("app/analyzers/bug_detector.py") == "production"


def test_classifies_unknown_file_context():
    assert classify_file_context("unknown") == "unknown"
    assert classify_file_context("") == "unknown"


def test_finding_includes_context_and_category():
    finding = make_finding(
        "B101",
        "Use of assert",
        "low",
        "tests/test_example.py",
        10,
        "Assertion detected.",
        "Review assertion usage.",
        "Bandit",
    )

    assert finding["file_context"] == "test"
    assert finding["category"] == "security"


def test_custom_finding_includes_code_quality_category():
    finding = make_finding(
        "RM101",
        "Mutable default argument",
        "medium",
        "src/example.py",
        4,
        "Mutable default detected.",
        "Use None and create a new collection.",
    )

    assert finding["file_context"] == "production"
    assert finding["category"] == "code_quality"


def test_project_scan_includes_context_and_category_counts(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    (tmp_path / "src" / "app.py").write_text(
        "result = eval(user_input)\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_app.py").write_text(
        "result = eval(user_input)\n",
        encoding="utf-8",
    )

    report = analyze_project(tmp_path)

    assert "context_counts" in report
    assert "category_counts" in report
    assert report["context_counts"]["production"] >= 1
    assert report["context_counts"]["test"] >= 1
    assert (
        report["context_counts"]["production"]
        + report["context_counts"]["test"]
        + report["context_counts"]["unknown"]
        == report["total_findings"]
    )
