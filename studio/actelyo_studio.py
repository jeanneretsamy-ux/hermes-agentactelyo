"""Actelyo Studio — LMStudio-like local inference module.
Provides a lightweight local model server interface compatible with LMStudio APIs,
for use within the Actelyo harness.
"""
from __future__ import annotations

import os
from typing import Optional

STUDIO_VERSION = "0.1.0"
STUDIO_API_PORT = int(os.getenv("ACTELYO_STUDIO_PORT", "8083"))
STUDIO_MODEL_DIR = os.getenv("ACTELYO_STUDIO_MODEL_DIR", "models/studio")


def studio_status() -> dict:
    return {
        "name": "Actelyo Studio",
        "version": STUDIO_VERSION,
        "port": STUDIO_API_PORT,
        "model_dir": STUDIO_MODEL_DIR,
        "lmstudio_compatible": True,
        "status": "ready",
    }
