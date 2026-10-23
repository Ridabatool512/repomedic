import ast

from app.analyzers.bug_detector import (
    BugRuleVisitor,
    analyze_project,
    make_finding,
    merge_findings,
)
import ast

from app.analyzers.bug_detector import (
    BugRuleVisitor,
    analyze_project,
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
    findings = analyze_source(
        "result = eval(user_input)\n"
    )

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