"""Detect identifiable new legal references in assertions, not their legal validity."""
import re

ARTICLE = re.compile(r"\b(?:article|art\.)\s+((?:[A-Z]\.\s*)?\d+(?:[.-]\d+)*)\b", re.IGNORECASE)
DOCKET = re.compile(r"\b\d{2}[-/\u2011\u2013]\d{2}[.\s]?\d{3}\b")
COURT = re.compile(r"\b(?:cassation|jurisprudence|tribunal|pourvoi|arrêt|cour)\b", re.IGNORECASE)


def canonical(value):
    return re.sub(r"[.\s/\u2011\u2013-]", "", value).casefold()


def article_key(value):
    value = re.sub(r"\s", "", value).casefold()
    return re.sub(r"^([a-z])\.", r"\1", value)


def assertion_texts(analysis):
    risks = analysis.get("risks")
    risks = risks if isinstance(risks, list) else []
    values = [analysis.get("summary"), *[r.get(k) for r in risks if isinstance(r, dict)
                                       for k in ("issue", "analysis", "proposal")]]
    return [x for x in values if isinstance(x, str)]


def validate_narrative_references(analysis, evidence, documents):
    supplied = "\n".join(e.title + "\n" + e.text for e in evidence.values())
    articles = {article_key(x) for x in ARTICLE.findall(supplied)}
    contract_articles = {article_key(x) for d in documents for x in ARTICLE.findall(d["text"])}
    dockets = {canonical(x) for x in DOCKET.findall(supplied)}
    errors = []
    for text in assertion_texts(analysis):
        for match in ARTICLE.finditer(text):
            key = article_key(match.group(1))
            contractual = re.match(r"\s+(?:du|de ce|du présent|de cet)\s+(?:contrat|document|accord|bail)",
                                  text[match.end():], re.IGNORECASE)
            if key not in articles and not (contractual and key in contract_articles):
                errors.append("Référence d'article non fournie dans une affirmation du brouillon")
        if COURT.search(text) and any(canonical(x) not in dockets for x in DOCKET.findall(text)):
            errors.append("Référence judiciaire non fournie dans une affirmation du brouillon")
    return list(dict.fromkeys(errors))
