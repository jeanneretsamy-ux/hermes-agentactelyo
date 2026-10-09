from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tomllib
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class HarnessError(Exception):
    """A safe, actionable error that may be returned to API consumers."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HarnessError(message)


def load_config(path: str | Path) -> dict:
    with open(path, "rb") as handle:
        cfg = tomllib.load(handle)
    require(bool(cfg.get("principal")), "principal manquant dans la configuration")
    require(isinstance(cfg.get("allowed_matters"), list), "allowed_matters manquant")
    return cfg


def secret(name: str) -> str:
    value = os.environ.get(name, "")
    require(bool(value), f"Variable serveur manquante : {name}")
    return value


def iso_date(value: Any) -> str:
    require(isinstance(value, str), "Date ISO YYYY-MM-DD requise")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HarnessError("Date ISO YYYY-MM-DD invalide") from exc
    require(parsed.isoformat() == value, "Date ISO YYYY-MM-DD requise")
    return value


def source_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def text_content(value: Any) -> str:
    require(isinstance(value, str), "Format de texte fournisseur inattendu")
    return unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def normalized(value: str) -> str:
    return " ".join(value.split())


def policy(cfg: dict, source: str, action: str) -> dict:
    item = cfg.get("sources", {}).get(source, {})
    require(item.get("enabled") is True, f"Source désactivée : {source}")
    require(bool(str(item.get("rights_basis", "")).strip()), f"Droits non documentés : {source}")
    require(item.get(f"allow_{action}") is True, f"Usage {action} non autorisé : {source}")
    return item


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HarnessError("Redirection fournisseur refusée ; vérifier l'URL configurée")


class Http:
    def request(self, method: str, url: str, body=None, headers=None, timeout=30,
                form: bytes | None = None):
        parsed = urlsplit(url)
        require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), "URL fournisseur invalide")
        require(not parsed.username and not parsed.password, "Identifiants interdits dans une URL")
        if parsed.scheme == "http":
            try:
                local = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                local = parsed.hostname == "localhost"
            require(local, "HTTP non chiffré autorisé uniquement en boucle locale")
        payload = form if form is not None else (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        )
        request_headers = {"Accept": "application/json", **(headers or {})}
        if payload is not None:
            request_headers.setdefault("Content-Type", "application/json")
        try:
            req = Request(url, data=payload, headers=request_headers, method=method)
            with build_opener(NoRedirect()).open(req, timeout=timeout) as response:
                raw = response.read(8_000_001)
            require(len(raw) <= 8_000_000, "Réponse fournisseur trop volumineuse")
            result = json.loads(raw)
            require(isinstance(result, dict), "Réponse JSON fournisseur inattendue")
            return result
        except HTTPError as exc:
            # Never expose response bodies, query strings, tokens, or documents.
            raise HarnessError(f"Fournisseur {parsed.hostname} : HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise HarnessError(f"Fournisseur {parsed.hostname} injoignable ou délai dépassé") from exc
        except (ValueError, UnicodeError) as exc:
            raise HarnessError(f"Fournisseur {parsed.hostname} : JSON invalide") from exc


@dataclass
class Evidence:
    source: str
    source_id: str
    title: str
    text: str
    url: str
    jurisdiction: str
    kind: str
    valid_from: str | None = None
    valid_to: str | None = None
    decision_date: str | None = None
    temporal_status: str = "unverified"
    retrieved_at: str = ""
    rights_basis: str = ""

    def __post_init__(self):
        if not self.retrieved_at:
            self.retrieved_at = datetime.now(timezone.utc).isoformat()

    def as_dict(self) -> dict:
        result = asdict(self)
        result["sha256"] = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        result["evidence_id"] = self.key
        return result

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"


def check_temporal(evidence: Evidence, as_of: str) -> Evidence:
    iso_date(as_of)
    if evidence.kind == "legislation":
        if evidence.valid_from and as_of < evidence.valid_from:
            evidence.temporal_status = "outside_period"
        elif evidence.valid_to and as_of >= evidence.valid_to:
            evidence.temporal_status = "outside_period"
        elif evidence.valid_from and evidence.valid_to:
            evidence.temporal_status = "within_period"
        else:
            evidence.temporal_status = "unverified"
    elif evidence.kind == "case_law":
        if evidence.decision_date:
            evidence.temporal_status = "future_decision" if evidence.decision_date > as_of else "decision_predates_request"
        else:
            evidence.temporal_status = "unverified"
    return evidence
