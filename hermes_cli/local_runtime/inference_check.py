"""Bounded real completion probe for the owned managed runtime, without installing anything."""
import json
import time
import urllib.error
import urllib.request


def check(model_id):
    from agent.model_metadata import MINIMUM_CONTEXT_LENGTH, _query_local_context_length_uncached
    from hermes_cli.local_runtime import bootstrap
    from hermes_cli.local_runtime.endpoint import _state_endpoint
    if model_id not in bootstrap.staged_model_ids():
        raise ValueError("Modèle GGUF absent : importez le fichier dans Studio avant le test.")
    endpoint = _state_endpoint()
    if not endpoint:
        raise ValueError("Serveur local arrêté : démarrez-le dans Studio avant le test.")
    started = time.monotonic()
    payload = {"model": model_id, "messages": [{"role": "user", "content": "Réponds uniquement par ACTELYO_OK."}],
               "max_tokens": 64, "temperature": 0, "stream": False}
    request = urllib.request.Request(endpoint["base_url"].rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
        "Authorization": f"Bearer {endpoint.get('api_key', '')}"}, method="POST")
    # The first completion may load weights. A timeout is a diagnostic failure, never proof of incompatibility.
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read(1_048_577)
    except urllib.error.HTTPError as exc:
        advice = {400: "Vérifiez le format de chat et les paramètres du modèle.",
                  401: "L’authentification du moteur a échoué ; redémarrez le serveur Studio.",
                  404: "Le moteur ne trouve pas ce modèle ; réimportez-le ou redémarrez le serveur.",
                  503: "Le moteur est indisponible ou en cours de chargement ; vérifiez la mémoire et son journal."}
        raise ValueError(f"Moteur HTTP {exc.code}. " + advice.get(exc.code, "Consultez le journal du moteur : le chargement ou la génération a échoué.")) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise ValueError("Le moteur ne répond pas dans le délai de test (120 s maximum d’attente réseau). Vérifiez son état et la mémoire disponible. Ce résultat ne prouve pas que le modèle est incompatible.") from exc
    if len(raw) > 1_048_576:
        raise ValueError("Réponse de diagnostic trop volumineuse.")
    data = json.loads(raw)
    choices = data.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Le moteur n’a retourné aucun texte. Vérifiez le modèle de chat, son format et le journal du moteur.")
    window = _query_local_context_length_uncached(model_id, endpoint['base_url'], endpoint.get('api_key', ''))
    if window is None:
        context_verdict = "Fenêtre de contexte non déterminée ; compatibilité avec l’agent complet non vérifiée."
    elif window < MINIMUM_CONTEXT_LENGTH:
        context_verdict = (f"Contexte annoncé : {window} tokens, inférieur aux {MINIMUM_CONTEXT_LENGTH} requis par l’agent complet. "
                           "Une réponse courte fonctionne mais pas nécessairement le Harness complet. "
                           "Utilisez un modèle avec une fenêtre suffisante ; ne déclarez pas une capacité fictive dans la configuration.")
    else:
        context_verdict = (f"Contexte annoncé : {window} tokens. Le seuil de l’agent complet est atteint, "
                           "mais une conversation longue peut encore le dépasser : compressez l’historique et limitez les documents joints.")
    return {"model_id": model_id, "inference_ok": True,
            "context_tokens": window, "context_diagnostic": context_verdict,
            "instruction_followed": content.strip() == "ACTELYO_OK",
            "response": content[:2000], "elapsed_seconds": round(time.monotonic() - started, 2),
            "limitations": "Ce test ne valide ni les appels d’outils, ni la vision, ni la qualité juridique."}
