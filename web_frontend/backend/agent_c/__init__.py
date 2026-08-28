"""Agent C：可视化与报告。A/B 通过本包对接，不必走 Web 会话。"""
from web_frontend.backend.agent_c.contract import CONTRACT_VERSION, contract_document
from web_frontend.backend.agent_c.paper_reproduction import (
    checklist_inventory,
    list_repro_recipes,
    load_repro_recipe,
    recipe_to_canonical_plan,
)
from web_frontend.backend.agent_c.plan_adapter import (
    is_massomics_plan_document,
    normalize_massomics_plan,
)
from web_frontend.backend.agent_c.plan_parser import load_plan, parse_plan, resolve_plot_type
from web_frontend.backend.agent_c.results_inventory import inventory_results
from web_frontend.backend.agent_c.runner import run_agent_c

__all__ = [
    "CONTRACT_VERSION",
    "contract_document",
    "is_massomics_plan_document",
    "normalize_massomics_plan",
    "parse_plan",
    "load_plan",
    "resolve_plot_type",
    "inventory_results",
    "run_agent_c",
    "list_repro_recipes",
    "load_repro_recipe",
    "recipe_to_canonical_plan",
    "checklist_inventory",
]
