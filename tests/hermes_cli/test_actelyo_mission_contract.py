"""Exercise the existing CLI/storage contract used by Atelier mission prompts."""
import argparse
import json


def test_mission_limits_and_idempotency_survive_reopening(tmp_path, monkeypatch, capsys):
    from hermes_cli import kanban_db as kb, kanban_db_connect as kbc
    from hermes_cli.kanban import kanban_command
    from hermes_cli.kanban_parser import build_parser

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile"))
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    kb.init_db()
    body = tmp_path / "mission.txt"
    body.write_text("Comparer les pièces.\n--ne-pas-interpreter-comme-option\nValidation avant envoi.", encoding="utf-8")
    parser = argparse.ArgumentParser()
    build_parser(parser.add_subparsers())
    args = parser.parse_args([
        "kanban", "create", "Mission ALPHA", "--body-file", str(body),
        "--assignee", "default", "--workspace", "scratch", "--goal",
        "--goal-max-turns", "20", "--max-runtime", "30m", "--max-retries", "2",
        "--completion-contract", "local-only", "--idempotency-key", "mission-alpha", "--json",
    ])
    assert kanban_command(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert kanban_command(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["id"] == second["id"]
    with kbc.connect_closing() as conn:
        task = kb.get_task(conn, first["id"])
        assert task.goal_mode and task.goal_max_turns == 20
        assert task.max_runtime_seconds == 1800 and task.max_retries == 2
        assert task.completion_contract == "local-only"
        assert task.assignee == "default"

