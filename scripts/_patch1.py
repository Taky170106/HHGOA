import ast, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
p = r"D:\HHG\scripts\build_cases.py"
s = open(p, encoding="utf-8").read()

pairs = [
    ('f["small_auths_1h"] = [str(t) for t in small["txn_id"]]',
     'f["small_auths_1h"] = [str(t) for t in small["txn_id"]] if "txn_id" in small.columns else []'),
    ('f["small_auth_amounts"] = [float(a) for a in small["amount_f"]]',
     'f["small_auth_amounts"] = [float(a) for a in small["amount_f"]] if "amount_f" in small.columns else []'),
    ('f["recurring_matches"] = [str(t) for t in rec["txn_id"]]',
     'f["recurring_matches"] = [str(t) for t in rec["txn_id"]] if "txn_id" in rec.columns else []'),
    ('f["online_48h_before"] = [str(t) for t in b_win[b_win["channel"] == "online"]["txn_id"]] if len(b_win) else []',
     'f["online_48h_before"] = [str(t) for t in b_win[b_win["channel"] == "online"]["txn_id"]] if ("txn_id" in b_win.columns and len(b_win)) else []'),
    ('f["online_48h_after"] = [str(t) for t in a_win[a_win["channel"] == "online"]["txn_id"]] if len(a_win) else []',
     'f["online_48h_after"] = [str(t) for t in a_win[a_win["channel"] == "online"]["txn_id"]] if ("txn_id" in a_win.columns and len(a_win)) else []'),
    ('f["card_prior_regions"] = sorted({str(a) for a in prior["addr1"]}) if len(prior) else []',
     'f["card_prior_regions"] = sorted({str(a) for a in prior["addr1"]}) if ("addr1" in prior.columns and len(prior)) else []'),
    ('f["card_prior_domains"] = sorted({str(a) for a in prior["p_emaildomain"].dropna()}) if len(prior) else []',
     'f["card_prior_domains"] = sorted({str(a) for a in prior["p_emaildomain"].dropna()}) if ("p_emaildomain" in prior.columns and len(prior)) else []'),
    ('f["card_prior_products"] = sorted(set(prior["product_cd"])) if len(prior) else []',
     'f["card_prior_products"] = sorted(set(prior["product_cd"])) if ("product_cd" in prior.columns and len(prior)) else []'),
    ('f["card_prior_channels"] = sorted(set(prior["channel"])) if len(prior) else []',
     'f["card_prior_channels"] = sorted(set(prior["channel"])) if ("channel" in prior.columns and len(prior)) else []'),
    ('f["card_prev_channel"] = str(prior.iloc[-1]["channel"]) if len(prior) else ""',
     'f["card_prev_channel"] = str(prior.iloc[-1]["channel"]) if ("channel" in prior.columns and len(prior)) else ""'),
    ('f["card_prev_ts"] = float(prior.iloc[-1]["ts_f"]) if len(prior) else 0.0',
     'f["card_prev_ts"] = float(prior.iloc[-1]["ts_f"]) if ("ts_f" in prior.columns and len(prior)) else 0.0'),
    ('f["card_prev_txn"] = str(prior.iloc[-1]["txn_id"]) if len(prior) else ""',
     'f["card_prev_txn"] = str(prior.iloc[-1]["txn_id"]) if ("txn_id" in prior.columns and len(prior)) else ""'),
    ('f["card_median_amount"] = float(prior["amount_f"].median()) if len(prior) else 0.0',
     'f["card_median_amount"] = float(prior["amount_f"].median()) if ("amount_f" in prior.columns and len(prior)) else 0.0'),
]
missing = [a for a, b in pairs if a not in s]
for a, b in pairs:
    if a in s:
        s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="").write(s)
ast.parse(s)
print("patched; missing patterns:", len(missing))
for m in missing:
    print("  NOT FOUND:", m[:70])
