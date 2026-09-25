"""Agentic fraud-investigation agent (LangGraph, Phase 4).

Package layout:
    agent/state.py    InvestigationState — the single source of truth per run
    agent/nodes/      one function per stage of the state machine
    agent/graph.py    StateGraph wiring + run_case()
    agent/llm/        Google AI Studio (Gemma) client with honest degradation
    agent/runs/       one JSON artifact per executed case (never cases/*.json)
"""
