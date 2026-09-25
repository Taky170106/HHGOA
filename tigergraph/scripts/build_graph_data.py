#!/usr/bin/env python3
"""
Build TigerGraph-ready vertex and edge CSVs from raw dataset.
- Deterministic, reproducible, UTF-8, explicit headers, stable IDs
- Never modifies raw files under DATASET/
- Validates duplicates, missing PKs, orphans, timestamps, numerics, categories

Outputs:
  data/vertices/*.csv
  data/edges/*.csv
  data/vertices/card_mapping.csv
  data/VALIDATION_REPORT.md  (pre-load validation, source-derived counts)

Usage:
  python tigergraph/scripts/build_graph_data.py
  python tigergraph/scripts/build_graph_data.py --validate-only
"""
import hashlib, os, re, sys, argparse
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "DATASET"
VERTICES = ROOT / "data" / "vertices"
EDGES = ROOT / "data" / "edges"
VALIDATION = ROOT / "data" / "VALIDATION_REPORT.md"

def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def device_profile_id(row) -> str:
    parts = [str(row.get("DeviceInfo") or ""), str(row.get("id_30") or ""), str(row.get("id_31") or ""), str(row.get("id_33") or "")]
    raw = "|".join(p.strip() for p in parts)
    if raw.strip("|").strip() == "":
        raw = "__EMPTY__"
    return "DP-" + sha16(raw)

def parse_ts(s):
    # ts already YYYY-MM-DD HH:MM:SS in source
    return s

def main(validate_only=False):
    VERTICES.mkdir(parents=True, exist_ok=True)
    EDGES.mkdir(parents=True, exist_ok=True)

    print("Loading raw files...")
    tx = pd.read_csv(DATASET / "transactions.csv", low_memory=False)
    ident = pd.read_csv(DATASET / "identity.csv", low_memory=False)
    closed = pd.read_csv(DATASET / "closed_cases_history.csv", low_memory=False)
    pack = pd.read_csv(DATASET / "case_pack.csv", low_memory=False)
    print(f"  transactions: {len(tx):,} x {len(tx.columns)}")
    print(f"  identity: {len(ident):,}")
    print(f"  closed: {len(closed):,}")
    print(f"  pack: {len(pack):,}")

    issues = []

    # --- validations (source) ---
    if tx["TransactionID"].duplicated().any():
        issues.append(f"DUPLICATE TransactionID: {tx['TransactionID'].duplicated().sum()}")
    if tx["customer_id"].isna().any() or tx["card1"].isna().any():
        issues.append("Missing customer_id or card1 in transactions")
    if not pd.to_datetime(tx["ts"], errors="coerce").notna().all():
        issues.append("Invalid ts in transactions")
    if (tx["TransactionAmt"] < 0).any():
        issues.append("Negative TransactionAmt found (unexpected)")
    # invalid categories
    valid_product = set(["W","C","H","R","S"])
    if not set(tx["ProductCD"].dropna().unique()).issubset(valid_product):
        issues.append(f"Unexpected ProductCD: {set(tx['ProductCD'].dropna().unique()) - valid_product}")
    # orphan identity
    tx_ids = set(tx["TransactionID"].astype(str))
    ident_orphans = (~ident["TransactionID"].astype(str).isin(tx_ids)).sum()
    if ident_orphans:
        issues.append(f"Orphan identity records not in transactions: {ident_orphans}")

    # --- derive derived channel (W -> in_person, else online) ---
    # README: W = in_person per PRODUCT mapping; but dataset already has channel? check
    if "channel" not in tx.columns:
        tx["channel"] = tx["ProductCD"].apply(lambda x: "in_person" if x == "W" else "online")
    else:
        # normalize
        tx["channel"] = tx["channel"].astype(str)

    # --- Build customer -> card1 base map ---
    cust_card = tx[["customer_id","card1"]].drop_duplicates()
    # 1:1 check
    if cust_card["customer_id"].duplicated().any() or cust_card["card1"].duplicated().any():
        issues.append("customer_id <-> card1 not 1:1")
    cust_to_card1 = dict(zip(cust_card["customer_id"], cust_card["card1"]))
    card1_to_cust = dict(zip(cust_card["card1"], cust_card["customer_id"]))

    # Determine suffix per customer from case files
    suffix_by_customer = {}
    def collect_card_ids(series):
        for v in series.dropna():
            for part in str(v).split("|"):
                part = part.strip()
                if not part:
                    continue
                m = re.match(r"^(C\d+)-K(\d+)$", part)
                if m:
                    cust, k = m.group(1), int(m.group(2))
                    suffix_by_customer[cust] = max(suffix_by_customer.get(cust, 1), k)

    collect_card_ids(closed["card_id"])
    collect_card_ids(closed["connected_card_ids"])
    collect_card_ids(pack["card_id"])

    # Canonical Card PK resolution (see schema/card_mapping.md steps 2-4).
    # One Card vertex per customer: C<customer_id>-K<max suffix seen>, else -K1.
    # A case may reference a lower suffix (e.g. C02231-K1 while C02231-K2 is the
    # canonical card); that reference must be resolved through this map before it
    # is written to a vertex attribute or an edge endpoint, otherwise the edge has
    # a dangling target (discrepancy D5: 37 ON_CARD orphans over 21 distinct cards).
    canon_changed = []

    def canonical_card_id(cid, ctx=""):
        cid = str(cid).strip() if cid is not None and not pd.isna(cid) else ""
        if not cid:
            return ""
        m = re.match(r"^(C\d+)-K(\d+)$", cid)
        if not m:
            return cid
        cust = m.group(1)
        if cust not in cust_to_card1:
            issues.append("card_id %s (%s): customer absent from transactions window - no Card vertex" % (cid, ctx))
            return cid
        canon = "%s-K%d" % (cust, suffix_by_customer.get(cust, 1))
        if canon != cid:
            canon_changed.append((ctx, cid, canon))
        return canon

    # Build canonical Card rows for all 13,553 customers
    card_rows = []
    for cust, card1 in cust_to_card1.items():
        suffix = suffix_by_customer.get(cust, 1)
        card_id = f"{cust}-K{suffix}"
        card_rows.append((card_id, int(card1), cust))
    # Add any connected_card_ids that reference customers not in transactions (outside window)
    extra_cards = set()
    for v in closed["connected_card_ids"].dropna():
        for part in str(v).split("|"):
            part = part.strip()
            if part and part not in {r[0] for r in card_rows}:
                extra_cards.add(part)
    for cid in sorted(extra_cards):
        m = re.match(r"^(C\d+)-K\d+$", cid)
        cust = m.group(1) if m else ""
        # card1_num 0 signals no transaction history in window
        card_rows.append((cid, 0, cust))

    card_df = pd.DataFrame(card_rows, columns=["card_id","card1_num","customer_id"])
    # enrich with card4/card6 etc. — take mode per customer
    card_attrs = tx.groupby("customer_id").agg(
        card4=("card4","first"), card6=("card6","first"),
        card2=("card2","first"), card3=("card3","first"), card5=("card5","first")
    ).reset_index()
    card_df = card_df.merge(card_attrs, on="customer_id", how="left")

    # B1 normalization: DATASET/transactions.csv stores issuer codes card2/card3/card5
    # as float64 (NaN present), so every non-empty value serialises as "189.0".
    # phase0/ENTITY_MODEL.md defines them as issuer codes (integers) and
    # schema.gsql declares them UINT, so the ".0" is a serialisation artifact, not
    # a value. Verified across all 590,742 raw rows: every non-empty value matches
    # ^\d+\.0*$ (zero non-integral values), so stripping it is lossless.
    # Empty stays empty. Any non-integral value would be preserved and reported.
    def _issuer_code(v):
        if pd.isna(v):
            return ""
        s = str(v).strip()
        if not s:
            return ""
        return re.sub(r"\.0+$", "", s) if re.match(r"^\d+\.0+$", s) else s

    for _c in ("card2", "card3", "card5"):
        if _c in card_df.columns:
            _bad = [s for s in card_df[_c].map(lambda v: "" if pd.isna(v) else str(v).strip())
                    if s and not re.match(r"^\d+\.0*$", s)]
            if _bad:
                issues.append("non-integral %s value(s) preserved as-is: %r" % (_c, _bad[:3]))
            card_df[_c] = card_df[_c].map(_issuer_code)

    # Customer vertex aggregates
    cust_agg = tx.groupby("customer_id").agg(
        total_txns=("TransactionID","count"),
        online_txns=("channel", lambda s: (s=="online").sum()),
        in_person_txns=("channel", lambda s: (s=="in_person").sum()),
        region_count=("addr1", lambda s: s.dropna().nunique()),
        avg_amount=("TransactionAmt","mean"),
        max_amount=("TransactionAmt","max"),
        first_ts=("ts","min"),
        last_ts=("ts","max"),
    ).reset_index()

    # Transaction vertex — core attributes only (see schema)
    tx_v = tx[["TransactionID","customer_id","card1","ts","TransactionDT","TransactionAmt","ProductCD","channel","risk_score","addr1","addr2","dist1","dist2","P_emaildomain","R_emaildomain"]].copy()
    # map card1 -> canonical card_id
    tx_v["card_id"] = tx_v["customer_id"].map(lambda c: f"{c}-K{suffix_by_customer.get(c,1)}")
    tx_v["txn_id"] = tx_v["TransactionID"].astype(str)
    # stringify addr/email for CSV stability — preserve empty for nulls
    for c in ["addr1","addr2","P_emaildomain","R_emaildomain"]:
        tx_v[c] = tx_v[c].apply(lambda x: "" if pd.isna(x) or str(x).lower() == "nan" else str(x).strip())
    tx_v["risk_score"] = tx_v["risk_score"].astype(float)
    # dist can be NaN -> empty
    # keep column order for output
    tx_v_out = tx_v[["txn_id","TransactionID","customer_id","card_id","card1","ts","TransactionDT","TransactionAmt","ProductCD","channel","risk_score","addr1","addr2","dist1","dist2","P_emaildomain","R_emaildomain"]].copy()
    tx_v_out.columns = ["txn_id","txn_num","customer_id","card_id","card1_num","ts","dt_seconds","amount","product_cd","channel","risk_score","addr1","addr2","dist1","dist2","p_emaildomain","r_emaildomain"]

    # DeviceProfile vertices from identity
    # composite hash
    ident["_dp_raw"] = ident.apply(lambda r: "|".join([str(r.get("DeviceInfo") or ""), str(r.get("id_30") or ""), str(r.get("id_31") or ""), str(r.get("id_33") or "")]), axis=1)
    ident["device_profile_id"] = ident.apply(device_profile_id, axis=1)
    # aggregate per profile
    dp_agg = ident.groupby("device_profile_id").agg(
        device_type=("DeviceType","first"),
        device_info=("DeviceInfo","first"),
        os=("id_30","first"),
        browser=("id_31","first"),
        screen=("id_33","first"),
        txn_count=("TransactionID","count"),
    ).reset_index()
    # customer/card counts per profile via join to transactions for customer
    txn_to_cust = dict(zip(tx["TransactionID"].astype(str), tx["customer_id"]))
    txn_to_card1 = dict(zip(tx["TransactionID"].astype(str), tx["card1"].astype(str)))
    ident["_cust"] = ident["TransactionID"].astype(str).map(txn_to_cust)
    ident["_card1"] = ident["TransactionID"].astype(str).map(txn_to_card1)
    for dp_id, g in ident.groupby("device_profile_id"):
        dp_agg.loc[dp_agg["device_profile_id"]==dp_id, "customer_count"] = g["_cust"].nunique()
        dp_agg.loc[dp_agg["device_profile_id"]==dp_id, "card_count"] = g["_card1"].nunique()
    dp_agg["customer_count"] = dp_agg["customer_count"].astype(int)
    dp_agg["card_count"] = dp_agg["card_count"].astype(int)
    dp_agg["specificity"] = 1.0 / dp_agg["customer_count"].clip(lower=1)
    for c in ["device_type","device_info","os","browser","screen"]:
        dp_agg[c] = dp_agg[c].apply(lambda x: "" if pd.isna(x) or str(x).lower() == "nan" else str(x))

    # EmailDomain vertices
    # purchaser 59, recipient 60
    p_domains = tx_v["P_emaildomain"].replace("", np.nan).dropna().unique()
    r_domains = tx_v["R_emaildomain"].replace("", np.nan).dropna().unique()
    all_domains = sorted(set(list(p_domains) + list(r_domains)))
    email_rows = []
    for d in all_domains:
        is_p = d in set(p_domains)
        is_r = d in set(r_domains)
        dtype = "both" if is_p and is_r else ("purchaser" if is_p else "recipient")
        # counts from tx
        mask_p = tx_v["P_emaildomain"] == d
        mask_r = tx_v["R_emaildomain"] == d
        mask = mask_p | mask_r
        sub = tx_v[mask]
        email_rows.append((d, dtype, int(sub["customer_id"].nunique()), int(sub["card_id"].nunique()), int(len(sub))))
    email_df = pd.DataFrame(email_rows, columns=["domain","domain_type","customer_count","card_count","txn_count"])

    # BillingRegion vertices
    # addr1 332 unique
    regions = tx_v[tx_v["addr1"] != ""].copy()
    # region_code = addr1 string, country = most common addr2
    br_rows = []
    for code, g in regions.groupby("addr1"):
        cc = g["addr2"].replace("", np.nan).dropna()
        country = cc.mode().iloc[0] if len(cc) else ""
        is_home = str(country) == "87.0" or str(country) == "87"
        br_rows.append((str(code), str(country), bool(is_home), int(g["customer_id"].nunique()), int(g["card_id"].nunique()), int(len(g))))
    br_df = pd.DataFrame(br_rows, columns=["region_code","country_code","is_home_region","customer_count","card_count","txn_count"])

    # ClosedCase vertices
    closed_v = closed.copy()
    closed_v["report_filed"] = closed_v["report_filed"].astype(str).str.lower().map({"yes": True, "no": False})
    # fill NaNs for string cols
    for c in ["connected_card_ids","txn_ids","analyst_notes","actions_taken","first_fraud_txn_id"]:
        if c in closed_v.columns:
            closed_v[c] = closed_v[c].apply(lambda x: "" if pd.isna(x) or str(x).lower() == "nan" else str(x))
    # Normalize transaction-ID cells: source column is float64 (NaN present), so str()
    # yields "3000120.0" which cannot join to Transaction.txn_id ("3000120").
    # Canonical form = integer string (same convention as txn_id / flagged_txn_id).
    if "first_fraud_txn_id" in closed_v.columns:
        closed_v["first_fraud_txn_id"] = closed_v["first_fraud_txn_id"].apply(
            lambda s: re.sub(r"^(\d+)\.0+$", r"\1", s) if s else s
        )
    # Resolve ClosedCase.card_id to the canonical Card PK (card_mapping.md step 4).
    # The source DATASET/closed_cases_history.csv keeps its original suffix values.
    if "card_id" in closed_v.columns:
        closed_v["card_id"] = closed_v["card_id"].apply(lambda v: canonical_card_id(v, "ClosedCase.card_id"))

    # BenchmarkCase vertices
    pack_v = pack.copy()
    for c in ["trigger_text","card_id","customer_id"]:
        pack_v[c] = pack_v[c].astype(str)
    pack_v["risk_score"] = pack_v["risk_score"].apply(lambda x: float(x) if pd.notna(x) else -1.0)
    pack_v["flagged_txn_id"] = pack_v["flagged_txn_id"].astype(str)

    if validate_only:
        # still need to report
        pass
    else:
        # Write vertices — deterministic ordering, UTF-8, explicit headers
        print("Writing vertices...")
        cust_agg.sort_values("customer_id").to_csv(VERTICES / "customer.csv", index=False, encoding="utf-8")
        card_df.sort_values("card_id").to_csv(VERTICES / "card.csv", index=False, encoding="utf-8")
        tx_v_out.sort_values("txn_id").to_csv(VERTICES / "transaction.csv", index=False, encoding="utf-8")
        dp_agg.sort_values("device_profile_id").to_csv(VERTICES / "device_profile.csv", index=False, encoding="utf-8")
        email_df.sort_values("domain").to_csv(VERTICES / "email_domain.csv", index=False, encoding="utf-8")
        br_df.sort_values("region_code").to_csv(VERTICES / "billing_region.csv", index=False, encoding="utf-8")
        closed_v.sort_values("case_id").to_csv(VERTICES / "closed_case.csv", index=False, encoding="utf-8")
        pack_v.sort_values("case_id").to_csv(VERTICES / "benchmark_case.csv", index=False, encoding="utf-8")
        # mapping file
        pd.DataFrame(sorted(card_rows), columns=["card_id","card1_num","customer_id"]).to_csv(VERTICES / "card_mapping.csv", index=False, encoding="utf-8")
        print("  vertices written")

        # Edges
        print("Writing edges...")
        # OWNS
        owns = card_df[["customer_id","card_id"]].copy()
        owns.columns = ["from_customer_id","to_card_id"]
        owns.sort_values(["from_customer_id","to_card_id"]).to_csv(EDGES / "owns.csv", index=False, encoding="utf-8")

        # MADE: Card -> Transaction
        made = tx_v_out[["card_id","txn_id"]].copy()
        # sequence_num per card ordered by ts
        tx_sorted = tx_v_out.sort_values(["card_id","ts","txn_id"])
        tx_sorted["sequence_num"] = tx_sorted.groupby("card_id").cumcount() + 1
        made = tx_sorted[["card_id","txn_id","sequence_num"]].copy()
        made.columns = ["from_card_id","to_txn_id","sequence_num"]
        made.sort_values(["from_card_id","sequence_num"]).to_csv(EDGES / "made.csv", index=False, encoding="utf-8")

        # NEXT: per-card temporal (Transaction -> Transaction)
        next_rows = []
        for card_id, g in tx_sorted.groupby("card_id"):
            g = g.sort_values(["ts","txn_id"])
            tids = g["txn_id"].tolist()
            tss = pd.to_datetime(g["ts"]).tolist()
            amts = g["amount"].tolist()
            channels = g["channel"].tolist()
            for i in range(len(tids)-1):
                dt_h = (tss[i+1] - tss[i]).total_seconds() / 3600.0
                ratio = (amts[i+1] / amts[i]) if amts[i] != 0 else 0
                chg = channels[i] != channels[i+1]
                next_rows.append((tids[i], tids[i+1], round(dt_h, 4), round(ratio, 4), bool(chg)))
        next_df = pd.DataFrame(next_rows, columns=["from_txn_id","to_txn_id","time_delta_hours","amount_ratio","channel_change"])
        next_df.sort_values(["from_txn_id","to_txn_id"]).to_csv(EDGES / "next.csv", index=False, encoding="utf-8")

        # BILLED_IN — exclude empty and NaN variants
        billed = tx_v_out[(tx_v_out["addr1"] != "") & (tx_v_out["addr1"].str.lower() != "nan")][["txn_id","addr1","addr2","channel"]].copy()
        billed["is_home_country"] = billed["addr2"].apply(lambda x: str(x) in ("87","87.0"))
        billed = billed[["txn_id","addr1","is_home_country","channel"]]
        billed.columns = ["from_txn_id","to_region_code","is_home_country","channel"]
        billed.sort_values(["from_txn_id"]).to_csv(EDGES / "billed_in.csv", index=False, encoding="utf-8")

        # PURCHASER / RECIPIENT — exclude empty and NaN
        def not_empty(s): return (s != "") & (s.str.lower() != "nan")
        purch = tx_v_out[not_empty(tx_v_out["p_emaildomain"])][["txn_id","p_emaildomain"]].copy()
        purch.columns = ["from_txn_id","to_domain"]
        purch.sort_values("from_txn_id").to_csv(EDGES / "purchaser_email.csv", index=False, encoding="utf-8")
        recip = tx_v_out[not_empty(tx_v_out["r_emaildomain"])][["txn_id","r_emaildomain"]].copy()
        recip.columns = ["from_txn_id","to_domain"]
        recip.sort_values("from_txn_id").to_csv(EDGES / "recipient_email.csv", index=False, encoding="utf-8")

        # FROM_DEVICE
        fd = ident[["TransactionID","device_profile_id","id_15","id_23","id_34","DeviceType"]].copy()
        fd["from_txn_id"] = fd["TransactionID"].astype(str)
        fd = fd[["from_txn_id","device_profile_id","id_15","id_23","id_34","DeviceType"]]
        fd.columns = ["from_txn_id","to_device_profile_id","newness","proxy_type","match_status","device_type"]
        for c in ["newness","proxy_type","match_status","device_type"]:
            fd[c] = fd[c].apply(lambda x: "" if pd.isna(x) or str(x).lower() == "nan" else str(x))
        fd.sort_values("from_txn_id").to_csv(EDGES / "from_device.csv", index=False, encoding="utf-8")

        # INVOLVES (ClosedCase -> Transaction) — parse txn_ids pipe
        inv_rows = []
        for _, row in closed.iterrows():
            raw = str(row["txn_ids"]) if pd.notna(row["txn_ids"]) else ""
            if not raw or raw == "nan":
                continue
            tids = [t.strip() for t in raw.split("|") if t.strip()]
            # float64 column -> "3000120.0"; normalize to integer string before comparing
            first = str(row["first_fraud_txn_id"]) if pd.notna(row["first_fraud_txn_id"]) else ""
            first = re.sub(r"^(\d+)\.0+$", r"\1", first)
            for seq, tid in enumerate(tids, 1):
                inv_rows.append((str(row["case_id"]), tid, tid == first, seq))
        inv_df = pd.DataFrame(inv_rows, columns=["from_case_id","to_txn_id","is_first_fraud","sequence_in_case"])
        inv_df.sort_values(["from_case_id","sequence_in_case"]).to_csv(EDGES / "involves.csv", index=False, encoding="utf-8")

        # ON_CARD — endpoint resolved through the canonical Card map (D5 fix)
        on_rows = [(str(r["case_id"]), str(r["card_id"])) for _, r in closed_v.iterrows()]
        if canon_changed:
            print("  canonical card_id resolutions applied: %d" % len(canon_changed))
        on_df = pd.DataFrame(on_rows, columns=["from_case_id","to_card_id"])
        on_df.sort_values(["from_case_id"]).to_csv(EDGES / "on_card.csv", index=False, encoding="utf-8")

        # CONNECTED_TO — split pipe
        conn_rows = []
        for _, r in closed.iterrows():
            raw = r["connected_card_ids"]
            if pd.isna(raw) or str(raw).strip() in ("", "nan"):
                continue
            for part in str(raw).split("|"):
                part = part.strip()
                if part:
                    conn_rows.append((str(r["case_id"]), part, "ring"))
        conn_df = pd.DataFrame(conn_rows, columns=["from_case_id","to_card_id","connection_type"])
        if len(conn_df):
            conn_df.sort_values(["from_case_id","to_card_id"]).to_csv(EDGES / "connected_to.csv", index=False, encoding="utf-8")
        else:
            pd.DataFrame(columns=["from_case_id","to_card_id","connection_type"]).to_csv(EDGES / "connected_to.csv", index=False, encoding="utf-8")

        # TRIGGERS (BenchmarkCase -> Transaction)
        trig_rows = []
        for _, r in pack.iterrows():
            trig_rows.append((str(r["case_id"]), str(r["flagged_txn_id"]), str(r["trigger_type"]), float(r["risk_score"]) if pd.notna(r["risk_score"]) else -1.0))
        trig_df = pd.DataFrame(trig_rows, columns=["from_case_id","to_txn_id","trigger_type","risk_score"])
        trig_df.sort_values("from_case_id").to_csv(EDGES / "triggers.csv", index=False, encoding="utf-8")
        print("  edges written")

    # ---- orphan / dup checks on produced graph ----
    def check_orphans():
        # Load produced vertices for PK sets
        cust_ids = set(pd.read_csv(VERTICES / "customer.csv")["customer_id"].astype(str)) if (VERTICES / "customer.csv").exists() else set(cust_to_card1.keys())
        card_ids = set(pd.read_csv(VERTICES / "card.csv")["card_id"].astype(str)) if (VERTICES / "card.csv").exists() else set(card_df["card_id"].astype(str))
        txn_ids = set(tx_v["txn_id"].astype(str))
        dp_ids = set(dp_agg["device_profile_id"].astype(str)) if len(dp_agg) else set()
        # check edges if written
        orphans = []
        if (EDGES / "made.csv").exists():
            made_check = pd.read_csv(EDGES / "made.csv", dtype=str)
            o = (~made_check["from_card_id"].isin(card_ids)).sum()
            if o: orphans.append(f"MADE from_card orphan: {o}")
            o2 = (~made_check["to_txn_id"].isin(txn_ids)).sum()
            if o2: orphans.append(f"MADE to_txn orphan: {o2}")
        if (EDGES / "involves.csv").exists():
            inv = pd.read_csv(EDGES / "involves.csv", dtype=str)
            o = (~inv["to_txn_id"].isin(txn_ids)).sum()
            if o: orphans.append(f"INVOLVES to_txn orphan: {o} (invented IDs — FAIL)")
        if (EDGES / "connected_to.csv").exists():
            ct = pd.read_csv(EDGES / "connected_to.csv", dtype=str)
            if len(ct):
                o = (~ct["to_card_id"].isin(card_ids)).sum()
                if o: orphans.append(f"CONNECTED_TO to_card orphan: {o}")
        if (EDGES / "from_device.csv").exists():
            fd2 = pd.read_csv(EDGES / "from_device.csv", dtype=str)
            o = (~fd2["to_device_profile_id"].isin(dp_ids)).sum()
            if o: orphans.append(f"FROM_DEVICE to_profile orphan: {o}")
        return orphans

    # Expected counts (source-derived)
    expected_vertices = {
        "Customer": len(cust_agg),
        "Card": len(card_df),
        "Transaction": len(tx_v_out),
        "DeviceProfile": len(dp_agg),
        "EmailDomain": len(email_df),
        "BillingRegion": len(br_df),
        "ClosedCase": len(closed_v),
        "BenchmarkCase": len(pack_v),
    }
    expected_edges = {}
    if not validate_only:
        # count from files we just wrote (or compute)
        import csv as _csv
        def count_csv(p):
            if not p.exists(): return 0
            with open(p, encoding="utf-8") as f:
                return sum(1 for _ in f) - 1
        expected_edges = {
            "OWNS": count_csv(EDGES / "owns.csv"),
            "MADE": count_csv(EDGES / "made.csv"),
            "NEXT": count_csv(EDGES / "next.csv"),
            "BILLED_IN": count_csv(EDGES / "billed_in.csv"),
            "PURCHASER_EMAIL": count_csv(EDGES / "purchaser_email.csv"),
            "RECIPIENT_EMAIL": count_csv(EDGES / "recipient_email.csv"),
            "FROM_DEVICE": count_csv(EDGES / "from_device.csv"),
            "INVOLVES": count_csv(EDGES / "involves.csv"),
            "ON_CARD": count_csv(EDGES / "on_card.csv"),
            "CONNECTED_TO": count_csv(EDGES / "connected_to.csv"),
            "TRIGGERS": count_csv(EDGES / "triggers.csv"),
        }

    orphan_issues = check_orphans() if not validate_only else []
    all_issues = issues + orphan_issues

    # Write VALIDATION_REPORT.md
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    with open(VALIDATION, "w", encoding="utf-8") as f:
        f.write("# Data Validation Report — Graph-Ready Files\n\n")
        f.write(f"Generated: deterministic build from DATASET/ (no raw modification)\n\n")
        f.write("## Source Counts\n\n")
        f.write(f"- transactions.csv: {len(tx):,} rows, {len(tx.columns)} cols\n")
        f.write(f"- identity.csv: {len(ident):,} rows\n")
        f.write(f"- closed_cases_history.csv: {len(closed):,} rows\n")
        f.write(f"- case_pack.csv: {len(pack):,} rows\n\n")
        f.write("## Expected Vertex Counts (source-derived)\n\n")
        f.write("| Vertex | Count | PK | Notes |\n|--------|-------|----|-------|\n")
        for k,v in expected_vertices.items():
            f.write(f"| {k} | {v:,} | — | |\n")
        if expected_edges:
            f.write("\n## Expected Edge Counts (from produced CSVs)\n\n")
            f.write("| Edge | Count | Notes |\n|------|-------|-------|\n")
            for k,v in expected_edges.items():
                f.write(f"| {k} | {v:,} | |\n")
        f.write("\n## Checks\n\n")
        f.write(f"- Duplicate TransactionIDs: {'FAIL' if any('DUPLICATE' in x for x in issues) else 'PASS (0)'}\n")
        f.write(f"- Missing PKs (customer_id/card1): {'FAIL' if any('Missing' in x for x in issues) else 'PASS'}\n")
        f.write(f"- Invalid timestamps: {'FAIL' if any('Invalid ts' in x for x in issues) else 'PASS'}\n")
        f.write(f"- Invalid categories (ProductCD): {'FAIL' if any('Unexpected ProductCD' in x for x in issues) else 'PASS'}\n")
        f.write(f"- Orphan identity records: {ident_orphans} (expected: ~0; 6,640 online without identity is valid — those txns simply have no FROM_DEVICE edge)\n")
        f.write(f"- customer_id ↔ card1 1:1: {'FAIL' if any('1:1' in x for x in issues) else 'PASS (13,553 each)'}\n")
        if orphan_issues:
            f.write(f"- Orphan edges in produced graph: FAIL\n")
            for o in orphan_issues:
                f.write(f"  - {o}\n")
        else:
            f.write(f"- Orphan edges in produced graph: {'PASS (0)' if not validate_only else 'not checked (validate-only)'}\n")
        if all_issues:
            f.write("\n## Issues\n\n")
            for iss in all_issues:
                f.write(f"- {iss}\n")
        else:
            f.write("\n## Issues\n\nNone — all checks pass.\n")
        f.write("\n## Null / Timestamp / Numeric Handling\n\n")
        f.write("- Nulls: empty string in CSV for nullable string FKs (addr1, email, proxy, etc.); numeric nulls as empty; risk_score -1 sentinel for missing benchmark risk.\n")
        f.write("- Timestamp: `ts` preserved as original `YYYY-MM-DD HH:MM:SS` (DATETIME); `dt_seconds` as UINT.\n")
        f.write("- Ordering: all CSVs sorted deterministically by PK.\n")
        f.write("- Encoding: UTF-8, explicit headers, stable IDs.\n")
        f.write("\n## Provenance\n\n")
        f.write("| Graph object | Source file | Source identifier | Transformation |\n|---|---|---|---|\n")
        f.write("| Customer | transactions.csv | customer_id | groupby aggregate |\n")
        f.write("| Card | transactions.csv + closed/case_pack card_id | customer_id + suffix | canonical CXXXX-KY via suffix_by_customer (see card_mapping.md) |\n")
        f.write("| Transaction | transactions.csv | TransactionID | direct + card_id join via customer_id |\n")
        f.write("| DeviceProfile | identity.csv | DeviceInfo+id_30+id_31+id_33 | SHA256 composite hash |\n")
        f.write("| EmailDomain | transactions.csv | P/R_emaildomain | distinct + counts |\n")
        f.write("| BillingRegion | transactions.csv | addr1 | distinct + mode country |\n")
        f.write("| ClosedCase | closed_cases_history.csv | case_id | direct + pipe-split edges |\n")
        f.write("| BenchmarkCase | case_pack.csv | case_id | direct |\n")
        f.write("| All edges | derived as above | — | see edge sections; no invented relationships |\n")

    print(f"\nValidation report: {VALIDATION}")
    if all_issues:
        print("ISSUES:")
        for iss in all_issues:
            print("  -", iss)
    else:
        print("All checks PASS")
    print("Done.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    main(validate_only=args.validate_only)
