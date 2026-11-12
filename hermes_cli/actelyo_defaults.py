"""Local first-run values only; never merge these over an existing profile."""

ACTELYO_LLM_BASE_URL = "http://127.0.0.1:1235/v1"


def actelyo_local_model_seed() -> dict:
    # An empty ID discovers the single loaded LLM from the actual local
    # catalogue; it never authorizes cloud fallback or a model download.
    return {"model": {"provider": "custom", "base_url": ACTELYO_LLM_BASE_URL, "default": ""}}
