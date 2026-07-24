"""
Web 端 Agent 执行：计划 → 工具匹配 → 执行（MCP 分析工具 + 本地 visual 工具）。
不加载 src.agent / RAG，逻辑集中在 web_frontend。
"""
from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from src.platform_utils import (
    is_windows,
    mcp_stdio_parameters,
    normalize_display_path,
    preferred_raw_converter,
)
from web_frontend.backend.agent_jobs import is_cancelled
from web_frontend.backend.json_parse import (
    extract_first_json_object,
    extract_plan_list,
    parse_tool_call,
)
from web_frontend.backend.tool_registry import (
    ALL_AGENT_TOOL_NAMES,
    LOCAL_TOOL_ALIASES,
    AgentContext,
    format_local_tool_result,
    is_local_tool,
    load_all_tools,
    normalize_agent_tool_name,
    run_local_tool,
)
from web_frontend.backend.plan_utils import (
    ensure_raw_conversion_step,
    filter_plan_tasks_to_registered_tools,
    guess_tool_name_from_task,
    inject_analysis_coloring_tasks,
    inject_mgf_standalone_tasks,
    inject_visual_standalone_tasks,
    normalize_plan_tasks_for_platform,
    raw_conversion_needed,
)
from web_frontend.backend.pipeline_utils import (
    conversion_downstream_blocked,
    conversion_environment_hint,
    differential_csv_has_rows,
    differential_downstream_blocked,
    ensure_empty_differential_csv,
    MZML_DEPENDENT_TOOLS,
    OPENMS_FEATUREXML_TOOLS,
    openms_featurexml_blocked,
    prune_differential_dependent_tasks,
    prune_mzml_dependent_tasks,
)
from web_frontend.backend.raw_converter import (
    build_conversion_plan_step,
    call_raw_converter_with_fallback,
    is_raw_converter,
    raw_converter_fallback_order,
    resolve_initial_raw_converter,
)
from web_frontend.backend.session_storage import session_upload_dir, session_work_dir
from web_frontend.backend.session_file_resolver import (
    mzml_ready_for_xcms,
    summarize_session_files,
)
from web_frontend.backend.tool_runner import (
    TOOL_RUNTIME_HINTS,
    call_tool_with_heartbeat,
    format_tick_message,
)
from web_frontend.backend.web_llm import WebLLMClient
from web_frontend.backend.tool_args_normalizer import (
    format_mcp_tool_result,
    is_mcp_tool_result_error,
    normalize_tool_args,
)
from web_frontend.backend.web_prompts import build_plan_prompt, build_tool_match_prompt


def build_session_paths(
    session_id: str,
    project_root: Path,
    storage_slug: Optional[str] = None,
) -> dict[str, str]:
    slug = storage_slug or session_id
    upload_path = session_upload_dir(project_root, slug)
    base_path = session_work_dir(project_root, slug)
    paths = {
        "upload": normalize_display_path(upload_path),
        "outputspace": normalize_display_path(base_path),
        "raw": normalize_display_path(upload_path / "raw"),
        "converted_mzml": normalize_display_path(base_path / "converted_mzml"),
        "peaks": normalize_display_path(base_path / "peak_detection_results"),
        "filtered": normalize_display_path(base_path / "filtered_features"),
        "statistical": normalize_display_path(base_path / "statistical_results"),
        "differential": normalize_display_path(base_path / "differential_features"),
        "annotated": normalize_display_path(base_path / "annotation_results"),
        "kegg": normalize_display_path(base_path / "kegg_enrichment_results"),
        "molecular_network": normalize_display_path(base_path / "molecular_network_results"),
        "deepmass": normalize_display_path(base_path / "deepmass_annotation_results"),
    }
    for key in (
        "converted_mzml",
        "peaks",
        "filtered",
        "statistical",
        "differential",
        "annotated",
        "kegg",
        "molecular_network",
        "deepmass",
    ):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)
    return paths


def _prune_remaining_differential_tasks(
    tasks: list[str],
    paths: dict[str, str],
) -> tuple[list[str], str | None]:
    """统计完成后裁剪无法执行的差异相关步骤。"""
    ensure_empty_differential_csv(Path(paths["statistical"]))
    blocked, reason = differential_downstream_blocked(paths)
    if not blocked:
        return tasks, None
    kept, removed = prune_differential_dependent_tasks(tasks)
    if not removed:
        return tasks, None
    return kept, reason


def build_data_list(upload_dir: str, paths: dict[str, str]) -> str:
    return "\n".join(summarize_session_files(paths, upload_dir))


def build_metadata_csv(upload_dir: str) -> str:
    upload = Path(upload_dir)
    meta = upload / "metadata.csv"
    if meta.is_file():
        return (
            f"{normalize_display_path(meta)}: "
            "This CSV file contains sample metadata, including columns for sample ID and experimental group."
        )
    return (
        f"{normalize_display_path(upload)}: "
        "Place metadata.csv in this session input folder when sample metadata is required."
    )


def _scan_existing_outputs(paths: dict[str, str]) -> list[str]:
    """列出 inputspace/outputspace 中已存在的关键产物，供计划阶段跳过重复步骤。"""
    found: list[str] = []
    if mzml_ready_for_xcms(paths, paths["upload"]):
        found.append("mzML input (inputspace and/or converted_mzml)")
    file_checks: list[tuple[Path, str]] = [
        (Path(paths["peaks"]) / "feature_table.csv", "XCMS feature_table.csv"),
        (Path(paths["peaks"]) / "spectra.mgf", "XCMS spectra.mgf"),
        (Path(paths["filtered"]) / "feature_table_filtered_imputed.csv", "filtered imputed table"),
    ]
    if differential_csv_has_rows(paths):
        file_checks.append(
            (Path(paths["statistical"]) / "differential_metabolites.csv", "differential_metabolites.csv")
        )
    file_checks.extend([
        (Path(paths["differential"]) / "differential_spectra.mgf", "differential_spectra.mgf"),
        (
            Path(paths["annotated"]) / "differential_feature_table_library_match_clean&add.csv",
            "annotation results",
        ),
        (Path(paths["molecular_network"]) / "molecular_network.graphml", "GNPS molecular network"),
        (Path(paths["deepmass"]) / "top1_annotations.csv", "DeepMASS2 annotations"),
    ])
    for path, label in file_checks:
        if path.is_file():
            found.append(label)
    return found


def build_web_goal_description(
    user_message: str,
    paths: dict[str, str],
    *,
    existing_outputs: Optional[list[str]] = None,
    recent_messages: Optional[list[dict]] = None,
) -> str:
    """Web 专用目标描述：白名单工具流程 + 已有产物 + 本轮用户意图。"""
    pref = preferred_raw_converter()
    convert_tool = str(pref["tool"])
    if is_windows():
        platform_note = (
            "Windows: use convert_raw_to_mzml_msconvert for .raw (Docker required). "
            "Do NOT use ThermoRawFileParser."
        )
    else:
        platform_note = (
            f"Linux: prefer {convert_tool} ({pref.get('reason', '')}). "
            "Use convert_raw_to_mzml_msconvert only when ThermoRawFileParser is unavailable."
        )

    upload = paths["upload"]
    raw_in = paths.get("raw") or str(Path(upload) / "raw")
    converted = paths["converted_mzml"]
    peaks = paths["peaks"]
    filtered = paths["filtered"]
    statistical = paths["statistical"]
    annotated = paths["annotated"]

    history_lines: list[str] = []
    if recent_messages:
        for msg in recent_messages[-8:]:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if not content or role not in ("user", "assistant"):
                continue
            if len(content) > 400:
                content = content[:400] + "..."
            history_lines.append(f"- [{role}] {content}")

    existing = existing_outputs or []
    existing_block = (
        "None yet."
        if not existing
        else "\n".join(f"  - {x}" for x in existing)
    )

    history_block = (
        "No prior messages in this session."
        if not history_lines
        else "\n".join(history_lines)
    )

    return f"""
CURRENT user request (highest priority — plan must reflect THIS message, not only defaults):
{user_message.strip()}

Recent conversation (for context only):
{history_block}

Already generated outputs (SKIP redundant steps if these exist unless user asks to re-run):
{existing_block}

Platform: {platform_note}

You MUST call tools to execute when the user asks for analysis, plot editing, or figure merging; do not only give textual advice.
Do NOT claim files were created unless a tool actually returned a file path.

Allowed tools: use ONLY exact names from available_tools (MCP whitelist + local visual).

Default recommended pipeline (when user does not ask for alternatives):
1. {convert_tool} — input_dir={raw_in}, output_dir={converted} (skip if user uploaded .mzML only, or mzML already covers all .raw)
2. data_preprocessing_xcms — input_dir: mzML from inputspace or {converted} (auto-synced), output_dir={peaks}
3. feature_filtering_and_missing_value_imputation_knn — input_dir={peaks} (feature_table.csv), output_dir={filtered}
4. statistical_analysis_mixomics — input_dir={filtered}, metadata_csv under {upload}, output_dir={statistical}
   (runtime auto-aligns metadata.csv Sample names to the feature table; stale DY-* rows are regenerated)
5. extract_differential_features — differential_csv + input_mgf from prior steps or outputspace, output_dir under outputspace
6. spectral_annotation — input_dir/output_dir under outputspace
7. kegg_compound_enrichment — input_dir/output_dir under outputspace
8. molecular_networking_gnps — input_mgf from differential_spectra.mgf, spectra.mgf, or uploaded .mgf; output_dir={paths.get('molecular_network', paths['outputspace'] + '/molecular_network_results')}
9. deepmass_annotation — input_dir={paths.get('deepmass', paths['outputspace'] + '/deepmass_annotation_results')} (uploaded .mgf auto-copied to differential_spectra.mgf), output_dir={paths.get('deepmass', paths['outputspace'] + '/deepmass_annotation_results')}
10. plot_edit — edit ANY existing result PNG via natural language (title/colors/fonts); for PCA/PLS-DA also supports color_by metadata column or k-means cluster coloring on existing scores (no mixOmics re-run); semantic SVG re-render when data CSV exists, otherwise generic title/style edit; writes edited_plots/
11. image_merge — merge multiple PNGs into one composite under merged_figures/
12. merge_edit — re-layout an existing merged figure (labels/font size/cols) using its .merge.json

Alternatives (pick when user explicitly asks, or when default tool is unsuitable):
- Conversion: convert_raw_to_mzml_OpenMS_FileConverter, data_transformation_proteowizard(_batch), mzml_directory_to_mgf
- Preprocessing: data_preprocessing_openms / mzmine / kpic / pitracer / tracmass / peakonly, mzmine_lcms_datapreprocess
- Peak steps: peak_detection_*, peak_picking_openms, feature_detection_openms, align_*, group_peaks_*, fill_missing_peaks_*, filter_redundant_*, redundant_feature_filtering_*, isotope_analysis_openms, identify_isotopes_openms_IsotopeTools, peak_group_alignment_openms, align_features_mzmine_joint_aligner
- Networking: molecular_networking_fbmn / ms2lda / molnetenhancer
- Library match: library_match_* (cosine/jaccard/spectral_entropy/spec2vec/ms2deepscore/blink/msbert/pair_from_mgf/full_workflow)

CRITICAL path rules after XCMS (default pipeline):
- Do NOT call peak_group_alignment_openms unless *.featureXML already exists under openms_feature_detection_results.
- For molecular_networking_fbmn after XCMS: use peak_detection_results/spectra.mgf (or differential_spectra.mgf) + feature_table.csv / feature_table_filtered_imputed.csv — NEVER require openms_aligned_features/.
- For molecular_networking_ms2lda: use peak_detection_results/spectra.mgf (feature-aligned full MS2 corpus). Do NOT use differential_spectra.mgf for Motif discovery.
- metadata.csv Sample must match feature-table column names; runtime will auto-align/regenerate if mismatched.

If user uploads .mzML only (no .raw), start with data_preprocessing_xcms (or an alternative preprocessing tool if requested) — do NOT require raw conversion.
If user uploads .mgf only and asks for DeepMASS, plan ONLY deepmass_annotation (no XCMS). Empty differential_metabolites.csv is OK.
If the user asks to edit plot style (title/color/font/align) or recolor existing PCA/PLS WITHOUT re-running analysis, plan plot_edit only — never invent PNG paths.
If user asks analysis AND mapping together (做PCA并按Batch着色 / FBMN按化学类看拓扑 / 火山p<0.01 / KEGG按Count着色): plan analysis tools ONLY; runtime auto-recolors/rethresholds afterward. Do NOT plan a chain of plot_edit recolor/threshold/channel steps.
If the user asks to merge images / make a panel figure, plan image_merge AFTER the analysis steps that produce those PNGs (and merge_edit only to adjust an existing merge).
Never invent tool names like plot_merge; the only merge tools are image_merge and merge_edit.
Merged outputs go under merged_figures/ (never merged_plots/).
Preferred plan shape: [analysis tools…] → optional image_merge → optional merge_edit. Keep plot_edit out of analysis+mapping plans.
Figures from statistical_analysis_mixomics / molecular_networking_* / kegg are frontend-editable afterward.

Path roots: upload={upload}, outputspace={paths['outputspace']}

If the user message is casual chat or unrelated to mass spec analysis / plotting / merging, return a plan with ZERO steps (empty plan array).
If outputs already exist in inputspace or outputspace, only plan the steps still needed for the user's current request.
If .raw files exist under {raw_in} but no matching mzML in inputspace or {converted}, the FIRST step MUST be {convert_tool}.
"""


async def _load_allowed_tools():
    return await load_all_tools()


def _needs_mcp_session(tasks: list[str]) -> bool:
    """计划中是否包含需要 MCP stdio 的工具（非本地 visual）。"""
    for task in tasks:
        name = guess_tool_name_from_task(task, ALL_AGENT_TOOL_NAMES)
        name = normalize_agent_tool_name(name)
        if name and not is_local_tool(name):
            return True
        # 未猜到工具名时保守打开 MCP
        if not name:
            lower = task.lower()
            if any(
                alias in lower
                for alias in (
                    "plot_edit",
                    "image_merge",
                    "merge_edit",
                    *LOCAL_TOOL_ALIASES.keys(),
                )
            ):
                continue
            return True
    return False


async def stream_agent_pipeline(
    *,
    user_message: str,
    session_id: str,
    storage_slug: Optional[str] = None,
    project_root: Path,
    persist_dir: str,
    source_dir: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    llm_api_key: Optional[str] = None,
    llm_base_url: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
    is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
    recent_messages: Optional[list[dict]] = None,
) -> AsyncIterator[dict]:
    del persist_dir, source_dir  # Web 流水线不使用 RAG 索引目录

    paths = build_session_paths(session_id, project_root, storage_slug=storage_slug)
    data_list = build_data_list(paths["upload"], paths)
    metadata_csv = build_metadata_csv(paths["upload"])
    existing_outputs = _scan_existing_outputs(paths)
    goal = build_web_goal_description(
        user_message,
        paths,
        existing_outputs=existing_outputs,
        recent_messages=recent_messages,
    )
    history_summary: list[dict] = []

    async def _should_stop() -> bool:
        if is_cancelled(cancel_event):
            return True
        if is_disconnected is not None and await is_disconnected():
            return True
        return False

    yield {"delta": "🔧 **Agent 模式**：正在加载工具列表并生成执行计划…\n\n"}

    try:
        tools_info = await _load_allowed_tools()
    except Exception as exc:
        yield {"error": f"加载 MCP 工具失败: {exc}"}
        return

    if not tools_info:
        yield {"error": "未找到可用的 MCP 工具，请检查 server.py 注册与白名单。"}
        return

    # yield {"delta": f"已注册 **{len(tools_info)}** 个 MCP 工具（Web 白名单）。\n\n"}

    loop = asyncio.get_event_loop()
    llm = WebLLMClient(
        model=model,
        api_key=llm_api_key,
        base_url=llm_base_url,
    )

    convert_tool = str(preferred_raw_converter()["tool"])
    mandatory_first_step = None
    if raw_conversion_needed(paths):
        mandatory_first_step = build_conversion_plan_step(paths, convert_tool)

    def _plan():
        prompt = build_plan_prompt(
            goal_description=goal,
            data_list=data_list,
            metadata_csv=metadata_csv,
            outputspace=paths["outputspace"],
            tools_info=tools_info,
            existing_outputs=existing_outputs,
            user_message=user_message,
            mandatory_first_step=mandatory_first_step,
        )
        return llm.think_complete(
            [{"role": "user", "content": str(prompt)}],
            temperature=temperature,
            max_tokens=8192,
        )

    yield {"delta": "📋 正在调用 LLM 生成计划…\n"}
    try:
        plan_resp = await loop.run_in_executor(None, _plan)
    except Exception as exc:
        yield {"error": f"计划生成失败: {exc}"}
        return

    if await _should_stop():
        yield {"delta": "\n\n⚠️ **已终止**（计划阶段）\n"}
        yield {"cancelled": True}
        return

    if not plan_resp:
        yield {
            "error": (
                "计划生成失败：LLM 返回为空。"
                "若刚看到欠费/鉴权报错，请先处理阿里云账户；"
                "否则请检查模型名、API 密钥与网络。"
            )
        }
        return

    tasks = extract_plan_list(plan_resp)
    tasks = normalize_plan_tasks_for_platform(tasks)
    tool_names = [t.name for t in tools_info]
    tasks_filtered = filter_plan_tasks_to_registered_tools(tasks, tool_names)

    if not tasks_filtered and tasks:
        yield {
            "delta": "⚠️ 计划步骤未匹配到已注册工具名，将尝试从文本中保留含 Use 的步骤…\n"
        }
        tasks_filtered = [t for t in tasks if "use " in t.lower()]

    tasks = tasks_filtered

    if raw_conversion_needed(paths):
        tasks = ensure_raw_conversion_step(tasks, paths, convert_tool)
        yield {
            "delta": f"ℹ️ 格式转换环境：{conversion_environment_hint()}\n\n"
        }

    blocked, block_reason = differential_downstream_blocked(paths)
    if blocked:
        pruned, removed = prune_differential_dependent_tasks(tasks)
        if removed:
            tasks = pruned
            yield {
                "delta": (
                    "ℹ️ 无差异代谢物表，已跳过差异提取/谱库注释/KEGG 富集相关步骤；"
                    "上传 .mgf 时仍可执行分子网络或 DeepMASS。\n\n"
                )
            }

    tasks = inject_mgf_standalone_tasks(tasks, user_message, paths, tool_names)
    tasks = inject_visual_standalone_tasks(tasks, user_message, tool_names)
    try:
        from web_frontend.backend.session_metadata import (
            list_metadata_columns,
            resolve_metadata_csv,
        )

        meta_for_intent = resolve_metadata_csv(paths["upload"])
        meta_cols = [str(c["name"]) for c in list_metadata_columns(meta_for_intent)]
    except Exception:
        meta_for_intent = None
        meta_cols = []
    before_prune = list(tasks)
    tasks, intent_info = inject_analysis_coloring_tasks(
        tasks,
        user_message,
        tool_names,
        metadata_csv=str(meta_for_intent) if meta_for_intent else None,
        metadata_columns=meta_cols,
    )
    intent_obj = intent_info.get("intent") or {}
    removed_plot_edits = intent_info.get("removed_plot_edits") or [
        t for t in before_prune if t not in tasks
    ]
    if removed_plot_edits:
        yield {
            "delta": (
                "ℹ️ 已从计划中去掉分析意图类 plot_edit（着色/阈值/通道）；"
                "将在对应分析工具成功后自动按意图重绘。"
                f"已去掉 {len(removed_plot_edits)} 步。\n\n"
            )
        }
    removed_by_intent = intent_info.get("removed_by_intent") or []
    if removed_by_intent:
        from web_frontend.backend.analysis_intent import describe_intent

        label = describe_intent(intent_obj) or "分析意图"
        yield {
            "delta": (
                f"ℹ️ 已按意图裁剪计划（{label}）：去掉 {len(removed_by_intent)} 步旁支分析"
                f"（如不要网络 / 只要指定图）。\n\n"
            )
        }
    for err in intent_obj.get("errors") or []:
        yield {"delta": f"⚠️ 分析意图校验：{err}\n\n"}
    for warn in intent_obj.get("warnings") or []:
        yield {"delta": f"ℹ️ {warn}\n\n"}

    if not tasks:
        parsed = extract_first_json_object(plan_resp or "")
        if isinstance(parsed.get("plan"), list) and len(parsed.get("plan")) == 0:
            yield {
                "delta": (
                    "ℹ️ 当前消息未触发工具执行。"
                    "如需分析，请描述具体目标（如「继续跑 XCMS」），或在发送时上传新文件。\n"
                )
            }
            return
        yield {
            "delta": "⚠️ 未能解析出可执行计划，原始响应：\n"
            + (plan_resp or "")[:3000]
            + "\n\n"
        }
        yield {"error": "计划为空或未包含已注册工具，未执行。"}
        return

    history_summary.append({"role": "user", "content": f"Plan: {tasks}"})
    yield {"delta": f"✅ 计划共 **{len(tasks)}** 步：\n"}
    for i, t in enumerate(tasks, 1):
        yield {"delta": f"  {i}. {t}\n"}
    yield {"delta": "\n---\n\n"}

    allowed_set = set(ALL_AGENT_TOOL_NAMES)
    agent_ctx = AgentContext(
        project_root=project_root,
        session_id=session_id,
        storage_slug=storage_slug or session_id,
        paths=paths,
        model=model,
        user_message=user_message,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
    )
    visual_results: list[dict[str, Any]] = []
    open_mcp = _needs_mcp_session(tasks)

    async def _run_task_loop(session: Optional[ClientSession]):
        nonlocal visual_results
        while tasks:
            if await _should_stop():
                yield {
                    "delta": "\n\n⚠️ **已终止**：后续步骤已跳过。\n"
                }
                yield {"cancelled": True}
                return

            task = tasks.pop(0)
            yield {"delta": f"\n### 执行任务\n{task}\n\n"}
            yield {"delta": "🔍 正在匹配工具…\n"}

            def _match_tool():
                prompt = build_tool_match_prompt(
                    goal_description=goal,
                    task=task,
                    outputspace=paths["outputspace"],
                    tools_info=tools_info,
                    history_summary=history_summary,
                )
                return llm.think(
                    [{"role": "user", "content": str(prompt)}],
                    temperature=temperature,
                    stream_to_stdout=False,
                )

            raw_match = None
            try:
                raw_match = await loop.run_in_executor(None, _match_tool)
            except Exception as exc:
                yield {"delta": f"⚠️ LLM 匹配异常: {exc}，尝试从任务文本推断工具…\n"}

            tool_name, tool_args = parse_tool_call(raw_match or "")
            tool_name = normalize_agent_tool_name(tool_name)
            if not tool_name:
                tool_name = guess_tool_name_from_task(task, allowed_set)
                tool_name = normalize_agent_tool_name(tool_name)
                if tool_name:
                    yield {"delta": f"ℹ️ 已从任务描述推断工具：**{tool_name}**，正在再次请求参数…\n"}
                    retry_prompt = build_tool_match_prompt(
                        goal_description=goal,
                        task=task,
                        outputspace=paths["outputspace"],
                        tools_info=[
                            t for t in tools_info if getattr(t, "name", None) == tool_name
                        ],
                        history_summary=history_summary,
                    )
                    try:
                        raw2 = await loop.run_in_executor(
                            None,
                            lambda: llm.think(
                                [{"role": "user", "content": str(retry_prompt)}],
                                temperature=temperature,
                                stream_to_stdout=False,
                            ),
                        )
                        tool_name, tool_args = parse_tool_call(raw2 or "")
                        tool_name = normalize_agent_tool_name(tool_name)
                    except Exception:
                        pass

            if not tool_name:
                err = f"未能解析工具调用：\n{(raw_match or '')[:1200]}\n"
                history_summary.append({"role": "tool", "content": err})
                yield {"delta": f"⚠️ {err}\n"}
                continue

            # 本地 visual 工具：不走 MCP，直接执行
            if is_local_tool(tool_name):
                if not tool_args or not isinstance(tool_args, dict):
                    tool_args = {}
                # 始终带上用户原文 + 计划步骤，避免丢掉中文约束（两列/ABCD/字号）
                existing_instruction = str(tool_args.get("instruction") or "").strip()
                tool_args["instruction"] = "\n".join(
                    part for part in (user_message, task, existing_instruction) if part and str(part).strip()
                ).strip()
                yield {"delta": f"🛠 调用本地工具 **{tool_name}** …\n"}
                try:
                    payload = await loop.run_in_executor(
                        None,
                        lambda: run_local_tool(tool_name, tool_args, agent_ctx),
                    )
                    result_str = format_local_tool_result(payload)
                    history_summary.append({"role": "tool", "content": result_str[:4000]})
                    for fpath in payload.get("files") or []:
                        visual_results.append(
                            {
                                "kind": payload.get("kind") or tool_name,
                                "file": fpath,
                            }
                        )
                    yield {"delta": f"✅ **{tool_name}** 完成：\n{result_str}\n\n"}
                except Exception as exc:
                    err_msg = f"工具 {tool_name} 失败: {exc}"
                    history_summary.append({"role": "tool", "content": err_msg})
                    yield {"delta": f"❌ {err_msg}\n\n"}
                continue

            blocked, block_reason = differential_downstream_blocked(paths)
            if blocked and tool_name in {
                "extract_differential_features",
                "spectral_annotation",
                "kegg_compound_enrichment",
            }:
                yield {
                    "delta": (
                        f"⏭️ 跳过 **{tool_name}**：{block_reason}\n\n"
                    )
                }
                continue

            conv_blocked, conv_reason = conversion_downstream_blocked(paths)
            if conv_blocked and tool_name in MZML_DEPENDENT_TOOLS:
                yield {
                    "delta": (
                        f"⏭️ 跳过 **{tool_name}**：{conv_reason}\n\n"
                    )
                }
                continue

            openms_blocked, openms_reason = openms_featurexml_blocked(paths)
            if openms_blocked and tool_name in OPENMS_FEATUREXML_TOOLS:
                yield {
                    "delta": (
                        f"⏭️ 跳过 **{tool_name}**：{openms_reason}\n\n"
                    )
                }
                continue

            if not tool_args or not isinstance(tool_args, dict):
                tool_args = {}

            try:
                normalized = normalize_tool_args(
                    tool_name, tool_args, paths, paths["upload"]
                )
            except FileNotFoundError as exc:
                # 缺输入时给出可继续的提示，避免整条流水线硬崩
                if tool_name in OPENMS_FEATUREXML_TOOLS or tool_name in {
                    "molecular_networking_fbmn",
                    "molecular_networking_ms2lda",
                    "feature_detection_openms",
                    "peak_picking_openms",
                    "peak_detection_openms_peakpickerhires",
                    "peak_detection_openms_featurefinder",
                    "spectral_annotation",
                    "kegg_compound_enrichment",
                }:
                    yield {
                        "delta": (
                            f"⏭️ 跳过 **{tool_name}**：{exc}\n\n"
                        )
                    }
                    continue
                raise
            if normalized != tool_args:
                yield {
                    "delta": (
                        "ℹ️ 已按 MCP 工具定义自动修正参数"
                        f"（`{tool_args}` → `{normalized}`）。\n"
                    )
                }
            tool_args = normalized

            if is_raw_converter(tool_name):
                tool_name = resolve_initial_raw_converter(tool_name)
                fallback_order = raw_converter_fallback_order(tool_name)
                if len(fallback_order) > 1:
                    yield {
                        "delta": (
                            "ℹ️ 格式转换将自动在以下工具间回退："
                            + " → ".join(f"`{n}`" for n in fallback_order)
                            + "。\n"
                        )
                    }

            hint = TOOL_RUNTIME_HINTS.get(tool_name)
            if hint:
                yield {"delta": f"🛠 调用 **{tool_name}** …\nℹ️ {hint}\n"}
            else:
                yield {"delta": f"🛠 调用 **{tool_name}** …\n"}

            try:
                result = None
                result_str = None
                conversion_failed = False
                if tool_name == "data_preprocessing_xcms":
                    from web_frontend.backend.xcms_patched_run import (
                        run_data_preprocessing_xcms,
                    )

                    def _run_xcms_patched():
                        return run_data_preprocessing_xcms(
                            tool_args.get("input_dir", paths["converted_mzml"]),
                            tool_args.get(
                                "output_dir", paths["peaks"]
                            ),
                            blank_pattern=tool_args.get(
                                "blank_pattern", "QC"
                            ),
                            file_pattern=tool_args.get(
                                "file_pattern", "*.mzML"
                            ),
                        )
                    log_path = await loop.run_in_executor(
                        None, _run_xcms_patched
                    )
                    result = type(
                        "R",
                        (),
                        {
                            "content": [
                                type(
                                    "T",
                                    (),
                                    {
                                        "text": (
                                            f"XCMS 完成，日志: {log_path}，"
                                            f"输出: {tool_args.get('output_dir', paths['peaks'])}"
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                elif tool_name == "feature_filtering_and_missing_value_imputation_knn":
                    from web_frontend.backend.feature_filter_runner import (
                        run_feature_filtering_knn,
                    )

                    def _run_knn_filter():
                        return run_feature_filtering_knn(
                            tool_args.get("input_dir", paths["peaks"]),
                            tool_args.get("output_dir", paths["filtered"]),
                            min_presence=float(
                                tool_args.get("min_presence", 0.5)
                            ),
                            min_intensity=float(
                                tool_args.get("min_intensity", 0.0)
                            ),
                            n_neighbors=int(tool_args.get("n_neighbors", 5)),
                        )

                    out_csv = await loop.run_in_executor(None, _run_knn_filter)
                    result = type(
                        "R",
                        (),
                        {
                            "content": [
                                type(
                                    "T",
                                    (),
                                    {
                                        "text": (
                                            "Feature filtering and KNN imputation completed.\n"
                                            f"Output: {out_csv}"
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                elif tool_name == "statistical_analysis_mixomics":
                    from web_frontend.backend.mixomics_runner import (
                        run_statistical_analysis_mixomics,
                    )

                    def _run_mixomics():
                        return run_statistical_analysis_mixomics(
                            tool_args.get("input_dir", paths["filtered"]),
                            tool_args.get("metadata_csv", paths["upload"]),
                            tool_args.get("output_dir", paths["statistical"]),
                            ncomp_pca=int(tool_args.get("ncomp_pca", 5)),
                            ncomp_plsda=int(tool_args.get("ncomp_plsda", 2)),
                            scale_method=str(
                                tool_args.get("scale_method", "autoscale")
                            ),
                            top_n_heatmap=int(
                                tool_args.get("top_n_heatmap", 50)
                            ),
                            seed=int(tool_args.get("seed", 123)),
                        )

                    yield {
                        "delta": "ℹ️ 使用**日志重定向**运行 mixOmics（避免 MCP 管道死锁）…\n"
                    }
                    log_path = await loop.run_in_executor(None, _run_mixomics)
                    pruned_tasks, prune_reason = _prune_remaining_differential_tasks(
                        tasks, paths
                    )
                    if prune_reason and len(pruned_tasks) < len(tasks):
                        tasks[:] = pruned_tasks
                        yield {
                            "delta": (
                                f"ℹ️ 统计未产生差异代谢物：{prune_reason}\n"
                                "已跳过差异提取、谱库注释与 KEGG 富集。"
                                "若已有 spectra.mgf 或上传了 .mgf，仍可运行 molecular_networking_gnps / deepmass_annotation。\n"
                            )
                        }
                    result = type(
                        "R",
                        (),
                        {
                            "content": [
                                type(
                                    "T",
                                    (),
                                    {
                                        "text": (
                                            "Statistical analysis completed.\n"
                                            f"Log: {log_path}\n"
                                            f"Output: {tool_args.get('output_dir', paths['statistical'])}"
                                        )
                                    },
                                )()
                            ]
                        },
                    )()
                else:
                    if session is None:
                        raise RuntimeError(
                            f"工具 {tool_name} 需要 MCP 会话，但当前未启动 MCP"
                        )
                    if is_raw_converter(tool_name):
                        result_str = None
                        async for ev in call_raw_converter_with_fallback(
                            session, tool_name, tool_args, paths
                        ):
                            if ev["type"] == "delta":
                                yield {"delta": ev["text"]}
                            elif ev["type"] == "tick":
                                yield {
                                    "delta": format_tick_message(
                                        ev["tool_name"],
                                        ev.get("elapsed_sec", 0),
                                    )
                                }
                            elif ev["type"] == "done":
                                tool_name = ev["tool_name"]
                                result = ev["result"]
                                result_str = ev["result_str"]
                                conversion_failed = bool(ev.get("all_failed"))
                                if conversion_failed:
                                    pruned, _removed = prune_mzml_dependent_tasks(
                                        tasks
                                    )
                                    if len(pruned) < len(tasks):
                                        tasks[:] = pruned
                                        yield {
                                            "delta": (
                                                "⚠️ 格式转换未成功，已跳过后续 XCMS 及下游步骤。"
                                                f" {conversion_environment_hint()}\n\n"
                                            )
                                        }
                    else:
                        async for ev in call_tool_with_heartbeat(
                            session, tool_name, tool_args
                        ):
                            if ev["type"] == "tick":
                                yield {
                                    "delta": format_tick_message(
                                        tool_name, ev.get("elapsed_sec", 0)
                                    )
                                }
                            elif ev["type"] == "result":
                                result = ev["result"]
                            elif ev["type"] == "error":
                                raise ev["error"]

                if result_str is None:
                    result_str = format_mcp_tool_result(result)
                history_summary.append(
                    {"role": "tool", "content": result_str[:4000]}
                )
                if is_mcp_tool_result_error(result, result_str) or conversion_failed:
                    fail_title = f"❌ **{tool_name}** 失败"
                    if conversion_failed:
                        fail_title = "❌ **格式转换** 全部候选工具均失败"
                    yield {
                        "delta": (
                            f"{fail_title}：\n{result_str}\n\n"
                            "ℹ️ 后续步骤可能因缺少输入文件而无法继续，请修复后重试。\n\n"
                        )
                    }
                    if is_raw_converter(tool_name) or (
                        tool_name in MZML_DEPENDENT_TOOLS
                        and conversion_downstream_blocked(paths)[0]
                    ):
                        pruned, _removed = prune_mzml_dependent_tasks(tasks)
                        if len(pruned) < len(tasks):
                            tasks[:] = pruned
                else:
                    yield {"delta": f"✅ **{tool_name}** 完成：\n{result_str}\n\n"}
                    # 出图工具成功后补写语义 sidecar，并按分析意图确定性重绘
                    if tool_name in {
                        "statistical_analysis_mixomics",
                        "molecular_networking_gnps",
                        "molecular_networking_fbmn",
                        "molecular_networking_ms2lda",
                        "molecular_networking_molnetenhancer",
                        "kegg_compound_enrichment",
                    }:
                        try:
                            from web_frontend.backend.plot_edit_service import (
                                ensure_default_plot_configs,
                            )

                            out_dir = tool_args.get("output_dir") or paths.get("outputspace")
                            written = await loop.run_in_executor(
                                None,
                                lambda: ensure_default_plot_configs(
                                    out_dir or paths["outputspace"],
                                    upload_dir=paths.get("upload"),
                                ),
                            )
                            # 再扫一遍会话 output 根，覆盖嵌套目录
                            if paths.get("outputspace") and Path(str(out_dir or "")).resolve() != Path(
                                paths["outputspace"]
                            ).resolve():
                                written2 = await loop.run_in_executor(
                                    None,
                                    lambda: ensure_default_plot_configs(
                                        paths["outputspace"],
                                        upload_dir=paths.get("upload"),
                                    ),
                                )
                                written = list(written) + list(written2)
                            if written:
                                yield {
                                    "delta": (
                                        f"📎 已为 {len(written)} 张结果图生成/更新语义编辑 sidecar。\n"
                                    )
                                }
                        except Exception as sidecar_exc:
                            yield {
                                "delta": f"⚠️ 语义 sidecar 生成跳过：{sidecar_exc}\n"
                            }
                        try:
                            from web_frontend.backend.analysis_intent import (
                                describe_intent,
                                has_analysis_plot_intent,
                                parse_analysis_intent,
                            )
                            from web_frontend.backend.plot_edit_service import (
                                apply_analysis_intent_after_tool,
                            )

                            if has_analysis_plot_intent(user_message):
                                intent_preview = parse_analysis_intent(user_message)
                                label = describe_intent(intent_preview) or "分析意图"
                                yield {
                                    "delta": (
                                        f"🎨 检测到分析意图（{label}），"
                                        "正在按意图重绘相关结果图…\n"
                                    )
                                }
                                out_for_intent = tool_args.get("output_dir") or paths.get(
                                    "outputspace"
                                )
                                coloring_results = await loop.run_in_executor(
                                    None,
                                    lambda: apply_analysis_intent_after_tool(
                                        project_root=project_root,
                                        session_id=session_id,
                                        storage_slug=storage_slug or session_id,
                                        user_message=user_message,
                                        tool_name=tool_name,
                                        output_dir=out_for_intent,
                                    ),
                                )
                                for item in coloring_results:
                                    if item.get("error"):
                                        yield {
                                            "delta": (
                                                f"⚠️ 意图重绘失败（{item.get('stem')}）："
                                                f"{item['error']}\n"
                                            )
                                        }
                                        continue
                                    fname = (item.get("file") or {}).get("name")
                                    if fname:
                                        visual_results.append(
                                            {"kind": "plot_edit", "file": fname}
                                        )
                                        yield {
                                            "delta": (
                                                f"✅ 已按意图重绘：`{fname}`"
                                                f"（{item.get('analysis_intent') or label}）\n"
                                            )
                                        }
                                if any(not r.get("error") for r in coloring_results):
                                    tasks[:] = [
                                        t
                                        for t in tasks
                                        if not (
                                            "plot_edit" in str(t).lower()
                                            and (
                                                "recolor" in str(t).lower()
                                                or "color_by" in str(t).lower()
                                                or "cluster" in str(t).lower()
                                                or "thresholds" in str(t).lower()
                                                or "color_channel" in str(t).lower()
                                                or "着色" in str(t)
                                            )
                                        )
                                    ]
                        except Exception as coloring_exc:
                            yield {
                                "delta": f"⚠️ 分析意图重绘跳过：{coloring_exc}\n"
                            }
            except Exception as exc:
                err_msg = (
                    f"工具 {tool_name} 失败: {exc}\n{traceback.format_exc()}"
                )
                history_summary.append({"role": "tool", "content": err_msg})
                yield {"delta": f"❌ {err_msg}\n\n"}
                if tool_name in MZML_DEPENDENT_TOOLS or is_raw_converter(tool_name):
                    pruned, _removed = prune_mzml_dependent_tasks(tasks)
                    if len(pruned) < len(tasks):
                        tasks[:] = pruned

    try:
        if open_mcp:
            params = mcp_stdio_parameters()
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    async for event in _run_task_loop(session):
                        yield event
                        if event.get("cancelled"):
                            return
        else:
            yield {"delta": "ℹ️ 本计划仅含本地工具（改图/拼图），跳过 MCP 子进程。\n\n"}
            async for event in _run_task_loop(None):
                yield event
                if event.get("cancelled"):
                    return

        done_payload: dict[str, Any] = {
            "delta": "\n\n---\n🎉 **所有计划任务已执行完毕。**\n"
            f"✅ 结果已写入 **outputspace/{storage_slug or session_id}/**。\n"
        }
        if visual_results:
            done_payload["visual_results"] = visual_results
            files_line = "、".join(v["file"] for v in visual_results)
            done_payload["delta"] += f"🖼️ 视觉产物：{files_line}\n"
        yield done_payload
        if visual_results:
            yield {"visual_results": visual_results, "finished": True}

    except Exception as exc:
        yield {"delta": f"\n❌ Agent 执行中断: {exc}\n{traceback.format_exc()}\n"}
        yield {"error": str(exc)}
