"""Validated sampling options for custom Chat Completions endpoints.

The existing provider extra_body path is the runtime authority; no second
agent configuration or renderer-only sampler is introduced.
"""
import math

FIELDS = {
    "temperature": ("temperature", 0, 2, False),
    "topP": ("top_p", 0.01, 1, False),
    "topK": ("top_k", 1, 1000, True),
    "minP": ("min_p", 0, 1, False),
    "repetitionPenalty": ("repeat_penalty", 0.1, 2, False),
    "maxOutputTokens": ("max_tokens", 1, 32768, True),
    "seed": ("seed", 0, 4294967295, True),
}
STANDARD = {"temperature", "topP", "maxOutputTokens"}

def generation_parameters(settings, adapter="openai-compatible"):
    if adapter not in ("openai-compatible", "llama.cpp"):
        raise ValueError("Unsupported generation adapter")
    if not isinstance(settings, dict):
        raise ValueError("Generation settings must be an object")
    result = {}
    for key, value in settings.items():
        if key == "thinking":
            if adapter != "llama.cpp" or not isinstance(value, bool):
                raise ValueError("Thinking requires a compatible llama.cpp endpoint")
            result["chat_template_kwargs"] = {"enable_thinking": value}
            continue
        if key not in FIELDS or (adapter == "openai-compatible" and key not in STANDARD):
            raise ValueError(f"Unsupported generation setting: {key}")
        wire, minimum, maximum, integer = FIELDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum or (integer and int(value) != value):
            raise ValueError(f"Invalid generation setting: {key}")
        result[wire] = value
    return result

def read_generation_settings(entry):
    body = entry.get("extra_body")
    if not isinstance(body, dict):
        return {}
    result = {key: body[rule[0]] for key, rule in FIELDS.items() if rule[0] in body}
    template = body.get("chat_template_kwargs")
    if isinstance(template, dict) and isinstance(template.get("enable_thinking"), bool):
        result["thinking"] = template["enable_thinking"]
    return result
