"""Web 端提示词：不依赖 RAG / PromptGenerator，避免 DashScope 嵌入与重型导入。"""
from __future__ import annotations

import json
from typing import Any


def _schema_params(tool: Any) -> dict:
    schema = getattr(tool, "inputSchema", None) or (
        tool.get("inputSchema") if isinstance(tool, dict) else None
    )
    if not schema or not isinstance(schema, dict):
        return {}
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    params = {}
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        entry = {"type": spec.get("type", "string")}
        if "default" in spec:
            entry["default"] = spec["default"]
        if key in required:
            entry["required"] = True
        params[key] = entry
    return params


def _compact_tools(tools_info: list[Any]) -> list[dict]:
    out = []
    for tool in tools_info:
        name = getattr(tool, "name", None) or (tool.get("name") if isinstance(tool, dict) else None)
        if not name:
            continue
        desc = getattr(tool, "description", None) or (tool.get("description") if isinstance(tool, dict) else "")
        desc = (desc or "").strip().split("\n")[0][:240]
        entry = {"name": name, "description": desc, "parameters": _schema_params(tool)}
        out.append(entry)
    return out


def _truncate_history(history_summary, max_len: int = 2000) -> str:
    if not history_summary:
        return "none"
    try:
        text = json.dumps(history_summary, ensure_ascii=False, default=str)
    except TypeError:
        text = str(history_summary)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def build_plan_prompt(
    *,
    goal_description: str,
    data_list: str,
    metadata_csv: str,
    outputspace: str,
    tools_info: list[Any],
    existing_outputs: list[str] | None = None,
    user_message: str = "",
    mandatory_first_step: str | None = None,
) -> dict:
    tools = _compact_tools(tools_info)
    tool_names = [t["name"] for t in tools]
    rules = [
        "Respond ONLY with one JSON object in the required format.",
        "Each plan step must start with: Use <exact_tool_name> to ...",
        "Do NOT put explanatory sentences or DeepMASS notes inside the plan array; only executable tool steps.",
        f"You may ONLY use these tool names: {tool_names}",
        "Do NOT use peak_detection_xcms_centwave, filter_redundant_features_camera, or any tool not in the list.",
        "Do not combine two tools in one step.",
        "Keep each step concise (one line); use absolute paths from input/output below.",
        "Output at most 9 plan steps so the JSON fits in one response.",
        "PRIORITY: follow the CURRENT user request in global_goal; do not ignore what the user just asked.",
        "If existing_outputs lists artifacts already on disk, SKIP those pipeline steps unless the user explicitly asks to re-run.",
        "If mandatory_first_step is set, plan[0] MUST be that step (or equivalent wording with the same tool and paths).",
        "If user uploaded .mzML to inputspace, data_preprocessing_xcms may run without raw conversion; mzML is auto-synced to converted_mzml.",
        "If .raw files exist but no mzML in inputspace or converted_mzml, raw conversion MUST be plan step 1 — never start with data_preprocessing_xcms.",
        "If intermediate outputs already exist (feature_table.csv, imputed table, etc.), skip upstream steps and continue from the latest missing step.",
        "If the user message is casual chat (greetings, unrelated questions), return {\"plan\": []} with zero steps.",
        "For raw conversion: input_dir is the session raw/ folder (or upload root if .raw are there); output_dir is converted_mzml under outputspace.",
        "Linux: prefer convert_raw_to_mzml_ThermoRawFileParser when listed in available_tools; Windows: use convert_raw_to_mzml_msconvert only.",
        "Never use converted_mzml as raw conversion input_dir.",
        "All tools use input_dir and output_dir (directories), NOT input_csv/output_csv, except extract_differential_features uses differential_csv + input_mgf + output_dir.",
        "feature_filtering: input_dir must contain feature_table.csv (usually peak_detection_results/).",
        "statistical_analysis_mixomics: input_dir has feature_table_filtered_imputed.csv; metadata_csv is upload/metadata.csv.",
        "molecular_networking_gnps: input_mgf is differential_features/differential_spectra.mgf OR peak_detection_results/spectra.mgf OR any uploaded .mgf; output_dir is molecular_network_results/.",
        "If the user uploads .mgf and asks for molecular networking and/or DeepMASS, plan molecular_networking_gnps and/or deepmass_annotation (skip XCMS unless they also uploaded raw/mzML).",
        "deepmass_annotation: input_dir is deepmass_annotation_results/ under outputspace; output_dir is the same or a sibling deepmass folder. Uploaded .mgf is auto-copied to differential_spectra.mgf — do NOT skip DeepMASS when differential_metabolites.csv is empty.",
    ]
    return {
        "role": "Act as a Metabolomics Expert. Follow all rules strictly.",
        "rules": rules,
        "current_user_message": user_message.strip(),
        "existing_outputs": existing_outputs or [],
        "mandatory_first_step": mandatory_first_step,
        "input_files": data_list,
        "metadata": metadata_csv,
        "outputspace": f"All outputs go under {outputspace}/",
        "global_goal": goal_description,
        "available_tools": tools,
        "response_format": {
            "plan": [
                "Use <tool_name> to <detailed task with input_dir/output_dir paths>."
            ]
        },
    }


def build_tool_match_prompt(
    *,
    goal_description: str,
    task: str,
    outputspace: str,
    tools_info: list[Any],
    history_summary=None,
) -> dict:
    tools = _compact_tools(tools_info)
    hinted = None
    for t in tools:
        if t["name"].lower() in task.lower():
            hinted = t["name"]
            break

    return {
        "role": "Tool selection assistant. Pick the tool for the current sub-task.",
        "rules": [
            "Respond ONLY with JSON: {\"tool_call\": {\"name\": \"...\", \"arguments\": {...}}}",
            "arguments keys MUST match exactly the \"parameters\" object for the chosen tool (e.g. input_dir, output_dir).",
            "Never use input_csv, input_feature_table, output_csv, input_msp as argument names unless listed in parameters.",
            "Use directory paths for input_dir/output_dir, not single output file paths.",
            "Do not invent tools outside available_tools.",
        ],
        "global_goal": goal_description,
        "current_sub_task": task,
        "suggested_tool": hinted,
        "context": _truncate_history(history_summary),
        "outputspace": f"Write outputs under {outputspace}/",
        "available_tools": tools,
        "response_format": {
            "tool_call": {"name": "tool name", "arguments": {"param": "value"}}
        },
    }
