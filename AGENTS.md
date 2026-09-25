# AGENTS.md — Agentic Fraud Investigation (TigerGraph × HHGoa 2026)

## Project Overview
Graph-grounded fraud investigation system. **Not** an LLM fraud detector. TigerGraph is the investigation memory; LangGraph orchestrates; LLM (Gemma 4 26B) reasons/plans/synthesizes. Output: 20 case files (`cases/HHG-001.json` … `HHG-020.json`) matching HHGoa spec.

## Tech Stack
| Layer | Stack |
|-------|-------|
| Frontend | Next.js, React, TypeScript, Tailwind, Recharts, React Flow |
| Backend | Python, FastAPI, Pydantic |
| Agent | LangGraph, Gemma 4 26B A4B |
| Graph | TigerGraph, GSQL, Graph Algorithms, TigerGraph MCP |
| GraphRAG | TigerGraph vectors, BGE-small-en-v1.5, historical cases, policies, typologies |
| Optional ML | XGBoost (only if dataset supports) |

## Repository Structure (planned)
```
agentic-fraud-investigation/
├── cases/                 # HHG-001.json … HHG-020.json (output)
├── backend/               # FastAPI: main.py, api/, services/, schemas/, config/
├── agent/                 # LangGraph: graph.py, state.py, nodes/, tools/, prompts/
├── tigergraph/            # schema/, gsql/, loaders/, algorithms/
├── mcp/                   # tools/, config/
├── graphrag/              # embeddings/, retrieval/, policies/, historical_cases/
├── models/                # risk/, embeddings/
├── evidence/              # analyzer.py, contradiction.py, optimizer.py
├── xai/                   # graph_explanation.py, provenance.py
├── counterfactual/        # engine.py
├── policies/              # rules.py, permissions.py
├── frontend/              # app/, components/, lib/
├── evaluation/            # evaluator.py, metrics.py, reports/
├── scripts/               # load_data.py, run_case.py, evaluate_all.py
└── tests/
```

## Critical Commands
```bash
# Backend deps
pip install -r requirements.txt

# Frontend deps
cd frontend && npm install

# Start backend (from repo root)
uvicorn backend.main:app --reload

# Start frontend
cd frontend && npm run dev

# Run single case
python scripts/run_case.py HHG-001

# Run all 20 cases
python scripts/evaluate_all.py
```

## Environment Setup
Copy `.env.example` → `.env` and fill:
```
TIGERGRAPH_HOST=
TIGERGRAPH_USERNAME=
TIGERGRAPH_PASSWORD=
TIGERGRAPH_GRAPH_NAME=
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=
MCP_ENDPOINT=
DATABASE_URL=
```
**Never commit `.env`.**

## Development Phase Order (strict)
```
Dataset → TigerGraph → GSQL → MCP → GraphRAG → Evidence → Agent → Innovation → Policy → UI → 20 Cases → Evaluation → Demo
```
**Do not skip phases.** Each layer depends on the previous.

## Key Architectural Principles (enforced)
1. **Graph evidence is authoritative** — LLM cannot invent relationships.
2. **Tool outputs are structured** — machine-readable, not free text.
3. **Every recommendation has evidence** — traceable to source.
4. **Uncertainty is explicit** — system can say "insufficient evidence".
5. **Actions are policy-constrained** — LLM recommendation → policy validation → allowed action.
6. **Every case is auditable** — complete investigation trail recorded.

## Agent Responsibilities (LLM)
- Reasoning, tool selection, investigation planning, evidence synthesis
- Contradiction interpretation, question generation, recommendation explanation
- Natural-language case summary
- **NOT**: inventing transactions/relationships, bypassing policy, creating risk scores, unrestricted DB ops

## LangGraph State Machine
```
START → TRIAGE → INVESTIGATE → RETRIEVE → ASSESS → CHECK_UNCERTAINTY
  → REQUEST_EVIDENCE → REINVESTIGATE → GENERATE_ACTIONS → COUNTERFACTUAL
  → POLICY → RECOMMEND → END
```

## TigerGraph MCP Tools (controlled bridge)
`get_case`, `get_entity`, `get_neighbors`, `get_transactions`, `find_paths`, `find_related_cases`, `run_fraud_pattern`, `search_graph`

## Evidence Flow
```
Graph Evidence → Categorize: Supporting / Contradicting / Missing
  → Evidence Sufficiency: SUFFICIENT / INSUFFICIENT / UNCERTAIN
  → If INSUFFICIENT: Evidence Value Optimizer (info value + cost + risk)
  → Additional Evidence (controlled, authorized, auditable)
  → Re-investigation → Risk Analysis → Graph XAI → Candidate Actions
  → Counterfactual Analysis → Policy Validation → NEXT BEST ACTION
```

## Testing Strategy
- **Unit**: GSQL parsing, evidence scoring, policy rules, counterfactual calc, output validation
- **Integration**: Agent→MCP→TigerGraph, GraphRAG→LLM, Agent→Policy
- **E2E**: Case → Investigation → Recommendation → Output

## Evaluation Criteria (hackathon weights)
| Area | Weight | Key Measures |
|------|--------|--------------|
| Investigation Accuracy | 25% | Pattern ID, evidence correctness, completeness |
| Next Best Action | 25% | Relevance, uncertainty handling, evidence requests, updates |
| Case Summary & Explainability | 10% | Progression, clarity, traceability |
| Agentic Design & Engineering | 15% | Tool use, orchestration, memory, permissions, controls, state |
| Innovation | 15% | Evidence Optimizer, contradiction-driven, Graph XAI, counterfactual, policy-aware |
| Demo Quality | 10% | E2E demo, UI clarity, visualization, communication |

## Immediate First Task (Phase 0)
**Analyze the HHG dataset before any implementation:**
- Inspect README, `case_pack.csv`, all 20 cases
- Derive exact input schema, output schema, entity map, relationship map, fraud-pattern catalogue
- Only then design TigerGraph schema

## References
- Full specification: `Agentic_Fraud_Investigation_Complete_README.md` (downloaded reference)
- HHGoa case-output specification (must match exactly for 20 cases)