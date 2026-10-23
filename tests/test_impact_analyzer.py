
import pytest

from app.analyzers.impact_analyzer import analyze_change_impact


def test_finds_direct_and_indirect_impact():
    dependency_report = {
        "dependencies": {
            "core.py": [],
            "service.py": ["core.py"],
            "app.py": ["service.py"],
            "unrelated.py": [],
        },
        "dependents": {
            "core.py": ["service.py"],
            "service.py": ["app.py"],
            "app.py": [],
            "unrelated.py": [],
        },
    }

    result = analyze_change_impact(
        dependency_report,
        "core.py",
    )

    assert result["directly_impacted_files"] == 1
    assert result["indirectly_impacted_files"] == 1
    assert result["total_impacted_files"] == 2
    assert result["risk_score"] == 30
    assert result["risk_level"] == "medium"


def test_returns_low_risk_for_unreferenced_file():
    dependency_report = {
        "dependencies": {
            "core.py": [],
            "unused.py": [],
        },
        "dependents": {
            "core.py": [],
            "unused.py": [],
        },
    }

    result = analyze_change_impact(
        dependency_report,
        "unused.py",
    )

    assert result["total_impacted_files"] == 0
    assert result["risk_score"] == 0
    assert result["risk_level"] == "low"


def test_rejects_unknown_file():
    dependency_report = {
        "dependencies": {"core.py": []},
        "dependents": {"core.py": []},
    }

    with pytest.raises(ValueError, match="File not found"):
        analyze_change_impact(
            dependency_report,
            "missing.py",
        )
