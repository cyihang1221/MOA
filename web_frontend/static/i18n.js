/**
 * MassAgent UI i18n (zh-CN / en)
 */
(function () {
  const STORAGE_KEY = "massagent-lang";
  const DEFAULT_LANG = "zh-CN";

  const STRINGS = {
    "zh-CN": {
      "meta.title": "MassAgent · 质谱 Agent",
      "meta.description": "MassAgent - 质谱数据分析智能 Agent",
      "shared.banner": "只读分享视图 · 他人可查看此会话，无法发送消息",
      "shared.exit": "返回我的会话",
      "brand.sub": "质谱数据分析 Agent",
      "btn.newSession": "+ 新会话",
      "runtime.title": "运行环境",
      "runtime.detecting": "正在检测…",
      "runtime.unavailable": "运行环境信息不可用",
      "runtime.detectFailed": "运行环境检测失败（不影响聊天）",
      "runtime.platform": "系统",
      "runtime.rawConv": "RAW 转换",
      "runtime.r": "R",
      "runtime.docker": "Docker",
      "runtime.unknown": "未知",
      "runtime.available": "可用",
      "runtime.notDetected": "未检测到",
      "workflow.title": "使用方式",
      "workflow.step1": "在发送按钮左侧上传一个或多个文件",
      "workflow.step2": "用自然语言描述分析目标",
      "workflow.step3": "Agent 自动选择合适工具执行",
      "tools.title": "可用工具",
      "toolbar.model": "模型",
      "toolbar.temp": "Temperature",
      "toolbar.lang": "Language",
      "toolbar.clearSession": "清空会话",
      "toolbar.share": "复制分享链接",
      "toolbar.shareCopied": "已复制",
      "welcome.title": "MassAgent 能做什么？",
      "welcome.desc":
        "上传 raw / mzML / mgf / rds 等质谱相关文件，用对话驱动完整分析流程。Agent 会根据你的描述，从下方工具库中自动选择合适步骤。",
      "files.title": "会话文件",
      "files.refresh": "刷新",
      "files.hint": "切换会话后显示输入/输出文件",
      "files.input": "输入（上传）",
      "files.output": "输出（Agent）",
      "files.empty": "暂无文件",
      "files.noInput": "尚无上传文件",
      "files.noOutput": "尚无 Agent 输出",
      "files.download": "下载",
      "files.slug": "目录标识：{slug}",
      "files.current": "当前会话文件",
      "files.loadFail": "文件列表加载失败：{msg}",
      "files.refreshing": "正在刷新…",
      "composer.placeholder":
        "描述分析需求；仅在上传新文件或明确要求分析时才会运行 Agent 工具（Enter 发送）",
      "attach.title": "添加附件",
      "stop.title": "终止生成",
      "btn.stop": "终止",
      "btn.send": "发送",
      "role.user": "你",
      "role.assistant": "MassAgent",
      "msg.edit": "编辑",
      "msg.cancel": "取消",
      "msg.saveResend": "保存并重发",
      "attach.remove": "移除",
      "session.shared": "分享会话（只读）",
      "session.unnamed": "未命名会话",
      "session.sharedBadge": "已分享",
      "session.rename": "重命名",
      "session.delete": "删除",
      "session.renamePrompt": "输入新的会话名称",
      "session.newTitle": "新会话",
      "session.deleteConfirm": "确定删除会话：{title} ？",
      "session.clearConfirm": "确定清空当前会话？",
      "tools.noDesc": "暂无描述",
      "tools.loadFail": "工具列表加载失败",
      "tools.cat.convert": "数据转换",
      "tools.cat.xcms": "XCMS 数据分析",
      "tools.cat.peaks": "峰检测",
      "tools.cat.processing": "峰处理与注释",
      "tools.cat.library": "谱库匹配",
      "tools.cat.networking": "分子网络",
      "tools.cat.deeplearn": "深度学习注释",
      "tools.cat.workflow": "流程编排",
      "tools.cat.other": "其他工具",
      "tools.desc.convert_raw_to_mzml_msconvert": "将 Thermo .raw 批量转换为 mzML（Windows 使用 Docker msconvert）",
      "tools.desc.convert_raw_to_mzml_ThermoRawFileParser": "将 Thermo .raw 批量转换为 mzML（Linux 推荐 ThermoRawFileParser）",
      "tools.desc.data_preprocessing_xcms": "XCMS 峰检测、对齐、分组、Gap filling 与 MS2 提取",
      "tools.desc.feature_filtering_and_missing_value_imputation_knn": "特征过滤与 KNN 缺失值填补",
      "tools.desc.statistical_analysis_mixomics": "mixOmics 多元/单变量统计与差异代谢物",
      "tools.desc.extract_differential_features": "提取差异代谢物特征及对应 MS/MS 谱图",
      "tools.desc.spectral_annotation": "GNPS 谱库注释（正/负离子库）",
      "tools.desc.kegg_compound_enrichment": "KEGG 化合物通路富集分析（ORA）",
      "tools.desc.molecular_networking_gnps": "GNPS 经典分子网络（余弦相似度、分子家族）",
      "tools.desc.deepmass_annotation": "DeepMASS2 Spec2Vec 深度学习代谢物注释（Docker）",
      "models.loadFail": "模型加载失败",
      "status.cancelled":
        "已终止（后续步骤已跳过；若终端仍在输出，属当前工具收尾）",
      "status.error": "完成（有错误）：{msg}",
      "status.done": "分析已完成，结果已保存到会话目录",
      "status.complete": "完成",
      "status.waitEdit": "请等待当前回复结束后再编辑",
      "status.failed": "失败：{msg}",
      "status.cancelledBg": "已终止（后台将不再执行后续步骤）",
      "status.streaming": "正在生成中，请先点「终止」或等待完成",
      "status.uploading": "正在上传附件...",
      "status.uploadingProgress": "正在上传 ({current}/{total})：{name}",
      "status.sending": "正在发送...",
      "status.sendFailed": "发送失败：{msg}",
      "status.stopRequested": "已请求终止（当前正在跑的工具可能仍在终端输出片刻）",
      "status.creatingSession": "正在创建新会话…",
      "status.createSessionFailed": "创建会话失败：{msg}",
      "status.pageLoadFailed": "页面加载失败：{msg}",
      "status.agentMode":
        "Agent 模式（{platform}）：正在规划并调用 MCP 工具…",
      "status.replying": "正在回复...",
      "status.crossPlatform": "跨平台",
      "upload.defaultPrompt":
        "请根据已上传的文件选择合适的工具进行分析，并给出清晰的结果摘要。",
      "upload.path": "路径",
      "upload.suffix":
        "请根据文件类型与我的需求，从可用工具中选择合适流程处理。",
      "upload.marker": "[已上传附件]",
      "image.download": "下载",
      "image.preview": "查看大图",
      "image.edit": "编辑",
      "image.editorTitle": "编辑图片：{name}",
      "image.addTitle": "添加标题",
      "image.addText": "添加文字",
      "image.addArrow": "添加箭头",
      "image.addColorBlock": "添加色块",
      "image.titlePosition": "标题位置",
      "image.titleTopCenter": "上方居中",
      "image.titleTopLeft": "上方居左",
      "image.titleTopRight": "上方居右",
      "image.titleInside": "图内自定义",
      "image.text": "文字",
      "image.textPlaceholder": "选择文字后编辑",
      "image.color": "颜色",
      "image.fontSize": "字号",
      "image.titleFontSize": "标题字号",
      "image.axisFontSize": "坐标轴字号",
      "image.plotlyFontApplied": "已更新标题/坐标轴字号",
      "image.deleteSelected": "删除选中",
      "image.save": "保存为新图",
      "image.newText": "双击/选中后编辑文字",
      "image.loading": "正在加载图片...",
      "image.ready": "可拖动标题、文字、箭头和色块；使用「吸管取色」+「全图替换」修改底图颜色。",
      "image.rasterTools": "底图换色",
      "image.eyedropper": "吸管取色",
      "image.eyedropperActive": "吸管已开启：在底图上点击取色",
      "image.eyedropperOff": "吸管取色",
      "image.sourceColor": "源颜色",
      "image.targetColor": "替换为",
      "image.tolerance": "容差",
      "image.replaceAllColors": "全图替换",
      "image.undo": "撤回",
      "image.undoEmpty": "没有可撤回的操作",
      "image.undoDone": "已撤回上一步",
      "image.rasterColorPicked": "已选取源颜色 {color}，设置替换色后点击「全图替换」。",
      "image.rasterColorApplied": "已替换底图中 {count} 个相近颜色像素。",
      "image.rasterPickFirst": "请先用吸管选取源颜色",
      "image.mergeOpen": "合并图片",
      "image.mergeTitle": "合并图片",
      "image.mergeHint": "勾选至少 2 张图片，预览后保存为论文拼图。",
      "image.mergeHintPs": "点击缩略图选图；改列数、标签、字号会即时生效。拖动：Shift 锁定方向，Ctrl 吸附；Alt+滚轮或右上角按钮缩放预览。",
      "image.mergeSnapHint": "Shift 锁定轴向 · Ctrl 吸附对齐 · Alt+滚轮 缩放预览",
      "image.mergeZoomFit": "适应窗口",
      "image.mergeZoomApplied": "预览缩放：{pct}%（不影响导出）",
      "image.mergeCanvasSize": "画布 {w}×{h} px",
      "image.mergeSelectHint": "请在左侧点击缩略图选择要合并的图片",
      "image.mergeNoImages": "当前会话暂无可合并的图片",
      "image.mergeCols": "列数",
      "image.mergeColsAuto": "自动",
      "image.mergeGap": "间距 (px)",
      "image.mergeColsApplied": "已按新列数重新排版",
      "image.mergeLabelsApplied": "已更新子图标签",
      "image.mergeLabelSizeApplied": "已更新标签字号",
      "image.mergeCustomLabelApplied": "已更新自定义标签",
      "image.mergeTextAdded": "已添加文字，可拖动调整位置",
      "image.mergeTextApplied": "已更新文字内容",
      "image.mergeTextSizeApplied": "已更新文字字号",
      "image.mergeImageToggled": "已更新所选图片",
      "image.mergeDeleted": "已删除选中元素",
      "image.mergeBg": "画布背景",
      "image.mergeLabels": "子图标签",
      "image.mergeLabelUpper": "A, B, C…",
      "image.mergeLabelLower": "a, b, c…",
      "image.mergeLabelNum": "1, 2, 3…",
      "image.mergeLabelCustom": "自定义",
      "image.mergeCustomLabel": "自定义标签",
      "image.mergeLabelFontSize": "标签字号",
      "image.mergeLabelNone": "无",
      "image.mergeAutoLayout": "自动排版",
      "image.mergeAddText": "添加文字",
      "image.mergeTextPlaceholder": "选中文字后编辑",
      "image.mergeRefresh": "刷新预览",
      "image.mergeSave": "保存拼图",
      "image.mergeNeedTwo": "请至少选择 2 张图片",
      "image.mergeNeedOne": "请至少选择 1 张图片",
      "image.mergePreviewReady": "预览已更新",
      "image.mergeLayoutReady": "排版完成，可拖动调整",
      "image.mergeSaving": "正在保存拼图…",
      "image.plotlyEditorTitle": "编辑图表：{name}",
      "image.plotlyHint": "在下拉框中选择图例系列，再用颜色块修改该系列颜色；可拖动标题和图例位置。",
      "image.plotlyReady": "请选择图例系列，然后点击颜色块。",
      "image.plotlyLegendColor": "图例系列",
      "image.plotlySelectTrace": "请选择图例系列…",
      "image.plotlyNoLegend": "此图无可编辑图例",
      "image.plotlyPickLegend": "正在修改：{name}",
      "image.plotlyColorApplied": "已应用颜色到：{name}",
      "image.saving": "正在保存编辑后的图片...",
      "image.saved": "已保存编辑图：{name}",
      "image.saveFail": "保存图片失败",
      "image.saveFailWithMsg": "保存图片失败：{msg}",
      "image.loadFail": "图片加载失败",
      "image.editorUnavailable": "图片编辑器加载失败，请检查 Konva 脚本是否可访问",
      "err.fetchSessions": "获取会话列表失败",
      "err.createSession": "创建会话失败",
      "err.deleteSession": "删除失败",
      "err.renameSession": "重命名失败",
      "err.enableShare": "开启分享失败",
      "err.upload": "文件上传失败",
      "err.uploadEmpty": "未选择有效文件（空文件已忽略）",
      "err.loadMessages": "加载消息失败",
      "err.sharedNotFound": "分享会话不存在或未开启分享",
      "err.clearSession": "清空失败",
      "err.network":
        "网络连接失败（请确认服务已启动；上传附件后 Agent 可能需数分钟，勿关闭页面）",
      "err.requestFailed": "请求失败 ({status})",
      "err.streamInterrupted":
        "连接中断（Agent 执行时间较长或服务器异常），请查看终端日志后重试",
    },
    en: {
      "meta.title": "MassAgent · Mass Spec Agent",
      "meta.description": "MassAgent - Intelligent mass spectrometry data analysis agent",
      "shared.banner": "Read-only share · Others can view this session but cannot send messages",
      "shared.exit": "Back to my sessions",
      "brand.sub": "Mass spectrometry data analysis agent",
      "btn.newSession": "+ New chat",
      "runtime.title": "Runtime",
      "runtime.detecting": "Detecting…",
      "runtime.unavailable": "Runtime info unavailable",
      "runtime.detectFailed": "Runtime detection failed (chat still works)",
      "runtime.platform": "OS",
      "runtime.rawConv": "RAW converter",
      "runtime.r": "R",
      "runtime.docker": "Docker",
      "runtime.unknown": "Unknown",
      "runtime.available": "Available",
      "runtime.notDetected": "Not detected",
      "workflow.title": "How to use",
      "workflow.step1": "Upload one or more files next to the send button",
      "workflow.step2": "Describe your analysis goal in natural language",
      "workflow.step3": "Agent picks and runs the right tools automatically",
      "tools.title": "Available tools",
      "toolbar.model": "Model",
      "toolbar.temp": "Temperature",
      "toolbar.lang": "Language",
      "toolbar.clearSession": "Clear session",
      "toolbar.share": "Copy share link",
      "toolbar.shareCopied": "Copied",
      "welcome.title": "What can MassAgent do?",
      "welcome.desc":
        "Upload raw / mzML / mgf / rds and drive the full workflow via chat. The agent selects appropriate steps from the tool library below.",
      "files.title": "Session files",
      "files.refresh": "Refresh",
      "files.hint": "Select a session to see input/output files",
      "files.input": "Input (uploads)",
      "files.output": "Output (Agent)",
      "files.empty": "No files",
      "files.noInput": "No uploads yet",
      "files.noOutput": "No agent output yet",
      "files.download": "Download",
      "files.slug": "Storage slug: {slug}",
      "files.current": "Current session files",
      "files.loadFail": "Failed to load files: {msg}",
      "files.refreshing": "Refreshing…",
      "composer.placeholder":
        "Describe your analysis; Agent tools run only on new uploads or explicit analysis requests (Enter to send)",
      "attach.title": "Add attachment",
      "stop.title": "Stop generation",
      "btn.stop": "Stop",
      "btn.send": "Send",
      "role.user": "You",
      "role.assistant": "MassAgent",
      "msg.edit": "Edit",
      "msg.cancel": "Cancel",
      "msg.saveResend": "Save & resend",
      "attach.remove": "Remove",
      "session.shared": "Shared session (read-only)",
      "session.unnamed": "Untitled session",
      "session.sharedBadge": "Shared",
      "session.rename": "Rename",
      "session.delete": "Delete",
      "session.renamePrompt": "Enter a new session name",
      "session.newTitle": "New session",
      "session.deleteConfirm": "Delete session “{title}”?",
      "session.clearConfirm": "Clear all messages in this session?",
      "tools.noDesc": "No description",
      "tools.loadFail": "Failed to load tools",
      "tools.cat.convert": "Format conversion",
      "tools.cat.xcms": "XCMS analysis",
      "tools.cat.peaks": "Peak detection",
      "tools.cat.processing": "Peak processing",
      "tools.cat.library": "Library matching",
      "tools.cat.networking": "Molecular networking",
      "tools.cat.deeplearn": "Deep learning annotation",
      "tools.cat.workflow": "Workflow",
      "tools.cat.other": "Other tools",
      "tools.desc.convert_raw_to_mzml_msconvert": "Batch convert Thermo .raw to mzML (Docker msconvert on Windows)",
      "tools.desc.convert_raw_to_mzml_ThermoRawFileParser": "Batch convert Thermo .raw to mzML (ThermoRawFileParser on Linux)",
      "tools.desc.data_preprocessing_xcms": "XCMS peak picking, alignment, grouping, gap filling, MS2 extraction",
      "tools.desc.feature_filtering_and_missing_value_imputation_knn": "Feature filtering and KNN imputation",
      "tools.desc.statistical_analysis_mixomics": "mixOmics multivariate/univariate stats and differential features",
      "tools.desc.extract_differential_features": "Extract differential features and MS/MS spectra",
      "tools.desc.spectral_annotation": "GNPS spectral library annotation (pos/neg)",
      "tools.desc.kegg_compound_enrichment": "KEGG pathway enrichment (ORA)",
      "tools.desc.molecular_networking_gnps": "GNPS classical molecular networking (cosine similarity, molecular families)",
      "tools.desc.deepmass_annotation": "DeepMASS2 Spec2Vec deep learning annotation (Docker)",
      "models.loadFail": "Failed to load models",
      "status.cancelled":
        "Stopped (remaining steps skipped; tool may still finish in terminal)",
      "status.error": "Finished with error: {msg}",
      "status.done": "Analysis complete; results saved to session folder",
      "status.complete": "Done",
      "status.waitEdit": "Wait for the current reply before editing",
      "status.failed": "Failed: {msg}",
      "status.cancelledBg": "Stopped (no further steps will run)",
      "status.streaming": "Generating… click Stop or wait for completion",
      "status.uploading": "Uploading attachments…",
      "status.uploadingProgress": "Uploading ({current}/{total}): {name}",
      "status.sending": "Sending…",
      "status.sendFailed": "Send failed: {msg}",
      "status.stopRequested": "Stop requested (current tool may log briefly)",
      "status.creatingSession": "Creating new session…",
      "status.createSessionFailed": "Failed to create session: {msg}",
      "status.pageLoadFailed": "Page load failed: {msg}",
      "status.agentMode": "Agent ({platform}): planning and calling MCP tools…",
      "status.replying": "Replying…",
      "status.crossPlatform": "cross-platform",
      "upload.defaultPrompt":
        "Analyze the uploaded files with suitable tools and summarize results.",
      "upload.path": "Path",
      "upload.suffix":
        "Pick an appropriate workflow from available tools based on file types and my request.",
      "upload.marker": "[Attachments uploaded]",
      "image.download": "Download",
      "image.preview": "View full size",
      "image.edit": "Edit",
      "image.editorTitle": "Edit image: {name}",
      "image.addTitle": "Add title",
      "image.addText": "Add text",
      "image.addArrow": "Add arrow",
      "image.addColorBlock": "Add color block",
      "image.titlePosition": "Title position",
      "image.titleTopCenter": "Top center",
      "image.titleTopLeft": "Top left",
      "image.titleTopRight": "Top right",
      "image.titleInside": "Inside plot",
      "image.text": "Text",
      "image.textPlaceholder": "Select text to edit",
      "image.color": "Color",
      "image.fontSize": "Font size",
      "image.titleFontSize": "Title font size",
      "image.axisFontSize": "Axis label font size",
      "image.plotlyFontApplied": "Updated title/axis font sizes",
      "image.deleteSelected": "Delete selected",
      "image.save": "Save as new image",
      "image.newText": "Select and edit this text",
      "image.loading": "Loading image...",
      "image.ready": "Drag titles, text, arrows, and swatches; use Eyedropper + Replace all for raster colors.",
      "image.rasterTools": "Raster recolor",
      "image.eyedropper": "Eyedropper",
      "image.eyedropperActive": "Eyedropper on: click the image to pick a color",
      "image.eyedropperOff": "Eyedropper",
      "image.sourceColor": "Source color",
      "image.targetColor": "Replace with",
      "image.tolerance": "Tolerance",
      "image.replaceAllColors": "Replace all",
      "image.undo": "Undo",
      "image.undoEmpty": "Nothing to undo",
      "image.undoDone": "Undid last step",
      "image.rasterColorPicked": "Source color {color} picked. Set the replacement color, then click Replace all.",
      "image.rasterColorApplied": "Replaced {count} matching image pixels.",
      "image.rasterPickFirst": "Pick a source color with the eyedropper first",
      "image.mergeOpen": "Merge images",
      "image.mergeTitle": "Merge images",
      "image.mergeHint": "Select at least 2 images, preview, then save as a composite figure.",
      "image.mergeHintPs": "Click thumbnails to select. Drag: Shift locks axis, Ctrl snaps. Alt+wheel or toolbar zooms preview only.",
      "image.mergeSnapHint": "Shift: lock axis · Ctrl: snap · Alt+wheel: zoom preview",
      "image.mergeZoomFit": "Fit to window",
      "image.mergeZoomApplied": "Preview zoom: {pct}% (export unchanged)",
      "image.mergeCanvasSize": "Canvas {w}×{h} px",
      "image.mergeSelectHint": "Click thumbnails on the left to choose images to merge",
      "image.mergeNoImages": "No images available to merge in this session",
      "image.mergeCols": "Columns",
      "image.mergeColsAuto": "Auto",
      "image.mergeGap": "Gap (px)",
      "image.mergeColsApplied": "Relayout applied for new column count",
      "image.mergeLabelsApplied": "Panel labels updated",
      "image.mergeLabelSizeApplied": "Label font size updated",
      "image.mergeCustomLabelApplied": "Custom label updated",
      "image.mergeTextAdded": "Text added — drag to reposition",
      "image.mergeTextApplied": "Text content updated",
      "image.mergeTextSizeApplied": "Text font size updated",
      "image.mergeImageToggled": "Selected images updated",
      "image.mergeDeleted": "Selected element deleted",
      "image.mergeBg": "Canvas background",
      "image.mergeLabels": "Panel labels",
      "image.mergeLabelUpper": "A, B, C…",
      "image.mergeLabelLower": "a, b, c…",
      "image.mergeLabelNum": "1, 2, 3…",
      "image.mergeLabelCustom": "Custom",
      "image.mergeCustomLabel": "Custom label",
      "image.mergeLabelFontSize": "Label font size",
      "image.mergeLabelNone": "None",
      "image.mergeAutoLayout": "Auto layout",
      "image.mergeAddText": "Add text",
      "image.mergeTextPlaceholder": "Select text to edit",
      "image.mergeRefresh": "Refresh preview",
      "image.mergeSave": "Save composite",
      "image.mergeNeedTwo": "Select at least 2 images",
      "image.mergeNeedOne": "Select at least 1 image",
      "image.mergePreviewReady": "Preview updated",
      "image.mergeLayoutReady": "Layout ready — drag to adjust",
      "image.mergeSaving": "Saving composite…",
      "image.plotlyEditorTitle": "Edit chart: {name}",
      "image.plotlyHint": "Choose a legend series from the dropdown, then use the color swatch. Drag title and legend to reposition.",
      "image.plotlyReady": "Select a legend series, then click the color swatch.",
      "image.plotlyLegendColor": "Legend series",
      "image.plotlySelectTrace": "Select a legend series…",
      "image.plotlyNoLegend": "No editable legend on this chart",
      "image.plotlyPickLegend": "Editing: {name}",
      "image.plotlyColorApplied": "Applied color to: {name}",
      "image.saving": "Saving edited image...",
      "image.saved": "Saved edited image: {name}",
      "image.saveFail": "Failed to save image",
      "image.saveFailWithMsg": "Failed to save image: {msg}",
      "image.loadFail": "Failed to load image",
      "image.editorUnavailable": "Image editor failed to load; check whether the Konva script is reachable",
      "err.fetchSessions": "Failed to fetch sessions",
      "err.createSession": "Failed to create session",
      "err.deleteSession": "Failed to delete",
      "err.renameSession": "Failed to rename",
      "err.enableShare": "Failed to enable sharing",
      "err.upload": "File upload failed",
      "err.uploadEmpty": "No valid files selected (empty files ignored)",
      "err.loadMessages": "Failed to load messages",
      "err.sharedNotFound": "Shared session not found or sharing disabled",
      "err.clearSession": "Failed to clear session",
      "err.network":
        "Network error (ensure server is running; agent may take minutes after upload)",
      "err.requestFailed": "Request failed ({status})",
      "err.streamInterrupted":
        "Connection lost (long agent run or server error); check logs and retry",
    },
  };

  const listeners = [];

  function normalizeLang(lang) {
    if (!lang) return DEFAULT_LANG;
    if (lang === "en" || lang.startsWith("en-")) return "en";
    if (lang === "zh-CN" || lang.startsWith("zh")) return "zh-CN";
    return DEFAULT_LANG;
  }

  function getLang() {
    return normalizeLang(localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG);
  }

  function t(key, params) {
    const lang = getLang();
    const table = STRINGS[lang] || STRINGS[DEFAULT_LANG];
    let text = table[key] ?? STRINGS[DEFAULT_LANG][key] ?? key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, "g"), String(v ?? ""));
      });
    }
    return text;
  }

  function applyStaticI18n() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.placeholder = t(key);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) el.title = t(key);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      const key = el.getAttribute("data-i18n-aria");
      if (key) el.setAttribute("aria-label", t(key));
    });
    document.documentElement.lang = getLang();
    document.title = t("meta.title");
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", t("meta.description"));
    const langSelect = document.getElementById("langSelect");
    if (langSelect) langSelect.value = getLang();
  }

  function setLang(lang) {
    const next = normalizeLang(lang);
    localStorage.setItem(STORAGE_KEY, next);
    applyStaticI18n();
    listeners.forEach((fn) => {
      try {
        fn(next);
      } catch {
        /* ignore */
      }
    });
  }

  function onLangChange(fn) {
    if (typeof fn === "function") listeners.push(fn);
  }

  function init() {
    const langSelect = document.getElementById("langSelect");
    if (langSelect) {
      langSelect.value = getLang();
      langSelect.addEventListener("change", () => setLang(langSelect.value));
    }
    applyStaticI18n();
  }

  window.MassI18n = { getLang, setLang, t, applyStaticI18n, onLangChange, init };

  function toolCategoryLabel(categoryId) {
    const key = `tools.cat.${categoryId}`;
    const label = t(key);
    return label === key ? categoryId : label;
  }

  function toolDescriptionLabel(toolName, fallback) {
    const key = `tools.desc.${toolName}`;
    const label = t(key);
    return label === key ? fallback || t("tools.noDesc") : label;
  }

  window.MassI18n.toolCategoryLabel = toolCategoryLabel;
  window.MassI18n.toolDescriptionLabel = toolDescriptionLabel;
})();
