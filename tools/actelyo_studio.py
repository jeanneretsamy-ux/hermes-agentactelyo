"""Desktop agent adapter for the same managed model service used by Studio.

No model weights or credentials live here. Session profile context is inherited,
and a job is only readable by the profile which started it through this tool.
"""
from __future__ import annotations

import asyncio
import json
import threading

from hermes_constants import get_hermes_home
from tools.registry import registry

_jobs: dict[str, str] = {}
_lock = threading.Lock()
_ACTIONS = ["status", "catalog", "test_inference", "install_runtime", "start", "stop", "activate", "eject", "import", "download", "job"]


async def handle_studio(args: dict, **_kwargs) -> str:
    from hermes_cli.web_routers import local_models as service

    action = args.get("action", "status")
    home = str(get_hermes_home().resolve())
    model = args.get("model_id", "")
    try:
        if action == "status":
            result = await asyncio.to_thread(service.local_models_status)
        elif action == "catalog":
            result = await asyncio.to_thread(service.local_models_catalog)
        elif action == "install_runtime":
            result = await asyncio.to_thread(service.install_runtime_in_current_profile)
        elif action in ("start", "stop"):
            result = await service.local_models_server(service.ServerActionBody(action=action))
        elif action == "test_inference":
            result = service.test_inference_in_current_profile(model)
        elif action == "activate":
            result = service.activate_model_in_current_profile(model)
        elif action == "eject":
            result = await asyncio.to_thread(service.local_models_eject, service.ModelEjectBody(model_id=model))
        elif action == "import":
            result = await service.local_models_sideload(service.SideloadBody(path=args.get("path", "")))
        elif action == "download":
            result = await asyncio.to_thread(service.local_models_download, service.ModelDownloadBody(model_id=model))
        elif action == "job":
            job_id = args.get("job_id", "")
            with _lock:
                if _jobs.get(job_id) != home:
                    raise ValueError("Ce travail n’appartient pas à ce profil ou a expiré.")
            result = await service.local_models_job(job_id)
        else:
            raise ValueError("Action Studio inconnue.")
        if isinstance(result, dict) and result.get("job_id"):
            with _lock:
                _jobs[result["job_id"]] = home
                while len(_jobs) > 256:
                    _jobs.pop(next(iter(_jobs)))
        return json.dumps({"success": True, "action": action, "data": result}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "action": action, "error": str(getattr(exc, "detail", exc))}, ensure_ascii=False)


registry.register(
    name="actelyo_studio", toolset="desktop_ui",
    schema={"name": "actelyo_studio", "description": (
        "Manage Actelyo Studio's local GGUF models on the connected backend machine, in the current profile. "
        "Read status/catalog before mutations; use exact returned model IDs. Import an existing absolute GGUF path, "
        "install the managed runtime or download a catalog model only when requested, start/stop the server, activate a model for NEW chats, "
        "or eject a model from memory. Activation does not change this conversation or prove inference works. "
        "test_inference performs a bounded real completion with an installed model; it may load weights and consume memory. Poll the job: this verifies text generation and a simple instruction, not tools, vision or legal accuracy. "
        "Jobs are asynchronous: poll job until done/error; never claim success from a job_id alone. "
        "Stopping/ejecting can affect other chats on this machine. Does not manage an external LM Studio process "
        "or load embedding/classifier adapters as chat models. Do not download or copy large files without user intent."
    ), "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": _ACTIONS},
        "model_id": {"type": "string"}, "path": {"type": "string"}, "job_id": {"type": "string"}
    }, "required": ["action"], "additionalProperties": False}},
    handler=handle_studio, is_async=True,
)
