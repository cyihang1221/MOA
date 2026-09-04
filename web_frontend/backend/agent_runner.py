"""
Web 端编排：A 规划、B 执行、C 出图（三个独立智能体）。

默认 Agent B 走 MassOmics-Agent-B（origin/B）独立进程，不使用本仓库 src/mcp_server。
``WEB_AGENT_B_BACKEND=local`` 时仍可回退到本地 MCP。
RAG 索引目录由 webapp 传入（softwares_database / softwares_database_RAG）。
"""
from __future__ import annotations

import asyncio
import re
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
from web_frontend.backend.agent_jobs import (
    get_thread_cancel_flag,
    is_cancelled,
    kill_session_processes,
)
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
from web_frontend.backend.anti_hallucination import (
    PLAN_SYSTEM_GUARD,
    TOOL_MATCH_SYSTEM_GUARD,
    messages_with_system,
)
from web_frontend.backend.web_prompts import build_plan_prompt, build_tool_match_prompt
from web_frontend.backend.literature_rag import (
    build_plan_literature_query,
    retrieve_literature,
)
from web_frontend.backend.skill_match import env_enabled as skill_match_enabled
from web_frontend.backend.skill_match import match_skills


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


def build_data_list(upload_dir: str, paths: dict[str, str], *, meta_report: dict | None = None) -> str:
    return "\n".join(summarize_session_files(paths, upload_dir, meta_report=meta_report))


def build_metadata_csv(upload_dir: str, *, report: dict | None = None) -> str:
    from web_frontend.backend.session_metadata import format_metadata_file_description

    return format_metadata_file_description(upload_dir, report=report)


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


_PLAN_REVIEW_FOOTER = (
    "\n\n---\n\n"
    "请审阅上述计划后回复 **确认计划**；修改意见将重新规划。未确认前不会执行。\n"
)


def _plan_preview_for_chat(preview: str) -> str:
    """计划正文后附审阅提示；若文末已有「确认计划」则不再重复。"""
    body = (preview or "").rstrip()
    if not body:
        return _PLAN_REVIEW_FOOTER
    if "确认计划" in body[-1200:]:
        return body + "\n"
    return body + _PLAN_REVIEW_FOOTER


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
ANTI-HALLUCINATION: emit a plan of Use <tool> steps only — never fake progress logs, success reports, or invented paths.

Allowed tools: use ONLY exact names from available_tools (MCP whitelist + local visual).

Default recommended pipeline (when user does not ask for alternatives):
1. {convert_tool} — input_dir={raw_in}, output_dir={converted} (skip if user uploaded .mzML only, or mzML already covers all .raw)
2. data_preprocessing_xcms — input_dir: mzML from inputspace or {converted} (auto-synced), output_dir={peaks}
3. feature_filtering_and_missing_value_imputation_knn — input_dir={peaks} (feature_table.csv), output_dir={filtered}
4. statistical_analysis_mixomics — input_dir={filtered}, metadata_csv under {upload}, output_dir={statistical}
   (runtime auto-aligns metadata.csv Sample names to the feature table; stale DY-* rows are regenerated)
   Optional args from user intent: group_column (PLS-DA Y, default Group), contrast_group1/contrast_group2 (volcano A vs B)
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


def _append_output_png_visuals(
    visual_results: list[dict[str, Any]],
    out_dir: str | Path | None,
    root: Path,
    *,
    kind: str,
    limit: int = 24,
) -> int:
    """把工具输出目录下的 PNG 记入 visual_results（供聊天预览 / 图库刷新）。"""
    if not out_dir:
        return 0
    base = Path(str(out_dir))
    if not base.is_dir():
        return 0
    existing = {
        str(item.get("file") or "").strip()
        for item in visual_results
        if isinstance(item, dict)
    }
    pngs = [
        p
        for p in base.rglob("*.png")
        if p.is_file() and "edited_plots" not in p.parts
    ]
    pngs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    added = 0
    root_res = root.resolve()
    for png in pngs:
        if added >= limit:
            break
        try:
            rel = png.resolve().relative_to(root_res).as_posix()
        except Exception:
            continue
        if rel in existing:
            continue
        visual_results.append({"kind": kind, "file": rel})
        existing.add(rel)
        added += 1
    return added


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
    mode: str = "full",
) -> AsyncIterator[dict]:
    paths = build_session_paths(session_id, project_root, storage_slug=storage_slug)
    meta_report: dict | None = None
    try:
        from web_frontend.backend.session_metadata import (
            ensure_metadata_from_inputs,
            format_metadata_report_summary,
        )

        _, meta_report = ensure_metadata_from_inputs(paths["upload"], paths=paths)
    except FileNotFoundError:
        meta_report = None
    except Exception:
        meta_report = None

    data_list = build_data_list(paths["upload"], paths, meta_report=meta_report)
    metadata_csv = build_metadata_csv(paths["upload"], report=meta_report)
    existing_outputs = _scan_existing_outputs(paths)
    goal = build_web_goal_description(
        user_message,
        paths,
        existing_outputs=existing_outputs,
        recent_messages=recent_messages,
    )
    history_summary: list[dict] = []
    loop = asyncio.get_event_loop()
    literature_context = ""
    literature_mode = "empty"
    skill_context = ""
    skill_matched: list[str] = []

    async def _should_stop() -> bool:
        if is_cancelled(cancel_event):
            return True
        if is_disconnected is not None and await is_disconnected():
            return True
        return False

    async def _run_cancellable(fn, *, label: str = "任务"):
        """在线程池跑阻塞任务；取消时杀子进程并尽快返回。"""
        flag = get_thread_cancel_flag(session_id) if session_id else None
        task = loop.run_in_executor(None, fn)

        def _cancelled_payload(exc: BaseException | None = None):
            extra = f"（{exc}）" if exc and "已终止" not in str(exc) else ""
            return ("__cancelled__", f"\n\n**已终止**：已停止{label}{extra}。\n")

        while True:
            if await _should_stop():
                if flag is not None:
                    flag.set()
                kill_session_processes(session_id)
                try:
                    result = await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
                    if isinstance(result, BaseException):
                        return _cancelled_payload(result)
                    return result
                except asyncio.TimeoutError:
                    return _cancelled_payload()
                except Exception as exc:
                    return _cancelled_payload(exc)
            done, _ = await asyncio.wait({task}, timeout=0.4)
            if done:
                try:
                    return task.result()
                except Exception as exc:
                    if await _should_stop() or "已终止" in str(exc):
                        return _cancelled_payload(exc)
                    raise

    mode_norm = (mode or "full").strip().lower()
    if mode_norm not in {"plan", "execute", "full"}:
        mode_norm = "full"

    if mode_norm == "execute":
        yield {"delta": "🔒 **Agent B**：加载已确认计划并执行（不重新规划）…\n\n"}
    elif mode_norm == "plan":
        yield {"delta": "📋 **Agent A**：根据数据与目标生成分析计划（确认前不执行）…\n\n"}
    else:
        yield {"delta": "🔧 **Agent 模式**：正在加载工具列表并生成执行计划…\n\n"}
    if meta_report:
        from web_frontend.backend.session_metadata import format_metadata_report_summary

        summary = format_metadata_report_summary(meta_report)
        if summary:
            yield {
                "delta": (
                    f"ℹ️ **样本分组**：{summary}"
                    "（metadata.csv 已写入会话 inputspace，mixOmics/PCA 将使用此分组）\n\n"
                )
            }

    if mode_norm == "execute":
        from web_frontend.backend.agent_backends import agent_b_backend

        if agent_b_backend() == "massomics":
            from web_frontend.backend.agent_b.massomics_executor import (
                stream_massomics_b_execution,
            )

            async for event in stream_massomics_b_execution(
                paths=paths,
                session_id=session_id,
                project_root=Path(project_root),
                cancel_event=cancel_event,
                should_stop=_should_stop,
            ):
                yield event
            return

    try:
        tools_info = await _load_allowed_tools()
    except Exception as exc:
        yield {"error": f"加载 MCP 工具失败: {exc}"}
        return

    if not tools_info:
        yield {"error": "未找到可用的 MCP 工具，请检查 server.py 注册与白名单。"}
        return

    # yield {"delta": f"已注册 **{len(tools_info)}** 个 MCP 工具（Web 白名单）。\n\n"}

    llm = WebLLMClient(
        model=model,
        api_key=llm_api_key,
        base_url=llm_base_url,
    )

    convert_tool = str(preferred_raw_converter()["tool"])
    mandatory_first_step = None
    if raw_conversion_needed(paths):
        mandatory_first_step = build_conversion_plan_step(paths, convert_tool)

    tasks: list[str] = []
    skip_planning = mode_norm == "execute"
    if skip_planning:
        from web_frontend.backend.agent_a.plan_document import load_executable_tasks

        tasks = load_executable_tasks(Path(paths["outputspace"]))
        if not tasks:
            yield {
                "error": (
                    "未找到已锁定的可执行计划（analysis_plan.json 中 executable_tasks）。"
                    "请先生成并确认计划。"
                )
            }
            return
        history_summary.append({"role": "user", "content": f"Plan: {tasks}"})
        yield {"delta": f"✅ 已加载锁定计划，共 **{len(tasks)}** 步：\n"}
        for i, t in enumerate(tasks, 1):
            yield {"delta": f"  {i}. {t}\n"}
        yield {"delta": "\n---\n\n"}

    if not skip_planning:
        from web_frontend.backend.agent_backends import (
            agent_a_backend,
            agent_b_backend,
            backend_status,
            massomics_available,
        )

        bs = backend_status(Path(project_root))
        a_backend = bs["agent_a_backend"]
        b_backend = bs["agent_b_backend"]
        yield {
            "delta": (
                f"🧭 **Agent A 后端**：`{a_backend}` · **Agent B 后端**：`{b_backend}`\n"
                f"   MassOmics 根目录：`{bs['massomics_root']}`"
                f"（{'可用' if bs['massomics_available'] else '不可用'}）\n\n"
            )
        }
        for w in bs.get("warnings") or []:
            yield {"delta": f"⚠️ {w}\n\n"}

        plan_doc_massomics: dict[str, Any] | None = None
        plan_resp: str | None = None
        used_a = "local"

        if skill_match_enabled():
            yield {"delta": "🧩 正在匹配文献参数 Skill…\n"}
            try:
                skill_payload = match_skills(
                    f"{user_message}\n{goal}",
                    project_root=Path(project_root),
                )
                skill_context = str(skill_payload.get("text") or "")
                skill_matched = list(skill_payload.get("matched") or [])
                skill_err = skill_payload.get("error")
                if skill_matched:
                    yield {
                        "delta": (
                            f"✅ 已注入 Skill：{', '.join(skill_matched)}"
                            f"（约 {len(skill_context)} 字符）。\n\n"
                        )
                    }
                elif skill_err:
                    yield {"delta": f"ℹ️ Skill 未加载（{skill_err}）。\n\n"}
                else:
                    yield {"delta": "ℹ️ 未命中场景 Skill 触发词，继续默认规划。\n\n"}
            except Exception as exc:
                yield {"delta": f"ℹ️ Skill 匹配跳过（{exc}）。\n\n"}

        if a_backend == "massomics" and massomics_available(Path(project_root)):
            from web_frontend.backend.agent_a.massomics_planner import run_massomics_planning

            yield {
                "delta": (
                    "📋 **MassOmics-Agent 规划**：加载 KnowledgeBase + 数据探测，"
                    "生成 PlanDocument…\n"
                )
            }
            tool_names_pre = [t.name for t in tools_info]

            def _massomics_plan():
                return run_massomics_planning(
                    user_message=user_message,
                    goal=goal,
                    data_list=data_list if isinstance(data_list, str) else str(data_list),
                    paths=paths,
                    registered_tools=tool_names_pre,
                    llm_client=llm,
                    temperature=temperature,
                    project_root=Path(project_root),
                    skill_context=skill_context or None,
                )

            try:
                mo_result = await _run_cancellable(_massomics_plan, label="MassOmics 规划")
            except Exception as exc:
                mo_result = exc

            if (
                isinstance(mo_result, tuple)
                and len(mo_result) == 2
                and mo_result[0] == "__cancelled__"
            ):
                yield {"delta": mo_result[1]}
                yield {"cancelled": True}
                return

            if isinstance(mo_result, Exception):
                yield {
                    "delta": (
                        f"⚠️ MassOmics 规划失败（{mo_result}），"
                        "回退 Web 本地规划（softwares_database RAG）。\n\n"
                    )
                }
            else:
                tasks, plan_doc_massomics, mo_meta = mo_result
                if tasks:
                    used_a = "massomics"
                    skills_hint = ", ".join(mo_meta.get("matched_skills") or []) or "—"
                    yield {
                        "delta": (
                            f"✅ MassOmics 规划完成：{mo_meta.get('n_steps', 0)} 步方案 → "
                            f"{mo_meta.get('n_tasks_mapped', 0)} 条 Web 可执行任务"
                            f"（文献 RAG={'有' if mo_meta.get('has_literature_rag') else '无'}"
                            f"，数据探测={'有' if mo_meta.get('data_inspect') else '无'}"
                            f"，skills 示例：{skills_hint}）。\n\n"
                        )
                    }
                else:
                    yield {
                        "delta": (
                            "⚠️ MassOmics 计划未能映射到 Web MCP 工具，"
                            "回退 Web 本地规划。\n\n"
                        )
                    }

        if used_a == "local":
            yield {"delta": "📚 正在检索文献/方法学知识库…\n"}

        if used_a == "local":
            def _retrieve_literature():
                return retrieve_literature(
                    build_plan_literature_query(
                        user_message=user_message,
                        goal_description=goal,
                    ),
                    persist_dir=persist_dir,
                    source_dir=source_dir,
                    top_k=5,
                )

            try:
                lit_payload = await _run_cancellable(_retrieve_literature, label="文献检索")
            except Exception as exc:
                lit_payload = {
                    "text": "",
                    "mode": "empty",
                    "sources": [],
                    "error": str(exc),
                }

            if (
                isinstance(lit_payload, tuple)
                and len(lit_payload) == 2
                and lit_payload[0] == "__cancelled__"
            ):
                yield {"delta": lit_payload[1]}
                yield {"cancelled": True}
                return

            lit_sources: list[Any] = []
            lit_error = None
            if isinstance(lit_payload, dict):
                literature_context = str(lit_payload.get("text") or "")
                literature_mode = str(lit_payload.get("mode") or "empty")
                lit_sources = list(lit_payload.get("sources") or [])
                lit_error = lit_payload.get("error")
            else:
                lit_error = "invalid_literature_payload"

            if literature_context.strip():
                if literature_mode == "vector":
                    yield {
                        "delta": (
                            f"✅ 已注入向量文献检索结果"
                            f"（约 {len(literature_context)} 字符）。\n\n"
                        )
                    }
                elif literature_mode == "corpus":
                    src_preview = "、".join(str(s) for s in lit_sources[:4]) or "repro_recipes"
                    yield {
                        "delta": (
                            f"✅ 已注入文献语料（repro_recipes/figure_index）：{src_preview}"
                            f"（约 {len(literature_context)} 字符）。\n\n"
                        )
                    }
                else:
                    src_preview = "、".join(str(s) for s in lit_sources[:4]) or "softwares_database"
                    prefer_vector = False
                    if isinstance(lit_payload, dict):
                        prefer_vector = bool(lit_payload.get("prefer_vector"))
                    if prefer_vector or (lit_error and "vector" in str(lit_error)):
                        reason = ""
                        if lit_error and ":" in str(lit_error):
                            reason = f"（{str(lit_error).split(':', 1)[-1]}）"
                        yield {
                            "delta": (
                                f"⚠️ 向量检索未成功{reason}，已回退关键词文献检索：{src_preview}"
                                f"（约 {len(literature_context)} 字符）。\n\n"
                            )
                        }
                    else:
                        yield {
                            "delta": (
                                f"✅ 已注入关键词文献检索：{src_preview}"
                                f"（约 {len(literature_context)} 字符）。\n\n"
                            )
                        }
            else:
                detail = f"（{lit_error}）" if lit_error else ""
                yield {
                    "delta": (
                        f"ℹ️ 未检索到可用文献上下文{detail}，将按工具白名单与用户意图规划。\n\n"
                    )
                }

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
                    literature_context=literature_context or None,
                    skill_context=skill_context or None,
                )
                return llm.think_complete(
                    messages_with_system(PLAN_SYSTEM_GUARD, str(prompt)),
                    temperature=temperature,
                    max_tokens=8192,
                )

            yield {"delta": " 正在调用 LLM 生成计划…\n"}
            try:
                plan_resp = await _run_cancellable(_plan, label="计划生成")
            except Exception as exc:
                yield {"error": f"计划生成失败: {exc}"}
                return

            if (
                isinstance(plan_resp, tuple)
                and len(plan_resp) == 2
                and plan_resp[0] == "__cancelled__"
            ):
                yield {"delta": plan_resp[1]}
                yield {"cancelled": True}
                return

            if await _should_stop():
                yield {"delta": "\n\n**已终止**（计划阶段）\n"}
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
                    "delta": (
                        "⚠️ 计划步骤未匹配到已注册工具名，"
                        "将尝试从文本中保留含 Use 的步骤…\n"
                    )
                }
                tasks_filtered = [t for t in tasks if "use " in t.lower()]

            tasks = tasks_filtered
        else:
            tool_names = [t.name for t in tools_info]

        if raw_conversion_needed(paths):
            tasks = ensure_raw_conversion_step(tasks, paths, convert_tool)
            yield {
                "delta": f"ℹ️ 格式转换：{conversion_environment_hint()}\n\n"
            }

        # 新分析计划里若含 mixOmics，会在本轮产出 differential_metabolites.csv；
        # 不可因「当前还没有差异表」而提前裁掉注释/KEGG。
        plan_will_make_diff = any(
            "statistical_analysis_mixomics" in str(t).lower() for t in tasks
        )
        blocked, block_reason = differential_downstream_blocked(paths)
        if blocked and not plan_will_make_diff:
            pruned, removed = prune_differential_dependent_tasks(tasks)
            if removed:
                tasks = pruned
                yield {
                    "delta": (
                        "ℹ️ 当前无可用差异代谢物表，且本轮计划不含统计分析，"
                        "已跳过差异提取/谱库注释/KEGG 富集；"
                        "上传 .mgf 时仍可执行分子网络或 DeepMASS。\n\n"
                    )
                }

        tasks = inject_mgf_standalone_tasks(tasks, user_message, paths, tool_names)
        tasks = inject_visual_standalone_tasks(tasks, user_message, tool_names)
        try:
            from web_frontend.backend.session_metadata import (
                ensure_metadata_from_inputs,
                list_metadata_columns,
                resolve_metadata_csv,
            )

            _, _ = ensure_metadata_from_inputs(paths["upload"], paths=paths)
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
            if used_a == "local":
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
            else:
                yield {
                    "delta": (
                        "⚠️ MassOmics 计划映射后无可执行步骤，"
                        "请检查 MassOmics 工具名与 Web MCP 白名单映射。\n\n"
                    )
                }
            yield {"error": "计划为空或未包含已注册工具，未执行。"}
            return

        history_summary.append({"role": "user", "content": f"Plan: {tasks}"})
        yield {"delta": f"✅ 计划共 **{len(tasks)}** 步（Agent A：`{used_a}`）：\n"}
        for i, t in enumerate(tasks, 1):
            yield {"delta": f"  {i}. {t}\n"}
        yield {"delta": "\n---\n\n"}

        out_path = Path(paths["outputspace"])
        data_understanding = data_list if isinstance(data_list, str) else str(data_list)
        if plan_doc_massomics:
            from web_frontend.backend.agent_a.massomics_planner import (
                save_massomics_plan_files,
                write_web_analysis_plan_from_massomics,
            )

            mo_json, mo_md = save_massomics_plan_files(out_path, plan_doc_massomics)
            plan_payload = write_web_analysis_plan_from_massomics(
                out_path,
                plan_doc=plan_doc_massomics,
                tasks=tasks,
                data_understanding=data_understanding,
                user_message=user_message,
                project_root=Path(project_root),
            )
            n_exec = len(plan_payload.get("executable_tasks") or [])
            md_path = out_path / "analysis_plan.md"
            yield {
                "delta": (
                    f"\n📄 已写入 MassOmics `plan_*.json/.md` 与 Web `analysis_plan.md`"
                    f"（可执行 {n_exec} 步）。\n\n"
                )
            }
            try:
                preview = mo_md.read_text(encoding="utf-8")
                yield {"delta": _plan_preview_for_chat(preview)}
            except OSError:
                try:
                    preview = md_path.read_text(encoding="utf-8")
                    yield {"delta": _plan_preview_for_chat(preview)}
                except OSError:
                    yield {"delta": _PLAN_REVIEW_FOOTER}
        else:
            from web_frontend.backend.agent_a.plan_document import write_analysis_plan

            plan_payload = write_analysis_plan(
                out_path,
                objective=user_message,
                data_understanding=data_understanding,
                tasks=tasks,
                user_message=user_message,
                project_root=Path(project_root),
            )
            n_exec = len(plan_payload.get("executable_tasks") or [])
            md_path = out_path / "analysis_plan.md"
            yield {
                "delta": (
                    f"\n📄 已写入 `analysis_plan.md`（可执行 {n_exec} 步）。\n\n"
                )
            }
            try:
                preview = md_path.read_text(encoding="utf-8")
                yield {"delta": _plan_preview_for_chat(preview)}
            except OSError:
                yield {"delta": _PLAN_REVIEW_FOOTER}
        if mode_norm == "plan":
            yield {"plan_ready": True, "n_steps": n_exec}
            return

    from web_frontend.backend.agent_backends import agent_b_backend

    b_exec = agent_b_backend()
    if b_exec == "massomics":
        from web_frontend.backend.agent_b.massomics_executor import (
            stream_massomics_b_execution,
        )

        async for event in stream_massomics_b_execution(
            paths=paths,
            session_id=session_id,
            project_root=Path(project_root),
            goal_text=user_message,
            cancel_event=cancel_event,
            should_stop=_should_stop,
        ):
            yield event
        return

    yield {
        "delta": (
            "⚙️ **Agent B**：本地 Web MCP（`src/mcp_server` + mixOmics/XCMS 专用 runner）\n\n"
        )
    }

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
    had_tool_failure = False
    open_mcp = _needs_mcp_session(tasks)

    async def _run_task_loop(session: Optional[ClientSession]):
        nonlocal visual_results, had_tool_failure
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
                    literature_context=literature_context or None,
                    skill_context=skill_context or None,
                )
                return llm.think(
                    messages_with_system(TOOL_MATCH_SYSTEM_GUARD, str(prompt)),
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
                        literature_context=literature_context or None,
                        skill_context=skill_context or None,
                    )
                    try:
                        raw2 = await loop.run_in_executor(
                            None,
                            lambda: llm.think(
                                messages_with_system(
                                    TOOL_MATCH_SYSTEM_GUARD, str(retry_prompt)
                                ),
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
                if tool_name == "plot_edit":
                    # 改图：优先用户自然语言；勿用换行拼接计划英文（会被拆成两次改同一张图）
                    tool_args["instruction"] = (
                        (user_message or "").strip()
                        or existing_instruction
                        or str(task).strip()
                    )
                else:
                    tool_args["instruction"] = "\n".join(
                        part
                        for part in (user_message, task, existing_instruction)
                        if part and str(part).strip()
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
                        kind = payload.get("kind") or tool_name
                        visual_results.append({"kind": kind, "file": fpath})
                        # 仅改图/拼图推送到聊天栏；分析工具出图不推 chat_image
                        yield {
                            "chat_image": {
                                "file": fpath,
                                "kind": kind,
                            }
                        }
                    yield {"delta": f"**{tool_name}** 完成：\n{result_str}\n\n"}
                except Exception as exc:
                    had_tool_failure = True
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
                    from web_frontend.backend.analysis_intent import (
                        build_analysis_intent,
                        describe_intent,
                        intent_to_mixomics_kwargs,
                        validate_mixomics_kwargs,
                    )

                    try:
                        from web_frontend.backend.session_metadata import (
                            list_metadata_columns,
                            resolve_metadata_csv,
                        )

                        _meta = resolve_metadata_csv(paths["upload"])
                        _cols = [str(c["name"]) for c in list_metadata_columns(_meta)]
                    except Exception:
                        _meta = None
                        _cols = []
                    intent_for_stats = build_analysis_intent(
                        user_message,
                        metadata_columns=_cols,
                        metadata_csv=str(_meta) if _meta else None,
                    )
                    for key, value in intent_to_mixomics_kwargs(intent_for_stats).items():
                        if not tool_args.get(key):
                            tool_args[key] = value
                    for warn in intent_for_stats.get("warnings") or []:
                        yield {"delta": f"{warn}\n"}
                    for err in intent_for_stats.get("errors") or []:
                        yield {"delta": f"分析意图校验：{err}\n"}

                    # 读实际 Group 水平做跑前硬校验
                    _levels: list[str] = []
                    try:
                        import pandas as pd

                        if _meta:
                            _mdf = pd.read_csv(_meta)
                            _gc = str(tool_args.get("group_column") or "Group")
                            _cmap = {str(c).lower(): c for c in _mdf.columns}
                            _real = _cmap.get(_gc.lower())
                            if _real is not None:
                                _levels = [
                                    str(v).strip()
                                    for v in _mdf[_real].dropna().unique().tolist()
                                    if str(v).strip()
                                ]
                    except Exception:
                        _levels = []

                    preflight_errs = validate_mixomics_kwargs(
                        {
                            "group_column": tool_args.get("group_column") or "Group",
                            "contrast_group1": tool_args.get("contrast_group1"),
                            "contrast_group2": tool_args.get("contrast_group2"),
                        },
                        metadata_columns=_cols,
                        group_levels=_levels,
                    )
                    # 无效 group_column / contrast 时去掉，避免 R 硬崩；并明确告知
                    if any("group_column" in e for e in preflight_errs):
                        tool_args.pop("group_column", None)
                    if any("火山对比" in e or "只有 1 个水平" in e for e in preflight_errs):
                        tool_args.pop("contrast_group1", None)
                        tool_args.pop("contrast_group2", None)
                    for err in preflight_errs:
                        yield {"delta": f" {err}\n"}
                    if preflight_errs and any("只有 1 个水平" in e for e in preflight_errs):
                        yield {
                            "delta": (
                                "当前 metadata 无法支撑计划中的 PLS/火山对比；"
                                "仍将运行 mixOmics（通常仅 PCA）。"
                                "请修正 metadata 的 Group（至少 2 个水平）后重试对比请求。\n"
                            )
                        }

                    if intent_for_stats and (
                        tool_args.get("group_column")
                        or (
                            tool_args.get("contrast_group1")
                            and tool_args.get("contrast_group2")
                        )
                    ):
                        label = describe_intent(intent_for_stats) or "统计参数"
                        yield {
                            "delta": (
                                f"已将分析意图注入 mixOmics（{label}）："
                                f"group_column={tool_args.get('group_column') or 'Group'}"
                                + (
                                    f", contrast={tool_args.get('contrast_group1')} vs "
                                    f"{tool_args.get('contrast_group2')}"
                                    if tool_args.get("contrast_group1")
                                    and tool_args.get("contrast_group2")
                                    else ""
                                )
                                + "\n"
                            )
                        }

                    def _run_mixomics():
                        kw: dict[str, Any] = {
                            "ncomp_pca": int(tool_args.get("ncomp_pca", 5)),
                            "ncomp_plsda": int(tool_args.get("ncomp_plsda", 2)),
                            "scale_method": str(
                                tool_args.get("scale_method", "autoscale")
                            ),
                            "top_n_heatmap": int(
                                tool_args.get("top_n_heatmap", 50)
                            ),
                            "seed": int(tool_args.get("seed", 123)),
                        }
                        for opt in (
                            "vip_threshold",
                            "pvalue_threshold",
                            "padj_threshold",
                            "log2fc_threshold",
                            "use_fdr",
                            "group_column",
                            "contrast_group1",
                            "contrast_group2",
                        ):
                            if tool_args.get(opt) is not None and str(
                                tool_args.get(opt)
                            ).strip() != "":
                                kw[opt] = tool_args[opt]
                        return run_statistical_analysis_mixomics(
                            tool_args.get("input_dir", paths["filtered"]),
                            tool_args.get("metadata_csv", paths["upload"]),
                            tool_args.get("output_dir", paths["statistical"]),
                            session_id=session_id,
                            cancel_flag=get_thread_cancel_flag(session_id),
                            **kw,
                        )

                    yield {
                        "delta": "使用**日志重定向**运行 mixOmics（避免 MCP 管道死锁）…\n"
                    }
                    mix_out = await _run_cancellable(_run_mixomics, label="mixOmics")
                    if (
                        isinstance(mix_out, tuple)
                        and len(mix_out) == 2
                        and mix_out[0] == "__cancelled__"
                    ):
                        yield {"delta": mix_out[1]}
                        yield {"cancelled": True}
                        return
                    log_path = mix_out
                    if await _should_stop():
                        yield {"delta": "\n\n**已终止**\n"}
                        yield {"cancelled": True}
                        return
                    # 如实汇报产物（避免「计划写了火山但实际只有 PCA」看起来像假对话）
                    try:
                        from pathlib import Path as _P

                        _out = _P(
                            str(
                                tool_args.get("output_dir")
                                or paths.get("statistical")
                                or ""
                            )
                        )
                        _root = _P(str(paths.get("outputspace") or ""))
                        _warn = _out / "analysis_warning.txt"
                        _params = _out / "analysis_params.txt"
                        _volcano = _out / "volcano_plot.png"
                        _pls = _out / "plsda_plot.png"
                        _pca = _out / "pca_plot.png"
                        if _params.is_file():
                            yield {
                                "delta": " 统计参数：\n"
                                + _params.read_text(encoding="utf-8", errors="replace")
                                + "\n"
                            }
                        if _warn.is_file():
                            yield {
                                "delta": "统计警告：\n"
                                + _warn.read_text(encoding="utf-8", errors="replace")
                                + "\n"
                            }
                        bits = []
                        bits.append("PCA✅" if _pca.is_file() else "PCA❌")
                        bits.append("PLS-DA✅" if _pls.is_file() else "PLS-DA❌")
                        bits.append("火山✅" if _volcano.is_file() else "火山❌")
                        yield {"delta": " 本次实际产出：" + " / ".join(bits) + "\n"}
                        # 记入 visual_results；聊天栏由 webapp 合并后预览（默认 3 张，… 展开）
                        # 注意：产物路径统一用 _out（output_dir），勿用未定义的 _stat_dir
                        _heatmap = _out / "heatmap_top_vip.png"
                        _vip = _out / "vip_scores.png"
                        _wanted_stems = {
                            str(s).strip()
                            for s in (
                                (intent_for_stats or {}).get("targets")
                                or (intent_for_stats or {}).get("target_stems")
                                or []
                            )
                            if str(s).strip()
                        }
                        _only_figs = bool((intent_for_stats or {}).get("only_figures"))
                        for _png, _kind in (
                            (_volcano, "volcano"),
                            (_pls, "plsda"),
                            (_pca, "pca"),
                            (_heatmap, "heatmap"),
                            (_vip, "vip"),
                        ):
                            if not _png.is_file():
                                continue
                            _stem = _png.stem  # e.g. volcano_plot / pca_plot
                            if _only_figs and _wanted_stems and _stem not in _wanted_stems:
                                continue
                            try:
                                _rel = _png.resolve().relative_to(_root.resolve()).as_posix()
                            except Exception:
                                _rel = _png.name
                            visual_results.append({"kind": _kind, "file": _rel})
                        wanted_volcano = bool(
                            tool_args.get("contrast_group1")
                            and tool_args.get("contrast_group2")
                        ) or ("火山" in str(user_message) or "volcano" in str(user_message).lower())
                        if wanted_volcano and not _volcano.is_file():
                            yield {
                                "delta": (
                                    " 本次未生成火山图。常见原因：metadata 只有 1 个 Group，"
                                    "或对比组名与 Group 列不一致。请检查 "
                                    "`statistical_results/analysis_warning.txt` 与 metadata。\n"
                                )
                            }
                    except Exception:
                        pass
                    pruned_tasks, prune_reason = _prune_remaining_differential_tasks(
                        tasks, paths
                    )
                    if prune_reason and len(pruned_tasks) < len(tasks):
                        tasks[:] = pruned_tasks
                        yield {
                            "delta": (
                                f"统计未产生差异代谢物：{prune_reason}\n"
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
                                                "格式转换未成功，已跳过后续 XCMS 及下游步骤。"
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
                    had_tool_failure = True
                    fail_title = f"**{tool_name}** 失败"
                    if conversion_failed:
                        fail_title = "**格式转换** 全部候选工具均失败"
                    yield {
                        "delta": (
                            f"{fail_title}：\n{result_str}\n\n"
                            "ℹ后续步骤可能因缺少输入文件而无法继续，请修复后重试。\n\n"
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
                    yield {"delta": f"**{tool_name}** 完成：\n{result_str}\n\n"}
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
                                    goal_text=user_message,
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
                                        goal_text=user_message,
                                    ),
                                )
                                written = list(written) + list(written2)
                            if written:
                                yield {
                                    "delta": (
                                        f"已为 {len(written)} 张结果图生成/更新语义编辑 sidecar。\n"
                                    )
                                }
                            # 网络/KEGG 等：扫输出目录 PNG，保证任意分析都能进聊天预览
                            if tool_name != "statistical_analysis_mixomics":
                                out_for_pngs = tool_args.get("output_dir") or paths.get(
                                    "outputspace"
                                )
                                _append_output_png_visuals(
                                    visual_results,
                                    out_for_pngs,
                                    Path(paths["outputspace"]),
                                    kind=tool_name,
                                )
                        except Exception as sidecar_exc:
                            yield {
                                "delta": f"语义 sidecar 生成跳过：{sidecar_exc}\n"
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
                                        f"检测到分析意图（{label}），"
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
                                                f"意图重绘失败（{item.get('stem')}）："
                                                f"{item['error']}\n"
                                            )
                                        }
                                        continue
                                    fname = (item.get("file") or {}).get("name")
                                    if not fname:
                                        continue
                                    visual_results.append(
                                        {"kind": "plot_edit", "file": fname}
                                    )
                                    yield {
                                        "delta": (
                                            f"已按意图重绘：`{fname}`"
                                            f"（{item.get('analysis_intent') or label}）\n"
                                        )
                                    }
                                # 意图重绘图写入 visual_results；聊天预览由 webapp 合并推送
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
                                "delta": f"分析意图重绘跳过：{coloring_exc}\n"
                            }
            except Exception as exc:
                had_tool_failure = True
                err_msg = (
                    f"工具 {tool_name} 失败: {exc}\n{traceback.format_exc()}"
                )
                history_summary.append({"role": "tool", "content": err_msg})
                yield {"delta": f"{err_msg}\n\n"}
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
            yield {"delta": "本计划仅含本地工具（改图/拼图），跳过 MCP 子进程。\n\n"}
            async for event in _run_task_loop(None):
                yield event
                if event.get("cancelled"):
                    return

        if had_tool_failure:
            done_payload: dict[str, Any] = {
                "delta": (
                    "\n\n---\n⚠️ **计划已跑完，但有步骤失败。**\n"
                    f"请查看上方错误与 outputspace/{storage_slug or session_id}/ 下的日志"
                    "（如 statistical_analysis_mixomics.log / analysis_warning.txt）。\n"
                )
            }
        else:
            done_payload = {
                "delta": "\n\n---\n🎉 **所有计划任务已执行完毕。**\n"
                f"结果已写入 **outputspace/{storage_slug or session_id}/**。\n"
            }
        if visual_results:
            done_payload["visual_results"] = visual_results
            files_line = "、".join(v["file"] for v in visual_results)
            done_payload["delta"] += f"视觉产物：{files_line}\n"
        done_payload["execute_done"] = True
        done_payload["had_tool_failure"] = had_tool_failure
        yield done_payload
        if visual_results:
            yield {"visual_results": visual_results, "finished": True}

    except Exception as exc:
        yield {"delta": f"\nAgent 执行中断: {exc}\n{traceback.format_exc()}\n"}
        yield {"error": str(exc)}
