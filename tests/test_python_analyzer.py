
from app.analyzers.python_analyzer import analyze_python_file


def test_analyzer_extracts_functions_classes_and_imports(tmp_path):
    source = tmp_path / "sample.py"

    source.write_text(
        "import os\n"
        "class Worker:\n"
        "    def run(self):\n"
        "        print(os.getcwd())\n"
        "async def start():\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = analyze_python_file(str(source))

    assert result["status"] == "success"
    assert "Worker" in [item["name"] for item in result["classes"]]
    assert "run" in [item["name"] for item in result["functions"]]
    assert "start" in [item["name"] for item in result["functions"]]
    assert any(item["module"] == "os" for item in result["imports"])
    assert any(item["name"] == "print" for item in result["calls"])


def test_analyzer_reports_syntax_errors(tmp_path):
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = analyze_python_file(str(source))

    assert result["status"] == "error"
    assert result["errors"][0]["type"] == "SyntaxError"
    assert result["errors"][0]["line"] == 1
