"""Web 端提示词：轻量计划/工具匹配；可选注入 literature_rag 检索到的文献上下文。"""
from __future__ import annotations

import json
from typing import Any

from web_frontend.backend.anti_hallucination import (
    PLAN_ANTI_HALLUCINATION_RULES,
    TOOL_MATCH_ANTI_HALLUCINATION_RULES,
)


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
    literature_context: str | None = None,
    skill_context: str | None = None,
) -> dict:
    tools = _compact_tools(tools_info)
    tool_names = [t["name"] for t in tools]
    has_literature = bool((literature_context or "").strip())
    has_skills = bool((skill_context or "").strip())
    rules = [
        "Respond ONLY with one JSON object in the required format.",
        "Each plan step must start with: Use <exact_tool_name> to ...",
        "Do NOT put explanatory sentences or DeepMASS notes inside the plan array; only executable tool steps.",
        f"You may ONLY use these tool names: {tool_names}",
        "Do NOT invent tool names that are not in the list above.",
        "Do not combine two tools in one step.",
        "Keep each step concise (one line); use absolute paths from input/output below.",
        "Output at most 12 plan steps so the JSON fits in one response.",
        "PRIORITY: follow the CURRENT user request in global_goal; do not ignore what the user just asked.",
        "Conflict resolution: USER instruction > skill_context (parameter consensus) > literature_context > default pipeline preferences.",
        "If skill_context is present, treat its Pipeline/Parameter Consensus as high-priority methodological evidence "
        "(software parameters like XCMS ppm/peakwidth, GNPS thresholds); map only onto available_tools.",
        "If literature_context is present, prefer published workflow tool choices/order/parameters that map onto available_tools; "
        "do not invent tools or file paths that appear only in literature.",
        "If literature_context or skill_context is present and the user did not truncate scope, briefly reflect evidence-backed stage choices "
        "in plan step wording (tool + why), still one executable line per step.",
        "Never fabricate paper citations; only mention sources that appear inside literature_context or skill_context.",
        "If existing_outputs lists artifacts already on disk, SKIP those pipeline steps unless the user explicitly asks to re-run.",
        "If mandatory_first_step is set, plan[0] MUST be that step (or equivalent wording with the same tool and paths).",
        "If user uploaded .mzML to inputspace, data_preprocessing_xcms (or an alternative preprocessing tool if requested) may run without raw conversion; mzML is auto-synced to converted_mzml.",
        "If .raw files exist but no mzML in inputspace or converted_mzml, raw conversion MUST be plan step 1 — never start with data_preprocessing_xcms.",
        "When the user asks for volcano contrast (A vs B) or PLS by a metadata column (按 Time 做 PLS), "
        "include group_column / contrast_group1 / contrast_group2 in statistical_analysis_mixomics arguments.",
        "If intermediate outputs already exist (feature_table.csv, imputed table, etc.), skip upstream steps and continue from the latest missing step.",
        "If the user message is casual chat (greetings, unrelated questions), return {\"plan\": []} with zero steps.",
        "For plot style edits (title/color/font/align) on EXISTING figures ONLY (no new analysis), use plot_edit — do NOT invent image paths or re-run analysis just to change style.",
        "Do NOT plan plot_edit for analysis mapping intents (color_by Group/Batch/化学类, volcano thresholds, KEGG color_channel, motif channel) when the plan already includes statistical_analysis_mixomics / molecular_networking_* / kegg_compound_enrichment — runtime deterministically re-renders after those tools succeed.",
        "When the user says 只要/仅 + figure names (e.g. volcano+VIP) or 不要分子网络/KEGG, prefer those tools only; runtime also prunes excluded analysis kinds from the plan.",
        "If the user asks to color by a metadata column that is missing (e.g. Time), do not invent the column — surface the available columns.",
        "Plan shape when user asks analysis + mapping + optional panel: "
        "(1) analysis tools only (trim by existing outputs / dependencies); "
        "(2) if user wants a panel/拼图, add image_merge (then merge_edit only if adjusting an existing merge); "
        "(3) NEVER append a chain of plot_edit recolor/threshold/channel steps.",
        "plot_edit is still valid alone for pure style/recolor on already-finished PNGs; never fake a new mapping by only editing palette keys.",
        "When the user mentions FBMN/MS2LDA/KEGG/拓扑着色, prefer the matching registered analysis tool; do not invent tool names.",
        "Analysis tools that produce PNGs write editable sidecars; later gallery/chat style edits use plot_edit.",
        "For merging multiple PNGs into one panel figure, use image_merge; to adjust an existing merge use merge_edit.",
        "Never invent tool names (no plot_merge) or folders (no merged_plots/); only image_merge/merge_edit → merged_figures/.",
        "When merging, honor user label case (ABCD vs abcd) and label font size (e.g. 150/350) exactly.",
        "plot_edit / image_merge / merge_edit write real files under edited_plots/ or merged_figures/; never invent file paths.",
        "After analysis that generates plots, remind that figures are editable in the web gallery (Agent 改图 / semantic editor) or via chat with plot_edit.",
        "Use ONLY exact tool names from available_tools. Default pipeline prefers XCMS + GNPS; choose OpenMS/MZmine/KPIC/PeakOnly/FBMN/library_match_* when the user asks for those methods "
        "(or when literature_context clearly recommends them and the tool is available).",
        "For raw conversion: input_dir is the session raw/ folder (or upload root if .raw are there); output_dir is converted_mzml under outputspace.",
        "Linux: prefer convert_raw_to_mzml_ThermoRawFileParser when listed in available_tools; Windows: use convert_raw_to_mzml_msconvert only.",
        "Never use converted_mzml as raw conversion input_dir.",
        "All tools use input_dir and output_dir (directories), NOT input_csv/output_csv, except extract_differential_features uses differential_csv + input_mgf + output_dir.",
        "feature_filtering: input_dir must contain feature_table.csv (usually peak_detection_results/).",
        "statistical_analysis_mixomics: input_dir has feature_table_filtered_imputed.csv; metadata_csv is upload/metadata.csv "
        "(runtime auto-aligns Sample names to the feature table; mismatched stale metadata is regenerated from filenames). "
        "Optional: group_column (PLS-DA Y, default Group), contrast_group1/contrast_group2 for volcano when >2 groups "
        "(e.g. Treatment vs Control). Runtime also injects these from user intent when stated in natural language.",
        "After XCMS: NEVER plan peak_group_alignment_openms unless *.featureXML already exists; "
        "FBMN must use XCMS feature_table.csv / filtered imputed table + spectra.mgf, not openms_aligned_features/.",
        "molecular_networking_ms2lda: ALWAYS use peak_detection_results/spectra.mgf "
        "(feature-aligned full MS2 corpus for Mass2Motif discovery). "
        "Do NOT use differential_spectra.mgf (often only a few VIP hits) or raw per-file MS2 dumps.",
        "spectral_annotation input_dir MUST be differential_features/ (needs differential_spectra.mgf + differential_feature_table.csv), "
        "never peak_detection_results/ or statistical_results/.",
        "kegg_compound_enrichment needs annotation_results/...library_match_clean&add.csv from spectral_annotation — not statistical_results/.",
        "molecular_networking_gnps / fbmn: input_mgf may be differential_spectra.mgf OR peak_detection_results/spectra.mgf; "
        "ms2lda must use peak_detection_results/spectra.mgf; output_dir is molecular_network_results/<method>/.",
        "If the user uploads .mgf and asks for molecular networking and/or DeepMASS, plan molecular_networking_* and/or deepmass_annotation (skip XCMS unless they also uploaded raw/mzML).",
        "deepmass_annotation: input_dir is deepmass_annotation_results/ under outputspace; output_dir is the same or a sibling deepmass folder. Uploaded .mgf is auto-copied to differential_spectra.mgf — do NOT skip DeepMASS when differential_metabolites.csv is empty.",
        "library_match_* / spectral_annotation: prefer when user asks for library matching or annotation against spectral libraries.",
        "peak_detection_* / align_* / group_peaks_* / fill_missing_* / filter_redundant_* / redundant_feature_filtering_*: use for step-by-step pipelines when user does not want end-to-end data_preprocessing_*.",
        *PLAN_ANTI_HALLUCINATION_RULES,
    ]
    payload = {
        "role": "Act as a Metabolomics Expert. Follow all rules strictly. You only emit a JSON plan; runtime executes tools.",
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
    if has_literature:
        payload["literature_context"] = literature_context.strip()
        payload["literature_note"] = (
            "Retrieved from softwares_database / softwares_database_RAG. "
            "Use as methodological evidence within available_tools; user instruction still wins."
        )
    if has_skills:
        sk = skill_context.strip()
        if len(sk) > 10000:
            sk = sk[:9980] + "\n...(truncated)"
        payload["skill_context"] = sk
        payload["skill_note"] = (
            "Extracted from high-reproducibility paper recipes (phase2_output). "
            "Prefer explicit software parameters; still only call available_tools."
        )
    return payload


def build_tool_match_prompt(
    *,
    goal_description: str,
    task: str,
    outputspace: str,
    tools_info: list[Any],
    history_summary=None,
    literature_context: str | None = None,
    skill_context: str | None = None,
) -> dict:
    tools = _compact_tools(tools_info)
    hinted = None
    for t in tools:
        if t["name"].lower() in task.lower():
            hinted = t["name"]
            break

    rules = [
        "Respond ONLY with JSON: {\"tool_call\": {\"name\": \"...\", \"arguments\": {...}}}",
        "arguments keys MUST match exactly the \"parameters\" object for the chosen tool (e.g. input_dir, output_dir).",
        "Never use input_csv, input_feature_table, output_csv, input_msp as argument names unless listed in parameters.",
        "Use directory paths for input_dir/output_dir, not single output file paths.",
        "Do not invent tools outside available_tools.",
        "When skill_context is present, prefer its explicit software parameters over vague defaults.",
        "When literature_context is present, prefer parameter values and tool choices supported by that evidence, "
        "but only if the tool exists in available_tools and argument names match the schema.",
        "Do not invent citation strings; do not copy inaccessible literature-only file paths.",
        "For plot_edit / image_merge / merge_edit: arguments must include instruction (natural language); optional source_rel or target_rel for specific files.",
        "Never claim a file was written unless the tool result lists a real path.",
        *TOOL_MATCH_ANTI_HALLUCINATION_RULES,
    ]
    payload = {
        "role": "Tool selection assistant. Pick the tool for the current sub-task. Emit JSON only.",
        "rules": rules,
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
    if (literature_context or "").strip():
        # 工具匹配阶段控制长度，避免挤掉 schema
        lit = literature_context.strip()
        if len(lit) > 4500:
            lit = lit[:4480] + "\n...(truncated)"
        payload["literature_context"] = lit
    if (skill_context or "").strip():
        sk = skill_context.strip()
        if len(sk) > 4500:
            sk = sk[:4480] + "\n...(truncated)"
        payload["skill_context"] = sk
    return payload
