"""从 Methods 文本用 LLM 抽取参数级 reproducibility_recipe。"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import find_dotenv, load_dotenv

from recipe_format import recipe_has_explicit_params


RECIPE_SYSTEM = """You are an expert metabolomics / mass-spectrometry methods curator.
Extract a reproducibility recipe from the paper Methods text.
Respond with ONE JSON object only (no markdown fences)."""


def _build_prompt(
    *,
    methods_text: str,
    paper_title: str,
    source_paper: str,
) -> str:
    schema = {
        "paper_title": "string",
        "source_paper": "Author et al. (year), Journal, DOI: ..., PMID: ...",
        "overall_reproducibility_score": "integer 0-100",
        "workflow_steps": [
            {
                "title": "short task name",
                "tool": "software / platform name with version if stated",
                "algorithm": "algorithm if stated else empty string",
                "parameters": "MUST use key=value pairs separated by commas when the paper states numbers/settings; use not_reported if absent. NEVER invent numeric parameters.",
                "input": "input data description",
                "output": "output description",
                "confidence": "high|medium|low based on how explicitly the paper states this step",
            }
        ],
        "data_availability": {
            "raw_data": "available|not_mentioned|request_only + accession if any",
            "processed_data": "...",
            "metadata": "...",
            "data_urls": "urls or empty",
        },
        "code_availability": "repository_linked|supplement|not_mentioned",
        "figure_recipes": [
            {
                "name": "Figure 1",
                "type": "pca_scores|volcano_plot|heatmap|network|pathway_map|boxplot|bar_chart|workflow_diagram|other",
                "caption": "what the figure shows / analysis purpose",
                "produced_by_step": "step index or list",
                "visualization_tool": "tool if stated",
                "statistical_test": "test + thresholds if stated",
            }
        ],
        "reproducibility_gaps": ["missing params or versions"],
        "reproducibility_strengths": ["explicit params, public data/code, etc."],
    }
    rules = [
        "Focus on computational / informatics steps (preprocessing, annotation, statistics, networking, enrichment).",
        "parameters field is CRITICAL: copy exact software settings from the text (e.g. ppm=5, peakwidth=[10,60], snthresh=10, cosine=0.7).",
        "If a parameter is implied but not numeric, write qualitative settings still as key=value when possible.",
        "Do NOT fabricate parameters that are not supported by the Methods text.",
        "Score high (80-95) only when multiple steps have explicit parameters AND data/code cues exist; score low when methods are vague.",
        "Include 3-12 workflow_steps when possible; skip pure wet-lab chemistry unless tied to acquisition settings.",
        "figure_recipes: infer figure purposes from Methods/Results language if figure captions are absent; mark visualization_tool=not_reported when unknown.",
        "Return JSON only.",
    ]
    payload = {
        "role": RECIPE_SYSTEM,
        "rules": rules,
        "paper_title": paper_title,
        "source_paper_hint": source_paper,
        "methods_text": methods_text[:42000],
        "json_schema": schema,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty LLM response")
    # strip fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # first {...}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("cannot parse JSON from LLM response")


def _llm_complete(prompt: str, *, temperature: float = 0.1) -> str:
    load_dotenv(find_dotenv(), override=False)
    # Prefer project LLM_Client streaming join; fall back to OpenAI non-stream
    try:
        from src.llm_client import LLM_Client

        client = LLM_Client()
        messages = [
            {"role": "system", "content": RECIPE_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        # monkey: think prints; capture via returning string
        out = client.think(messages, temperature=temperature)
        if out:
            return out
    except Exception as exc:
        print(f"[extract_recipe] LLM_Client fallback ({exc})")

    from openai import OpenAI

    model = os.getenv("LLM_MODEL_ID")
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    timeout = int(os.getenv("LLM_TIMEOUT", "120"))
    if not all([model, api_key, base_url]):
        raise ValueError("缺少 LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": RECIPE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        stream=False,
    )
    return (resp.choices[0].message.content or "").strip()


def normalize_recipe(
    data: dict[str, Any],
    *,
    paper_title: str,
    source_paper: str,
) -> dict[str, Any]:
    out = dict(data)
    out["paper_title"] = out.get("paper_title") or paper_title
    out["source_paper"] = out.get("source_paper") or source_paper
    try:
        score = int(out.get("overall_reproducibility_score") or 0)
    except (TypeError, ValueError):
        score = 0
    out["overall_reproducibility_score"] = max(0, min(100, score))

    steps = out.get("workflow_steps") or []
    if isinstance(steps, list):
        cleaned = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            params = str(step.get("parameters") or "").strip()
            if not params:
                step["parameters"] = "not_reported"
            cleaned.append(step)
        out["workflow_steps"] = cleaned
    else:
        out["workflow_steps"] = []

    # 若几乎没有显式参数却打高分，下调
    if out["overall_reproducibility_score"] >= 80 and not recipe_has_explicit_params(out):
        out["overall_reproducibility_score"] = min(out["overall_reproducibility_score"], 55)
        gaps = list(out.get("reproducibility_gaps") or [])
        gaps.append("score_adjusted: few explicit software parameters found in Methods")
        out["reproducibility_gaps"] = gaps
    return out


def extract_recipe_from_methods(
    methods_text: str,
    *,
    paper_title: str = "",
    source_paper: str = "",
    temperature: float = 0.1,
) -> dict[str, Any]:
    if not (methods_text or "").strip():
        raise ValueError("methods_text is empty")
    prompt = _build_prompt(
        methods_text=methods_text,
        paper_title=paper_title,
        source_paper=source_paper,
    )
    raw = _llm_complete(prompt, temperature=temperature)
    data = _extract_json(raw)
    return normalize_recipe(data, paper_title=paper_title, source_paper=source_paper)
