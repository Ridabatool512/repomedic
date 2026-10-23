
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "RepoMedic API"
    assert response.json()["status"] == "running"


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_scan_rejects_path_outside_workspace():
    response = client.post(
        "/api/scan",
        json={"project_path": "C:\\Windows"},
    )

    assert response.status_code == 403


def test_scan_rejects_missing_directory():
    response = client.post(
        "/api/scan",
        json={
            "project_path": str(
                app_workspace() / "missing-project"
            )
        },
    )

    assert response.status_code == 404


def test_scan_rejects_file_instead_of_directory(tmp_path):
    test_file = tmp_path / "example.py"
    test_file.write_text("print('hello')", encoding="utf-8")

    response = client.post(
        "/api/scan",
        json={"project_path": str(test_file)},
    )

    assert response.status_code == 403


def test_scan_accepts_workspace_project():
    response = client.post(
        "/api/scan",
        json={
            "project_path": str(
                app_workspace() / "demo-project"
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"]["python_files"] >= 1


def test_impact_rejects_missing_project():
    response = client.post(
        "/api/impact",
        json={
            "project_path": str(
                app_workspace() / "missing-project"
            ),
            "changed_file": "main.py",
        },
    )

    assert response.status_code == 404


def app_workspace():
    from app.main import WORKSPACE_ROOT

    return WORKSPACE_ROOT
