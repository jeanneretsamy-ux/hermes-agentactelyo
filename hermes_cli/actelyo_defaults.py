"""Local first-run values only; never merge these over an existing profile."""

ACTELYO_LLM_BASE_URL = "http://127.0.0.1:1235/v1"


def actelyo_local_model_seed() -> dict:
    # An empty ID requires an actual model selection. It is not an invented
    # catalogue entry and does not authorize cloud fallback or model download.
    return {"model": {"provider": "custom", "base_url": ACTELYO_LLM_BASE_URL, "default": ""}}
