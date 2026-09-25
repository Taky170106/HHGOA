# Card ID Mapping — Q1 Resolution (Phase 1)

**Question Q1 (Phase 0 §19):** canonical card ID strategy for `connected_card_ids`, `INVOLVES` edges, and SAR subjects — numeric `card1` vs benchmark `CXXXX-KY`.

## Decision (Phase 1, deterministic)

`Card` vertex `PRIMARY_ID` is the **benchmark-format `CXXXX-KY`** (`card_id`). The numeric `card1` from `transactions.csv` is stored as attribute `card1_num`.

### Mapping construction (reproducible, in `tigergraph/scripts/build_graph_data.py`)

1. Build base map from `transactions.csv`: every distinct `(customer_id, card1)` → one Card. In the 6-month window this is **1:1** (13,553 pairs, verified).

2. For each `customer_id`, determine the canonical suffix `K*`:
   - Collect all `card_id` values where `card_id` starts with that `customer_id + "-K"` from:
     - `closed_cases_history.csv:card_id`
     - `closed_cases_history.csv:connected_card_ids` (pipe-split)
     - `case_pack.csv:card_id`
   - If any suffix seen, use the **max suffix** per customer (e.g., `C06403-K2` → suffix 2). This preserves `K2` cards observed in closed cases.
   - If no `K*` seen for that customer, assign suffix `1` → `CXXXX-K1`.

3. Resulting `card_id` = `customer_id + "-K" + suffix`. For customers with `K2` in history, their single card in transactions maps to `CXXXX-K2` (not `K1`) — this is correct because transactions for that customer/card all belong to that card regardless of suffix label. Customers with only `K1` remain `CXXXX-K1`.

4. All edge files reference `card_id` in this canonical form:
   - `OWNS`: `Customer.customer_id → Card.card_id`
   - `MADE`: `Card.card_id → Transaction.txn_id` (via customer_id→card1 join)
   - `ON_CARD` / `CONNECTED_TO` / `TRIGGERS`: already in `CXXXX-KY` form — resolved through the same map; any `connected_card_ids` whose prefix has no transaction customer (outside 13,553) creates a Card vertex with `card1_num = 0` and is flagged in validation.

### Why this is faithful

- No invented card numbers. Every `card_id` is either observed in a case file or deterministically derived as `customer_id + "-K1"` (the only plausible single-card label).
- Numeric `card1` is preserved as `Card.card1_num` and `Transaction.card1_num` for audit.
- All 590,742 transactions join cleanly: `Transaction.customer_id → Card.card_id` via the map.
- All 5,565 closed-case `ON_CARD` edges and 92 `CONNECTED_TO` edges and 20 benchmark `TRIGGERS` edges resolve without orphans (verified in `data/validation`).

### Example

- `Customer C12382` has `card1 = 21139` in transactions. Closed/case_pack shows `C12382-K1` → Card `C12382-K1` with `card1_num=21139`.
- `Customer C06403` has one card in transactions. Closed case `CC-0002` uses `C06403-K2` → Card `C06403-K2` (not `K1`) with that customer's `card1_num`.

### Reversibility

`card1_num` ↔ `card_id` is invertible via the `customer_id` bridge file `data/vertices/card_mapping.csv` produced by the build script.
