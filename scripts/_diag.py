import io, sys, os, json
_w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_w._hhg_wrapped = True
sys.stdout = _w
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_cases as B

FLAGS = ["card_testing", "out_of_region", "new_device", "proxy", "match_anomaly",
         "amount_outlier", "new_product", "burst", "ring", "device_prior_fraud",
         "card_prior_fraud", "domain_new", "channel_change", "recurring", "denied"]

print("%-8s %-16s %5s %5s %5s %5s %6s %6s  %s" %
      ("case", "trigger", "risk", "ml", "p0", "anom", "p0disp", "", "flags"))
for row in B.pack:
    f = B.gather(row)
    a = B.analyse(f)
    fl = [k for k in FLAGS if a[k]]
    print("%-8s %-16s %5s %5.2f %5.2f %5d %6.2f  %s" % (
        f["case_id"], f["trigger_type"],
        "-" if a["risk_input"] is None else "%.2f" % a["risk_input"],
        a["ml_probability"], a["p_initial"], a["anomaly_count"],
        a["graph_signal"], ",".join(fl)))
