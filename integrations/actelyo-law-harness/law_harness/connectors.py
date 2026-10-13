from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import quote, urlencode, urlsplit

from .core import (Evidence, HarnessError, Http, check_temporal, iso_date,
                   policy, require, secret, source_date, text_content)


class Legifrance:
    def __init__(self, cfg: dict, http: Http):
        self.cfg, self.http = cfg, http
        self.token, self.expires = "", 0.0

    def _post(self, path: str, payload: dict):
        settings = policy(self.cfg, "legifrance", "process")
        env = settings.get("environment", "sandbox")
        require(env in {"sandbox", "production"}, "Environnement PISTE invalide")
        prefix = "sandbox-" if env == "sandbox" else ""
        if time.monotonic() >= self.expires:
            form = urlencode({"grant_type": "client_credentials", "scope": "openid",
                              "client_id": secret(settings.get("client_id_env", "PISTE_CLIENT_ID")),
                              "client_secret": secret(settings.get("client_secret_env", "PISTE_CLIENT_SECRET"))}).encode()
            result = self.http.request("POST", f"https://{prefix}oauth.piste.gouv.fr/api/oauth/token",
                                       headers={"Content-Type": "application/x-www-form-urlencoded"}, form=form)
            require(isinstance(result.get("access_token"), str) and bool(result["access_token"]), "Jeton PISTE absent")
            self.token = result["access_token"]
            try:
                ttl = max(1, int(result.get("expires_in", 3600)) - 30)
            except (TypeError, ValueError) as exc:
                raise HarnessError("Expiration PISTE invalide") from exc
            self.expires = time.monotonic() + ttl
        base = f"https://{prefix}api.piste.gouv.fr/dila/legifrance/lf-engine-app"
        return self.http.request("POST", base + path, payload,
                                 {"Authorization": f"Bearer {self.token}"})

    def search(self, query: str, as_of: str, limit: int = 5) -> list[dict]:
        iso_date(as_of)
        # Version-specific French codes only in v0.1.
        result = self._post("/search", {"fond": "CODE_DATE", "recherche": {
            "champs": [{"typeChamp": "ARTICLE", "operateur": "ET", "criteres": [
                {"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP", "valeur": query, "operateur": "ET"}]}],
            "filtres": [{"facette": "DATE_VERSION", "singleDate": as_of}],
            "pageNumber": 1, "pageSize": limit, "operateur": "ET", "sort": "PERTINENCE", "typePagination": "ARTICLE"}})
        require(isinstance(result.get("results"), list), "Schéma recherche Légifrance inattendu")
        hits: list[dict] = []
        # Article IDs may be nested in titles/sections/extracts depending on API release.
        def walk(node):
            if isinstance(node, dict):
                identifier = node.get("id")
                if isinstance(identifier, str) and re.fullmatch(r"LEGIARTI\d+", identifier):
                    if not any(h["source_id"] == identifier for h in hits):
                        hits.append({"source": "legifrance", "source_id": identifier,
                                     "title": str(node.get("title") or node.get("num") or identifier)})
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(result["results"])
        require(not result["results"] or bool(hits), "Résultats PISTE sans identifiants d'articles consultables")
        return hits[:limit]

    def fetch(self, source_id: str, as_of: str) -> Evidence:
        require(bool(re.fullmatch(r"LEGIARTI\d+", source_id)), "Identifiant article Légifrance invalide")
        result = self._post("/consult/getArticle", {"id": source_id})
        article = result.get("article")
        require(isinstance(article, dict), "Schéma article Légifrance inattendu")
        require(article.get("id") == source_id, "Article retourné différent de l'article demandé")
        text = text_content(article.get("texte") or article.get("texteHtml") or "")
        require(bool(text), "Article sans texte consultable")
        evidence = Evidence("legifrance", source_id, str(article.get("num") or source_id), text,
                            f"https://www.legifrance.gouv.fr/codes/article_lc/{source_id}", "FR", "legislation",
                            valid_from=source_date(article.get("dateDebut")),
                            valid_to=source_date(article.get("dateFin")),
                            rights_basis=policy(self.cfg, "legifrance", "process")["rights_basis"])
        return check_temporal(evidence, as_of)


class LegalDataHunter:
    BASE = "https://legaldatahunter.com/v1"

    def __init__(self, cfg: dict, http: Http):
        self.cfg, self.http = cfg, http

    def _call(self, method: str, path: str, body=None):
        settings = policy(self.cfg, "legal_data_hunter", "process")
        key = secret(settings.get("token_env", "LEGAL_DATA_HUNTER_API_KEY"))
        return self.http.request(method, self.BASE + path, body, {"Authorization": f"Bearer {key}"})

    def _allowed(self, origin: str):
        settings = policy(self.cfg, "legal_data_hunter", "process")
        require(origin in settings.get("allowed_sources", []), "Origine LDH non autorisée par le contrat configuré")
        require(bool(re.fullmatch(r"FR/[A-Za-z0-9_-]+", origin)), "Origine LDH française invalide")

    def search(self, query: str, as_of: str, limit: int = 5) -> list[dict]:
        iso_date(as_of)
        results = []
        settings = policy(self.cfg, "legal_data_hunter", "process")
        for namespace in ("case_law", "legislation"):
            result = self._call("POST", "/search", {"q": query, "namespace": namespace, "top_k": limit})
            require(isinstance(result.get("hits"), list), "Schéma recherche LDH inattendu")
            for hit in result["hits"]:
                require(isinstance(hit, dict), "Résultat LDH invalide")
                origin = hit.get("source", "")
                identifier = hit.get("source_id")
                if origin not in settings.get("allowed_sources", []):
                    continue
                self._allowed(origin)
                require(isinstance(identifier, str) and bool(identifier), "Identifiant LDH absent")
                results.append({"source": "legal_data_hunter", "source_id": f"{origin}/{identifier}",
                                "title": str(hit.get("title") or identifier), "kind": namespace})
        return results[:limit]

    def fetch(self, source_id: str, as_of: str) -> Evidence:
        parts = source_id.split("/")
        require(len(parts) == 3 and bool(parts[2]) and parts[2] not in {".", ".."}, "Identifiant LDH invalide")
        origin, identifier = "/".join(parts[:2]), parts[2]
        self._allowed(origin)
        path = "/documents/" + "/".join(quote(p, safe="") for p in parts)
        result = self._call("GET", path)
        # Different API releases may wrap the document in 'document'.
        doc = result.get("document", result)
        require(isinstance(doc, dict), "Schéma document LDH inattendu")
        if doc.get("source_id") is not None:
            require(doc["source_id"] == identifier, "Identifiant LDH retourné différent")
        if doc.get("source") is not None:
            require(doc["source"] == origin, "Origine LDH retournée différente")
        text = text_content(doc.get("text", ""))
        require(bool(text), "Document LDH sans texte")
        kind = doc.get("type") or doc.get("namespace") or "unknown"
        if not isinstance(kind, str) or kind not in {"legislation", "case_law"}:
            kind = "unknown"
        # Do not infer legislative validity from retrieval time or publication date.
        url = str(doc.get("url") or "")
        if url and urlsplit(url).scheme != "https":
            url = ""
        evidence = Evidence("legal_data_hunter", source_id, str(doc.get("title") or identifier),
                            text, url, "FR", kind,
                            valid_from=source_date(doc.get("valid_from")),
                            valid_to=source_date(doc.get("valid_to")),
                            decision_date=source_date(doc.get("decision_date")),
                            rights_basis=policy(self.cfg, "legal_data_hunter", "process")["rights_basis"])
        return check_temporal(evidence, as_of)


class Model:
    def __init__(self, cfg: dict, http: Http):
        self.cfg, self.http = cfg, http

    def _base(self):
        url = str(self.cfg.get("model", {}).get("base_url", "http://127.0.0.1:1234/v1")).rstrip("/")
        parsed = urlsplit(url)
        require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), "URL modèle invalide")
        require(not parsed.query and not parsed.fragment and not parsed.username and not parsed.password, "URL modèle invalide")
        require(parsed.path.rstrip("/") == "/v1", "API modèle compatible /v1 requise")
        return url

    def _headers(self):
        settings = self.cfg.get("model", {})
        key = os.environ.get(settings.get("token_env", "LM_STUDIO_API_TOKEN"), "")
        return {"Authorization": f"Bearer {key}"} if key else {}

    def models(self):
        result = self.http.request("GET", self._base() + "/models", headers=self._headers())
        require(isinstance(result.get("data"), list), "Liste des modèles invalide")
        return [item["id"] for item in result["data"] if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def complete(self, system: str, payload: dict, schema: dict | None = None):
        settings = self.cfg.get("model", {})
        base = self._base()
        from ipaddress import ip_address
        host = urlsplit(base).hostname
        try:
            local = ip_address(host).is_loopback
        except ValueError:
            local = host == "localhost"
        require(local or settings.get("allow_remote_documents") is True,
                "Transmission des documents vers un modèle distant non autorisée")
        require(bool(settings.get("name")), "Nom du modèle non configuré")
        result = self.http.request("POST", base + "/chat/completions", {
            "model": settings["name"], "temperature": 0,
            "max_tokens": settings.get("max_output_tokens", 4096),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "actelyo_output", "strict": True, "schema": schema or {"type": "object"}}}}, self._headers(),
            timeout=settings.get("timeout_seconds", 120))
        try:
            raw = result["choices"][0]["message"]["content"]
            output = json.loads(raw)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise HarnessError("Le modèle n'a pas fourni le JSON attendu") from exc
        require(isinstance(output, dict), "Sortie modèle JSON objet requise")
        return output
