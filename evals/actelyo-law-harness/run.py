"""Reproducible paired safety pilot; never reports automatic legal correctness."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrations" / "actelyo-law-harness"))
from law_harness.connectors import Model
from law_harness.core import Evidence, HarnessError, Http, check_temporal, load_config
from law_harness.harness import Harness, REVIEW_PROMPT, validate_analysis
from law_harness.schemas import REVIEW_SCHEMA

def digest(value):
    return hashlib.sha256(value).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

class RecordingHttp(Http):
    def __init__(self):
        self.calls = []

    def request(self, method, url, *args, **kwargs):
        start = time.perf_counter()
        item = {"method": method, "seconds": None, "ok": False}
        try:
            result = super().request(method, url, *args, **kwargs)
            item["ok"] = True
            if isinstance(result.get("usage"), dict):
                item["usage"] = result["usage"]
            return result
        finally:
            item["seconds"] = round(time.perf_counter() - start, 3)
            self.calls.append(item)

class SnapshotConnector:
    """Oracle retrieval isolates generation/gates; does not test live APIs."""
    def __init__(self, items, fail=False):
        self.items = items
        self.fail = fail

    def search(self, query, as_of, limit):
        if self.fail:
            raise HarnessError("Panne documentaire synthétique d'évaluation")
        return [{"source_id": item.source_id} for item in self.items[:limit]]

    def fetch(self, source_id, as_of):
        item = next(e for e in self.items if e.source_id == source_id)
        return check_temporal(copy.deepcopy(item), as_of)

def diagnostics(analysis, documents, evidence):
    if analysis is None:
        return {"generated": False, "citation_count": 0, "citation_defect": None,
                "errors": [], "missing_reference_signal": False}
    if not isinstance(analysis, dict):
        return {"generated": True, "citation_count": 0, "citation_defect": None,
                "errors": ["Non-object output"], "missing_reference_signal": False}
    errors = validate_analysis(analysis, documents, evidence)
    risks = analysis.get("risks", [])
    risks = risks if isinstance(risks, list) else []
    count = sum(len(r.get("citations", [])) for r in risks if isinstance(r, dict)
                and isinstance(r.get("citations"), list))
    # Signal only: excludes echoed contract clauses and source quotes.
    narrative = " ".join([str(analysis.get("summary", "")),
                          *map(str, analysis.get("open_questions", [])),
                          *[str(r.get("analysis", "")) + " " + str(r.get("limitations", []))
                            for r in risks if isinstance(r, dict)]]).lower()
    gap = bool(re.search(r"manqu|non fourni|pas fourni|absen|insuffisan|non disponible|"
                         r"ne permet pas|impossible|non vérifi|non vérifi|hors.*périmètre", narrative))
    citation_defect = any("preuve inconnue" in e or "citation introuvable" in e
                          or "citation invalide" in e or "aucune preuve citée" in e for e in errors)
    return {"generated": True, "citation_count": count, "citation_defect": citation_defect,
            "errors": errors, "missing_reference_signal": gap}

def delivered_analysis(record):
    return record.get("analysis") if record.get("status") in {"draft", "draft_incomplete"} else None

def mechanical_proxy(case, record, checks):
    rubric = case["rubric"]
    answer = delivered_analysis(record)
    refusal = record["status"] in {"insufficient_evidence", "scope_refused"}
    if rubric.get("expected_abstention"):
        return refusal or (isinstance(answer, dict) and not answer.get("risks")
                           and checks["missing_reference_signal"] and not checks["errors"])
    if not isinstance(answer, dict) or checks["errors"]:
        return False
    risks = answer.get("risks", [])
    if rubric.get("risk_required") and not risks:
        return False
    required = rubric.get("expected_citation")
    if required and not any(c.get("evidence_id") == required for r in risks for c in r.get("citations", [])):
        return False
    if rubric.get("missing_reference") and not checks["missing_reference_signal"]:
        return False
    return True

def summarize(records, cases):
    result = {}
    by_id = {c["id"]: c for c in cases}
    for arm in ("grounded_model", "harness"):
        rows = [r for r in records if r["arm"] == arm]
        delivered = [r for r in rows if delivered_analysis(r) is not None]
        generated = [r for r in rows if r["checks"]["generated"]]
        result[arm] = {
            "attempts": len(rows),
            "runtime_failures": sum(r["status"] == "runtime_error" for r in rows),
            "delivered_analyses": len(delivered),
            "delivery_coverage": len(delivered) / len(rows) if rows else None,
            "generated_citation_defect_responses": sum(r["checks"]["citation_defect"] is True for r in generated),
            "generated_responses": len(generated),
            "delivered_citation_defect_responses": sum(r["checks"]["citation_defect"] is True for r in delivered),
            "delivered_responses_denominator": len(delivered),
            "blocked_validation": sum(r["status"] == "blocked_validation" for r in rows),
            "explicit_refusals": sum(r["status"] in {"insufficient_evidence", "scope_refused"} for r in rows),
            "mechanical_proxy_passes": sum(r["mechanical_proxy_pass"] for r in rows),
            "mechanical_proxy_denominator": len(rows),
            "missing_reference_signal": sum(r["checks"]["missing_reference_signal"] for r in rows
                if by_id[r["case_id"]]["rubric"].get("missing_reference")),
            "missing_reference_attempts": sum(bool(by_id[r["case_id"]]["rubric"].get("missing_reference")) for r in rows),
            "total_seconds": round(sum(r["seconds"] for r in rows), 2),
            "substantive_legal_success_rate": None,
            "overall_hallucination_rate": None,
        }
    result["justinian_comparable"] = False
    result["interpretation"] = ("Exact citation checks and lexical gap signals are not semantic legal grading. "
                                "Blocked answers reduce delivery coverage and are not successful legal reviews. "
                                "Small internal pilot with oracle retrieval; no live-provider or native-file evaluation.")
    return result

def blind_pack(out, records, cases):
    by_id = {c["id"]: c for c in cases}
    shuffled = list(records)
    random.SystemRandom().shuffle(shuffled)
    key, answers, annotations = [], [], []
    for i, row in enumerate(shuffled, 1):
        anon = f"ANSWER-{i:04d}"
        case = by_id[row["case_id"]]
        key.append({"answer_id": anon, "case_id": row["case_id"], "arm": row["arm"], "repeat": row["repeat"]})
        answers.append({"answer_id": anon, "case_id": case["id"], "request": case["request"],
                        "status": row["status"], "analysis": delivered_analysis(row),
                        "rubric": case["rubric"]["human_criteria"]})
        annotations.append({"answer_id": anon, "reviewer": None, "qualified_legal_reviewer": None,
                            "criteria_met": [None] * len(case["rubric"]["human_criteria"]),
                            "hallucination_found": None, "notes": None})
    write_json(out / "blind-answers.json", answers)
    write_json(out / "blind-key.json", key)
    write_json(out / "jurist-annotations.template.json", annotations)

def adjudicate(folder, filename):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    cases = json.loads((folder / "dataset.snapshot.json").read_text(encoding="utf-8"))["cases"]
    counts = {c["id"]: len(c["rubric"]["human_criteria"]) for c in cases}
    keys = json.loads((folder / "blind-key.json").read_text(encoding="utf-8"))
    mapping = {k["answer_id"]: k for k in keys}
    annotations = json.loads(filename.read_text(encoding="utf-8"))
    if len({a.get("answer_id") for a in annotations}) != len(annotations):
        raise ValueError("Duplicate annotations")
    results = {}
    for arm in ("grounded_model", "harness"):
        selected = []
        for a in annotations:
            k = mapping.get(a.get("answer_id"))
            if k is None:
                raise ValueError("Unknown blind answer")
            valid = (bool(a.get("reviewer")) and a.get("qualified_legal_reviewer") is True
                     and type(a.get("hallucination_found")) is bool
                     and len(a.get("criteria_met", [])) == counts[k["case_id"]]
                     and all(type(x) is bool for x in a["criteria_met"]))
            if valid and k["arm"] == arm:
                selected.append(a)
        n = len(selected)
        results[arm] = {"reviewed": n, "expected": sum(k["arm"] == arm for k in keys),
                        "success_rate_among_reviewed": sum(all(a["criteria_met"]) for a in selected) / n if n else None,
                        "hallucination_rate_among_reviewed": sum(a["hallucination_found"] for a in selected) / n if n else None,
                        "complete": n == sum(k["arm"] == arm for k in keys)}
    write_json(folder / "human-results.json", {"manifest_sha256": digest((folder / "manifest.json").read_bytes()),
        "dataset_sha256": manifest["dataset_sha256"], "results": results, "justinian_comparable": False})

def run(args):
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    baseline_prompt = args.baseline_prompt.read_text(encoding="utf-8") if args.baseline_prompt else REVIEW_PROMPT
    cases = dataset["cases"][:args.limit] if args.limit else dataset["cases"]
    args.out.mkdir(parents=True, exist_ok=False)
    cfg = load_config(ROOT / "integrations" / "actelyo-law-harness" / "config.example.toml")
    cfg.update(principal="evaluation-synthetic-only", allowed_matters=["EVAL-001"],
               allow_documents_to_model=True, documents_rights_basis=dataset["rights_basis"],
               allow_search_queries_external=True)
    cfg["model"].update(base_url=args.base_url, name=args.model, timeout_seconds=args.timeout,
                        max_output_tokens=args.max_tokens, allow_remote_documents=args.allow_remote,
                        token_env=args.token_env)
    cfg["sources"] = {"legifrance": {"enabled": True, "rights_basis": dataset["rights_basis"],
                                    "allow_process": True, "allow_display": True}}
    source_root = ROOT / "integrations" / "actelyo-law-harness" / "law_harness"
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": digest(raw),
        "code_revision": args.code_revision,
        "case_ids": [c["id"] for c in cases], "repeats": args.repeats, "model": args.model,
        "base_url": args.base_url, "temperature": 0, "max_output_tokens": args.max_tokens,
        "timeout_seconds": args.timeout, "review_prompt_sha256": digest(REVIEW_PROMPT.encode()),
        "baseline_prompt_sha256": digest(baseline_prompt.encode()),
        "baseline_prompt_file": str(args.baseline_prompt) if args.baseline_prompt else None,
        "service_files_sha256": {p.name: digest(p.read_bytes()) for p in sorted(source_root.glob("*.py"))},
        "retrieval": "fixed public statutory snapshots; oracle fixture, not a live API",
        "contracts": "synthetic", "rubric_author": "internal agent, not independently lawyer validated",
        "model_weights_sha256": None, "baseline": "frozen baseline prompt when supplied; same sources; no planner, no date exclusion, no hard gates",
        "differences": ["harness planning call", "date exclusion", "scope refusal", "exact quotation/identity validation",
                        "identifier-bound schema and prompt", "same-model factual consistency audit"],
        "judges": "mechanical checks only; jurist annotations not yet supplied", "justinian_comparable": False}
    write_json(args.out / "manifest.json", manifest)  # Frozen BEFORE any model call.
    write_json(args.out / "dataset.snapshot.json", {**dataset, "cases": cases})
    (args.out / "baseline-prompt.txt").write_text(baseline_prompt, encoding="utf-8")
    (args.out / "review-prompt.txt").write_text(REVIEW_PROMPT, encoding="utf-8")
    records = []
    for repeat in range(1, args.repeats + 1):
        for case in cases:
            items = [Evidence(**item, rights_basis=dataset["rights_basis"]) for item in dataset["evidence"]
                     if item["source_id"] in case["evidence_ids"]]
            checked = [check_temporal(copy.deepcopy(e), case["request"]["as_of"]) for e in items]
            reference_map = {e.key: e for e in checked}
            # Counterbalance time order across cases/repeats; never parallelize a local model.
            arms = ("grounded_model", "harness") if (repeat + cases.index(case)) % 2 else ("harness", "grounded_model")
            for arm in arms:
                http = RecordingHttp()
                model = Model(cfg, http)
                start = time.perf_counter()
                try:
                    if arm == "harness":
                        report = Harness(cfg, http=http, model=model,
                            connectors={"legifrance": SnapshotConnector(items, case.get("connector_failure", False))}).review(case["request"])
                    else:
                        payload = {**case["request"], "issues": [], "evidence": [e.as_dict() for e in checked]}
                        answer = model.complete(baseline_prompt, payload, schema=REVIEW_SCHEMA)
                        report = {"status": "draft", "analysis": answer, "evidence": [e.as_dict() for e in checked]}
                except HarnessError as exc:
                    refused = arm == "harness" and "Seule la juridiction FR" in str(exc)
                    report = {"status": "scope_refused" if refused else "runtime_error",
                              "analysis": None, "error": str(exc)}
                seconds = round(time.perf_counter() - start, 3)
                check = diagnostics(report.get("analysis"), case["request"]["documents"], reference_map)
                row = {"case_id": case["id"], "repeat": repeat, "arm": arm, "seconds": seconds,
                       "status": report["status"], "analysis": report.get("analysis"),
                       "report": report, "checks": check, "model_calls": http.calls}
                row["mechanical_proxy_pass"] = mechanical_proxy(case, row, check)
                records.append(row)
                with (args.out / "records.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                write_json(args.out / "summary.json", summarize(records, cases))
                print(json.dumps({"case": case["id"], "repeat": repeat, "arm": arm, "status": row["status"],
                                  "seconds": seconds, "citation_defect": check["citation_defect"]}), flush=True)
    blind_pack(args.out, records, cases)
    print(json.dumps({"finished": True, "attempts": len(records), "output": str(args.out)}), flush=True)

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("run")
    cmd.add_argument("--dataset", type=Path, default=Path(__file__).with_name("pilot-fr-v1.json"))
    cmd.add_argument("--baseline-prompt", type=Path, help="Frozen prompt for a stable baseline across harness versions")
    cmd.add_argument("--code-revision", default=None, help="Published code revision recorded before generation")
    cmd.add_argument("--out", type=Path, required=True)
    cmd.add_argument("--model", default="legalya-v30")
    cmd.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    cmd.add_argument("--token-env", default="LM_STUDIO_API_TOKEN")
    cmd.add_argument("--allow-remote", action="store_true")
    cmd.add_argument("--timeout", type=int, default=180)
    cmd.add_argument("--max-tokens", type=int, default=1600)
    cmd.add_argument("--repeats", type=int, default=2)
    cmd.add_argument("--limit", type=int)
    judge = commands.add_parser("adjudicate")
    judge.add_argument("--folder", type=Path, required=True)
    judge.add_argument("--annotations", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        if args.code_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", args.code_revision):
            parser.error("code-revision must be a full lowercase commit SHA")
        if args.repeats < 1 or args.repeats > 10 or args.limit is not None and args.limit < 1:
            parser.error("Positive bounded repeats and limit required")
        run(args)
    else:
        adjudicate(args.folder, args.annotations)

if __name__ == "__main__":
    main()
