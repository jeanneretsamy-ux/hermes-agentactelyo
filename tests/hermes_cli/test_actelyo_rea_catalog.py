"""The Actelyo REA integration stays pinned and limits its initial tool surface."""

from pathlib import Path

import hermes_yaml as yaml


REPO = Path(__file__).resolve().parents[2]


def test_rea_catalog_pins_package_and_starts_windows_stdio_server():
    manifest = yaml.safe_load(
        (REPO / "optional-mcps" / "rea" / "manifest.yaml").read_text(encoding="utf-8")
    )

    assert manifest["transport"] == {
        "type": "stdio",
        "command": "cmd.exe",
        "args": ["/d", "/c", "npx", "-y", "rea-agents@6.5.0", "mcp"],
    }


def test_rea_default_tools_are_limited_to_application_evidence_workflow():
    manifest = yaml.safe_load(
        (REPO / "optional-mcps" / "rea" / "manifest.yaml").read_text(encoding="utf-8")
    )

    assert manifest["tools"]["default_enabled"] == [
        "binary_session",
        "analyze_javascript_application",
        "inspect_analysis_view",
        "trace_application_feature",
    ]

