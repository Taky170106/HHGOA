"""Machine validation of the 20 benchmark case answers.

Checks (case_output requirement list):
  * exactly the 20 case ids in DATASET/case_pack.csv, one file each, correct names
  * valid JSON, no duplicate case ids
  * every required field of the benchmark schema is present and well-typed
  * every required investigation section is present (record, evidence, findings,
    decision, actions, graph evidence, SAR status, next best action, approval
    route, pre- and post-additional-evidence states)
  * cross-field consistency (SAR flag vs FILE_REPORT, legitimate -> empty
    exposure, enum domains, policy action/route identifiers)
  * ANTI-FABRICATION: every entity id must exist in the dataset, exposure must
    equal the recomputed sum of the affected transactions, and no placeholder
    tokens may appear where a real value is required

Writes cases/validation_report.json and docs/CASE_OUTPUT_VALIDATION.md.
Run:  python scripts/validate_cases.py
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys

import pandas as pd

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "cases")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

TOP_FIELDS = ["case_id", "case", "evidence_requests", "next_best_actions", "sar",
              "stop_reason", "tool_calls", "tokens", "latency_s"]
CASE_FIELDS = ["status", "verdict", "fraud_probability", "pattern", "pattern_description",
               "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
               "connected_device_profiles", "exposure_usd", "evidence",
               "similar_prior_cases", "summary", "written_to_graph", "graph_case_id"]
SAR_FIELDS = ["file", "reason", "narrative", "subjects", "total_amount_usd", "activity_dates"]
NBA_FIELDS = ["initial", "final", "what_changed"]
SECTIONS = ["investigation_record", "findings", "decision", "actions_taken", "graph_evidence",
            "sar_status", "required_approval_route", "pre_additional_evidence_state",
            "post_additional_evidence_state"]
PATTERNS = {"card_testing", "card_not_present_fraud", "card_not_present_new_device",
            "out_of_region_use", "account_takeover", "undocumented", "none"}
STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VERDICTS = {"fraud", "legitimate", "uncertain"}
SOURCES = {"graph", "document", "customer", "external"}
ACTIONS = {"ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD",
           "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH",
           "BLOCK_CARD", "BLOCK_ALL_CARDS", "GENERATE_REPORT", "CREATE_CASE", "FILE_REPORT",
           "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD"}
ROUTES = {"auto", "L1", "L2"}
REQ_TYPES = {"customer_validation", "step_up_auth", "analyst_info"}
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|dummy|placeholder|lorem ipsum|xxx+)\b", re.I)
PLACEHOLDER_EQ = {"unknown", "test", "n/a", "-", "none provided", "tbd", "todo"}
# legitimate vocabulary that must not be mistaken for placeholders
OK_WORDS = {"card_testing", "card testing", "card-test", "test-then-use"}


def main():
    errors, warns, per_case = [], [], []
    pack = list(csv.DictReader(open(os.path.join(ROOT, "DATASET", "case_pack.csv"),
                                    encoding="utf-8")))
    expected = [r["case_id"] for r in pack]
    pack_by_id = {r["case_id"]: r for r in pack}

    # ---- dataset ground truth for anti-fabrication checks ----
    tx = pd.read_csv(os.path.join(ROOT, "data", "vertices", "transaction.csv"),
                     usecols=["txn_id", "amount"], dtype=str)
    known_txns = set(tx["txn_id"])
    amount = dict(zip(tx["txn_id"], pd.to_numeric(tx["amount"])))
    cards = set(pd.read_csv(os.path.join(ROOT, "data", "vertices", "card.csv"),
                            usecols=["card_id"], dtype=str)["card_id"])
    customers = set(pd.read_csv(os.path.join(ROOT, "data", "vertices", "customer.csv"),
                                usecols=["customer_id"], dtype=str)["customer_id"])
    cases_cc = set(pd.read_csv(os.path.join(ROOT, "data", "vertices", "closed_case.csv"),
                               usecols=["case_id"], dtype=str)["case_id"])

    files = sorted(f for f in os.listdir(CASES) if f.endswith(".json") and
                   f.startswith("HHG-"))
    if len(files) != 20:
        errors.append("expected 20 case files, found %d" % len(files))
    got = [f[:-5] for f in files]
    if sorted(got) != sorted(expected):
        errors.append("file names do not match case_pack.csv: missing=%s extra=%s"
                      % (sorted(set(expected) - set(got)), sorted(set(got) - set(expected))))
    if len(set(got)) != len(got):
        errors.append("duplicate case file names")

    for cid in expected:
        path = os.path.join(CASES, "%s.json" % cid)
        ce = []
        if not os.path.exists(path):
            errors.append("%s: file missing" % cid)
            per_case.append({"case_id": cid, "ok": False, "errors": ["file missing"]})
            continue
        try:
            a = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            errors.append("%s: invalid JSON: %s" % (cid, e))
            per_case.append({"case_id": cid, "ok": False, "errors": ["invalid JSON"]})
            continue

        if a.get("case_id") != cid:
            ce.append("case_id field %r != file name" % a.get("case_id"))
        for f in TOP_FIELDS:
            if f not in a:
                ce.append("missing top-level field %s" % f)
        c = a.get("case", {})
        for f in CASE_FIELDS:
            if f not in c:
                ce.append("missing case field %s" % f)
        s = a.get("sar", {})
        for f in SAR_FIELDS:
            if f not in s:
                ce.append("missing sar field %s" % f)
        n = a.get("next_best_actions", {})
        for f in NBA_FIELDS:
            if f not in n:
                ce.append("missing next_best_actions field %s" % f)
        for f in SECTIONS:
            if f not in a:
                ce.append("missing required section %s" % f)

        # ---- enums / types ----
        if c.get("verdict") not in VERDICTS:
            ce.append("verdict %r not in enum" % c.get("verdict"))
        if c.get("status") not in STATUSES:
            ce.append("status %r not in enum" % c.get("status"))
        if c.get("pattern") not in PATTERNS:
            ce.append("pattern %r not in enum" % c.get("pattern"))
        fp = c.get("fraud_probability")
        if not isinstance(fp, (int, float)) or not (0 <= fp <= 1):
            ce.append("fraud_probability %r out of range" % fp)
        if c.get("pattern") == "undocumented" and len(c.get("pattern_description", "")) < 40:
            ce.append("pattern_description required for undocumented pattern")
        if c.get("pattern") != "undocumented" and c.get("pattern_description") != "":
            ce.append("pattern_description must be empty for pattern %s" % c.get("pattern"))

        # ---- evidence ----
        ev = c.get("evidence", [])
        if not isinstance(ev, list) or not ev:
            ce.append("case.evidence must be a non-empty list")
            ev = []
        ev_ids = []
        for i, e in enumerate(ev):
            for f in ("claim", "source", "ref", "entity_ids"):
                if f not in e:
                    ce.append("evidence[%d] missing %s" % (i, f))
            if e.get("source") not in SOURCES:
                ce.append("evidence[%d] source %r not in enum" % (i, e.get("source")))
            if not e.get("claim"):
                ce.append("evidence[%d] empty claim" % i)
            ev_ids.append(e.get("evidence_id", "EV-%02d" % (i + 1)))
            for x in e.get("entity_ids", []):
                x = str(x)
                if x.startswith("HHG-"):
                    if x not in pack_by_id:
                        ce.append("evidence[%d] unknown case id %s" % (i, x))
                elif x.startswith("CC-"):
                    if x not in cases_cc:
                        ce.append("evidence[%d] fabricated closed-case id %s" % (i, x))
                elif re.match(r"^\d{6,}$", x):
                    if x not in known_txns:
                        ce.append("evidence[%d] fabricated transaction id %s" % (i, x))
                elif x.startswith("C"):
                    if x not in cards and x not in customers:
                        ce.append("evidence[%d] fabricated card/customer id %s" % (i, x))

        # ---- affected transactions + exposure recomputation ----
        aff = c.get("affected_txn_ids", [])
        if not isinstance(aff, list):
            ce.append("affected_txn_ids must be a list")
            aff = []
        for t in aff:
            if str(t) not in known_txns:
                ce.append("affected_txn_ids contains fabricated id %s" % t)
        exp = c.get("exposure_usd", 0)
        if c.get("verdict") == "legitimate":
            if aff:
                ce.append("legitimate verdict must have empty affected_txn_ids")
            if exp not in (0, 0.0):
                ce.append("legitimate verdict must have exposure_usd 0")
            if s.get("file"):
                ce.append("legitimate verdict must not file a SAR")
        elif aff:
            want = round(sum(float(amount.get(str(t), 0)) for t in aff), 2)
            if abs(want - float(exp)) > 0.01:
                ce.append("exposure_usd %.2f != recomputed %.2f from affected_txn_ids"
                          % (float(exp), want))
        if c.get("first_suspicious_txn_id") and str(c["first_suspicious_txn_id"]) not in known_txns:
            ce.append("first_suspicious_txn_id %s not in dataset" % c["first_suspicious_txn_id"])
        for x in c.get("connected_card_ids", []):
            if str(x) not in cards:
                ce.append("connected_card_ids contains fabricated id %s" % x)
        for x in c.get("similar_prior_cases", []):
            if str(x) not in cases_cc:
                ce.append("similar_prior_cases contains fabricated id %s" % x)

        # ---- actions / routes ----
        for stage in ("initial", "final"):
            acts = n.get(stage, [])
            if not isinstance(acts, list) or not acts:
                ce.append("next_best_actions.%s must be a non-empty list" % stage)
                continue
            for i, x in enumerate(acts):
                if x.get("action") not in ACTIONS:
                    ce.append("%s[%d] action %r not a policy action" % (stage, i, x.get("action")))
                if x.get("route") not in ROUTES:
                    ce.append("%s[%d] route %r invalid" % (stage, i, x.get("route")))
                if not x.get("reason"):
                    ce.append("%s[%d] missing reason" % (stage, i))
                elif not re.search(r"\bR\d{1,2}\b|Section", x["reason"]):
                    ce.append("%s[%d] reason does not cite a policy rule" % (stage, i))

        # ---- SAR consistency ----
        if "FILE_REPORT" in [x.get("action") for x in n.get("final", [])]:
            if not s.get("file"):
                ce.append("FILE_REPORT in final actions but sar.file is false")
        if s.get("file"):
            if not s.get("narrative") or len(s["narrative"].split()) < 60:
                ce.append("sar.file true requires a substantive narrative")
            if not s.get("subjects"):
                ce.append("sar.file true requires subjects")
            if not s.get("activity_dates") or len(s["activity_dates"]) != 2:
                ce.append("sar.file true requires activity_dates [start, end]")
            if not s.get("total_amount_usd"):
                ce.append("sar.file true requires total_amount_usd")
        else:
            if s.get("narrative") or s.get("subjects") or s.get("total_amount_usd") or \
                    s.get("activity_dates"):
                ce.append("sar.file false must have empty narrative/subjects/dates and 0 amount")

        # ---- required investigation sections ----
        ir = a.get("investigation_record", [])
        if len(ir) < 9:
            ce.append("investigation_record needs the 9 CASE->APPROVAL_ROUTE steps (has %d)"
                      % len(ir))
        if not a.get("findings"):
            ce.append("findings must be non-empty")
        dec = a.get("decision", {})
        if not dec.get("decision") or not dec.get("rationale") or \
                not dec.get("supporting_evidence_ids"):
            ce.append("decision must carry decision + rationale + supporting_evidence_ids")
        if not a.get("actions_taken"):
            ce.append("actions_taken must be non-empty")
        ge = a.get("graph_evidence", {})
        if not ge.get("queries") or not ge.get("entities") or not ge.get("edges"):
            ce.append("graph_evidence must carry queries + entities + edges")
        if not a.get("sar_status"):
            ce.append("sar_status missing")
        if not a.get("required_approval_route"):
            ce.append("required_approval_route missing")
        pre = a.get("pre_additional_evidence_state", {})
        post = a.get("post_additional_evidence_state", {})
        for k in ("current_evidence", "current_findings", "preliminary_decision",
                  "preliminary_next_best_action", "required_approval_route"):
            if k not in pre:
                ce.append("pre_additional_evidence_state missing %s" % k)
        for k in ("additional_evidence_received", "updated_evidence", "updated_findings",
                  "updated_decision", "updated_next_best_action", "updated_approval_route"):
            if k not in post:
                ce.append("post_additional_evidence_state missing %s" % k)
        if post.get("additional_evidence_received") is False and a.get("evidence_requests"):
            ce.append("evidence_requests present but additional_evidence_received is false")
        if post.get("additional_evidence_received") is True and not a.get("evidence_requests"):
            ce.append("additional_evidence_received true without evidence_requests")
        if not isinstance(a.get("evidence_requests"), list):
            ce.append("evidence_requests must be a list")
        else:
            for i, r in enumerate(a["evidence_requests"]):
                if r.get("type") not in REQ_TYPES:
                    ce.append("evidence_requests[%d] type %r invalid" % (i, r.get("type")))
                for k in ("asked_after_step", "assumed_response"):
                    if k not in r:
                        ce.append("evidence_requests[%d] missing %s" % (i, k))
        if not a.get("stop_reason"):
            ce.append("stop_reason missing")
        if not isinstance(a.get("tool_calls"), int) or a.get("tool_calls", 0) < 1:
            ce.append("tool_calls must be a positive integer")
        if not isinstance(a.get("tokens"), int):
            ce.append("tokens must be an integer")
        if not isinstance(a.get("latency_s"), (int, float)) or a.get("latency_s", 0) <= 0:
            ce.append("latency_s must be a positive number")

        # ---- placeholder scan over free text ----
        def scan(text, where):
            if not isinstance(text, str):
                return
            if text.strip().lower() in PLACEHOLDER_EQ and text.strip().lower() not in OK_WORDS:
                ce.append("placeholder value %r in %s" % (text, where))
            m = PLACEHOLDER.search(text)
            if m and m.group(0).lower() not in OK_WORDS:
                ce.append("placeholder token %r in %s" % (m.group(0), where))

        scan(c.get("summary", ""), "case.summary")
        scan(c.get("pattern_description", ""), "case.pattern_description")
        scan(a.get("stop_reason", ""), "stop_reason")
        scan(s.get("reason", ""), "sar.reason")
        if s.get("file"):
            scan(s.get("narrative", ""), "sar.narrative")
        for i, x in enumerate(n.get("final", [])):
            scan(x.get("reason", ""), "final[%d].reason" % i)
        for i, e in enumerate(ev):
            scan(e.get("claim", ""), "evidence[%d].claim" % i)

        ok = not ce
        errors.extend("%s: %s" % (cid, e) for e in ce)
        per_case.append({"case_id": cid, "ok": ok, "errors": ce,
                         "verdict": c.get("verdict"), "pattern": c.get("pattern"),
                         "fraud_probability": c.get("fraud_probability"),
                         "exposure_usd": c.get("exposure_usd"),
                         "evidence_items": len(ev),
                         "sar_file": s.get("file"),
                         "next_best_action": (n.get("final") or [{}])[0].get("action", ""),
                         "approval_route": a.get("required_approval_route", []),
                         "additional_evidence_received": post.get("additional_evidence_received"),
                         "tool_calls": a.get("tool_calls")})

    # ---- placeholder scan over every case file text ----
    for f in files:
        txt = open(os.path.join(CASES, f), encoding="utf-8").read()
        for bad in ("TODO", "TBD", "FIXME", "lorem ipsum"):
            if bad.lower() in txt.lower():
                errors.append("%s: contains placeholder text %r" % (f, bad))

    passed = sum(1 for x in per_case if x["ok"])
    report = {
        "expected_case_ids": expected,
        "expected_count": 20,
        "files_found": len(files),
        "files_matching_case_pack": sorted(got) == sorted(expected),
        "cases_passed": passed,
        "cases_failed": 20 - passed,
        "total_errors": len(errors),
        "errors": errors,
        "warnings": warns,
        "per_case": per_case,
        "status": "PASS" if (passed == 20 and len(errors) == 0 and len(files) == 20) else "FAIL",
    }
    with open(os.path.join(CASES, "validation_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    # ---- markdown ----
    lines = ["# Case Output Validation", "",
             "Generated by `python scripts/validate_cases.py`.", "",
             "| Metric | Value |", "|---|---|",
             "| Expected cases (case_pack.csv) | 20 |",
             "| Answer files found | %d |" % len(files),
             "| Filenames match case_pack.csv | %s |" % ("yes" if sorted(got) == sorted(expected)
                                                         else "NO"),
             "| Cases passing all checks | %d / 20 |" % passed,
             "| Total errors | %d |" % len(errors),
             "| **Status** | **%s** |" % report["status"], "",
             "## Checks performed", "",
             "- exactly 20 case ids from `DATASET/case_pack.csv`, one file each, names match",
             "- valid JSON, no duplicate case ids",
             "- all benchmark fields present (`case`, `sar`, `next_best_actions`, "
             "`evidence_requests`, `stop_reason`, `tool_calls`, `tokens`, `latency_s`)",
             "- all investigation sections present (investigation record, evidence, findings, "
             "decision, actions taken, graph evidence, SAR status, next best action, approval "
             "route, pre- and post-additional-evidence states)",
             "- enum domains (verdict/status/pattern/source/action/route/evidence request type)",
             "- SAR flag agrees with `FILE_REPORT` in final actions; legitimate verdict implies "
             "empty exposure and no SAR",
             "- **every entity id exists in the dataset** (transactions, cards, customers, "
             "closed cases)",
             "- **`exposure_usd` recomputed from `affected_txn_ids` and matched**",
             "- every action reason cites a policy rule (R1-R10 or Section)",
             "- no placeholder tokens (TODO/TBD/dummy/unknown/test) where a real value is "
             "required", "",
             "## Per-case results", "",
             "| Case | Verdict | Pattern | P | Exposure | Evidence | SAR | NBA | Routes | OK |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for x in per_case:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            x.get("case_id"), x.get("verdict"), x.get("pattern"),
            x.get("fraud_probability"), x.get("exposure_usd"), x.get("evidence_items"),
            x.get("sar_file"), x.get("next_best_action"),
            ",".join(x.get("approval_route", []) or []), "OK" if x["ok"] else "FAIL"))
    lines += ["", "## Errors", ""]
    lines += ["- `%s`" % e for e in errors] or ["- none"]
    with open(os.path.join(DOCS, "CASE_OUTPUT_VALIDATION.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("files=%d/20  passed=%d/20  errors=%d  status=%s"
          % (len(files), passed, len(errors), report["status"]))
    for e in errors[:25]:
        print("  ERROR", e)
    if len(errors) > 25:
        print("  ... %d more" % (len(errors) - 25))
    print("WROTE cases/validation_report.json and docs/CASE_OUTPUT_VALIDATION.md")
    return report


if __name__ == "__main__":
    main()
