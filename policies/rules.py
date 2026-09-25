"""Policy gate for recommended actions (Phase 4).

The agent never acts on the graph — it *recommends*. Every candidate action is
validated here before it can be shown as the NEXT BEST ACTION.

Rules enforce the project's architectural principles:
  1. no action without evidence traceable to a real graph entity
  2. escalation requires both model risk and graph evidence
  3. "insufficient evidence" is an allowed, first-class outcome
  4. graph mutation is never a legal action (read-only investigation layer)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Candidate actions the agent may propose, in order of preference.
ACTIONS: List[str] = [
    "ESCALATE_TO_FRAUD_REVIEW",
    "REQUEST_ADDITIONAL_EVIDENCE",
    "LINK_HISTORICAL_CASE_FOR_ANALYST_REVIEW",
    "CLOSE_NO_FURTHER_ACTION",
]

# Hard denials — none of these can ever be recommended by this layer.
FORBIDDEN_ACTIONS: List[str] = [
    "BLOCK_CARD", "DELETE_VERTEX", "WRITE_TO_GRAPH", "RUN_GSQL_WRITE",
    "AUTO_CLOSE_CASE", "SEND_CUSTOMER_NOTIFICATION",
]

RISK_ESCALATE = 0.75     # model probability at/above this may escalate
RISK_LOW = 0.30          # at/below this, escalation is impossible


def validate(action: str, facts: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (allowed, reason). `facts` is assembled by the agent from real
    graph evidence and the model score — never from the LLM's imagination."""
    if action in FORBIDDEN_ACTIONS or action not in ACTIONS:
        return False, f"policy_denied: '{action}' is not an allowed recommendation"

    prob = float(facts.get("risk_probability", -1.0))
    graph_n = int(facts.get("graph_evidence_count", 0))
    hist_n = int(facts.get("historical_case_count", 0))
    uncertainty = facts.get("uncertainty", "SUFFICIENT")

    if graph_n == 0:
        if action == "REQUEST_ADDITIONAL_EVIDENCE":
            return True, "no graph evidence yet: collecting evidence is the only legal step"
        return False, "policy_denied: no graph evidence supports this action"

    if action == "ESCALATE_TO_FRAUD_REVIEW":
        if uncertainty == "INSUFFICIENT":
            return False, "policy_denied: evidence insufficient for escalation"
        if prob < RISK_ESCALATE:
            return False, (f"policy_denied: model probability {prob:.3f} < "
                           f"escalation threshold {RISK_ESCALATE}")
        if hist_n == 0 and graph_n < 3:
            return False, "policy_denied: escalation needs graph corroboration " \
                          "(historical case linkage or >=3 graph facts)"
        return True, (f"risk {prob:.3f} >= {RISK_ESCALATE} with {graph_n} graph "
                      f"facts and {hist_n} historical case link(s)")

    if action == "REQUEST_ADDITIONAL_EVIDENCE":
        if uncertainty == "SUFFICIENT" and prob >= RISK_ESCALATE:
            return False, "policy_denied: evidence already sufficient to escalate"
        return True, "residual uncertainty: more evidence improves the decision"

    if action == "LINK_HISTORICAL_CASE_FOR_ANALYST_REVIEW":
        if hist_n == 0:
            return False, "policy_denied: no historical case actually links to this entity"
        return True, f"{hist_n} historical ClosedCase record(s) link to this entity"

    if action == "CLOSE_NO_FURTHER_ACTION":
        if prob > RISK_LOW:
            return False, (f"policy_denied: model probability {prob:.3f} > "
                           f"{RISK_LOW}; cannot recommend closing")
        if hist_n > 0:
            return False, "policy_denied: historical case linkage exists"
        return True, f"risk {prob:.3f} <= {RISK_LOW} and no historical linkage"

    return False, "policy_denied: unknown action"


def select(facts: Dict[str, Any], candidates: List[str]) -> Dict[str, Any]:
    """Try candidates in order; return the first allowed one, else the safest
    legal fallback. Records every denial so the decision is auditable."""
    tried = []
    for action in candidates:
        ok, reason = validate(action, facts)
        tried.append({"action": action, "allowed": ok, "reason": reason})
        if ok:
            return {"action": action, "reason": reason, "evaluated": tried,
                    "policy": "policies/rules.py (allowlist + evidence gates)"}
    return {"action": "REQUEST_ADDITIONAL_EVIDENCE",
            "reason": "policy_denied all candidates; safest legal recommendation",
            "evaluated": tried,
            "policy": "policies/rules.py (allowlist + evidence gates)"}
