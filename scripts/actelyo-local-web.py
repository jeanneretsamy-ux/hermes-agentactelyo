"""Start the actual Actelyo Law Harness dashboard on this computer's loopback."""
import argparse
import os
import shutil
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Actelyo Law Harness en localhost")
parser.add_argument("--port", type=int, default=8091)
parser.add_argument("--home", type=Path, default=Path.home() / ".actelyo-law-harness" / "web")
parser.add_argument("--web-dist", type=Path)
parser.add_argument("--no-open", action="store_true")
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
home = args.home.resolve()
home.mkdir(parents=True, exist_ok=True)
os.environ["HERMES_HOME"] = str(home)
os.environ["PYTHONPATH"] = str(repo) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
os.environ.pop("HERMES_SERVE_HEADLESS", None)
# Windows cold imports can exceed the terminal's 15-second default handshake.
os.environ.setdefault("HERMES_TUI_STARTUP_TIMEOUT_MS", "120000")
if args.web_dist:
    os.environ["HERMES_WEB_DIST"] = str(args.web_dist.resolve())
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]
if not os.environ.get("HERMES_NODE") and (node := shutil.which("node")):
    os.environ["HERMES_NODE"] = node
if (repo / "ui-tui" / "dist" / "entry.js").exists():
    os.environ.setdefault("HERMES_TUI_DIR", str(repo / "ui-tui"))
sys.path.insert(0, str(repo))
os.chdir(home)
from hermes_cli.config import atomic_config_write
from toolsets import _HERMES_CORE_TOOLS
if not (home / "config.yaml").exists():
    atomic_config_write(home / "config.yaml", {
        "model": {"default": "legalya-v30", "provider": "lmstudio", "base_url": "http://127.0.0.1:1234/v1", "context_length": 16384},
        "providers": {"lmstudio": {"request_timeout_seconds": 600}},
        "display": {"language": "fr"},
        "platform_hints": {"tui": {"append": "Le nom de cette application est Actelyo Law Harness. Présente-toi sous ce nom exact et réponds en français. Les noms techniques dans les chemins ou les outils ne sont pas ton nom."}},
        "terminal": {"backend": "local", "cwd": str(home)},
        "telemetry": {"shared_metrics": {"enabled": False, "send": False}},
        # All tools remain discoverable without sending every schema each turn.
        "tools": {"tool_search": {"enabled": "on", "listing": "off", "defer": [name for name in _HERMES_CORE_TOOLS if name != "clarify"]}},
    })
if not (home / "SOUL.md").exists():
    (home / "SOUL.md").write_text("Tu es Actelyo Law Harness, l’agent Actelyo. Réponds en français. Utilise les outils réellement disponibles et distingue toujours une action effectuée d’une action proposée. N’invente aucune référence juridique.\n", encoding="utf-8")
from tools.skills_sync import sync_skills
sync_skills(quiet=True)
from hermes_cli import web_server
print(f"Actelyo Law Harness : http://127.0.0.1:{args.port}", flush=True)
web_server.start_server(host="127.0.0.1", port=args.port, open_browser=not args.no_open, headless=False, isolated=True)
