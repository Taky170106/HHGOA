# Graph Algorithms — Justified Use

> Do NOT present algorithms as fraud detectors. Each algorithm is a **relationship-analysis aid** whose output an investigator interprets with evidence and policy. All algorithms run on `hhg_fraud_graph` after loading.

## 1. Weakly Connected Components (WCC) — DeviceSharing / Ring Discovery

- **Why relevant**: Rule R6 / Investigation Path A & E. Cards linked by a shared `DeviceProfile`, `BillingRegion`, or `Recipient Email` form components; the 4 verified fraud rings (CC-2649/2971/2985/3035 share 92 `CONNECTED_TO` edges and identical 23-card sets) should appear as one component.
- **Input**: projection of `Card -[MADE]- Transaction -[FROM_DEVICE]- DeviceProfile` (or region/email variant)
- **Output**: `component_id` per `Card`/`Transaction`/`DeviceProfile`; component size
- **Investigator use**: surface candidate rings; filter by `DeviceProfile.specificity` to exclude generic profiles (e.g., `Windows|chrome 63|1920x1080` with 800+ cards) which form trivial super-components.
- **Limitation**: WCC on generic device profiles = single giant component (noise). Must run on **specific** profiles only (specificity ≥ 0.01, i.e., ≤100 cards). Does not prove fraud — only shared exposure.

## 2. Louvain / Label Propagation — Community Detection on Transaction-Transaction via Shared Device

- **Why relevant**: Identify coordinated bursts (undocumented patterns) without hard clustering.
- **Input**: `Transaction <-[FROM_DEVICE]-> Transaction` co-occurrence graph, 1-hop, windowed by `ts` (e.g., same week).
- **Output**: `community_id` per transaction
- **Use**: Proposed for Innovation: detect sub-$500 burst clusters (closed docs describe "4x <$500 in 40 min" pattern).
- **Limitation**: Without temporal windowing, communities merge via generic devices. Requires `ts` filter + specificity weighting.

## 3. Breadth-First / Shortest-Path — Path Analysis (Provenance)

- **Why relevant**: Explainability (phase0/EXPLAINABILITY_MODEL.md). Shortest path `BenchmarkCase -> flagged Transaction -> Customer/Card -> Prior Case` is the strongest human-readable explanation.
- **Input**: source `BenchmarkCase.case_id` (or `flagged_txn_id`), target `ClosedCase.case_id` or `Card.card_id`
- **Output**: path list (vertices/edges) + path length + shared-entity label
- **Use**: Populate `evidence[].ref` and `summary` with auditable paths.
- **Limitation**: Multiple paths exist; shortest may use a generic device/email — weight by specificity.

## 4. PageRank / Degree Centrality — Centrality

- **Why relevant**: Surface high-reuse `DeviceProfile`/`EmailDomain`/`BillingRegion` nodes (hubs) for triage.
- **Input**: full `hhg_fraud_graph` (or DeviceProfile subgraph)
- **Output**: `centrality_score` per vertex; ranked list.
- **Use**: Flag profiles for manual review if `customer_count > 50` AND specificity low (likely generic) vs. `customer_count 2-10` AND high specificity (rare shared device = higher suspicion).
- **Limitation**: Centrality alone is anti-signal for generic devices — high centrality = low specificity = weak evidence. Must be interpreted inversely for fraud.

## 5. Jaccard Similarity (Neighbor Overlap) — Relationship Analysis

- **Why relevant**: Measure overlap of card transaction neighborhoods (shared regions/devices/emails) without full community detection.
- **Input**: two `Card` vertices (or card's transaction sets)
- **Output**: Jaccard coefficient [0,1]
- **Use**: Rank `connected_card_ids` candidates; justify `connected_device_profiles` in answer file.
- **Limitation**: Needs temporal window and threshold tuning; generic devices inflate similarity.

---

## TigerGraph Built-ins Referenced

- `TG_WCC`, `TG_Louvain`, `TG_LabelProp`, `TG_BFS`, `TG_ShortestPath`, `TG_PageRank`, `TG_DegreeCentrality`, `TG_Jaccard` from `gsql-graph-algorithms` library. All support `hhg_fraud_graph` vertex/edge types above.

## No Fraud-Score Claim

None of the above emits a fraud probability. The investigating agent combines their outputs with transaction amounts, temporal deltas, `risk_score`, and historical `ClosedCase` outcomes under policy rules R1–R10 to produce `fraud_probability` and `next_best_actions`. Every recommendation remains evidence- and policy-constrained.

## File

GSQL wrappers for the three primary aids are in `tigergraph/algorithms/algorithms.gsql`.
