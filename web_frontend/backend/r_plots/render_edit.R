# 改图与初图共用的 R 出图入口。
# 得分图在改图阶段只有 scores CSV，没有 mixOmics 的 pca/plsda 对象，
# 因此 plotIndiv 与 ggplot 两种风格都由这一份 ggplot2 代码按 score_style 切换。
# 火山图、VIP 柱、KEGG 用 ggplot2；VIP 热图用 pheatmap。
options(rgl.useNULL = TRUE)
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(pheatmap)
})

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) y else x

base_family <- "Noto Sans CJK SC"

# plot_config.font_size 的 title / axis / legend / label，单位 pt；缺省时用各图原来的字号。
font_value <- function(spec, key, default) {
  v <- tryCatch(suppressWarnings(as.numeric(spec$font_size[[key]])), error = function(e) NULL)
  if (length(v) != 1 || is.na(v) || v <= 0) default else v
}

legend_position <- function(spec) {
  if (identical(spec$legend_show, FALSE)) return("none")
  pos <- tolower(as.character(spec$legend_position %||% "right"))
  if (pos %in% c("right", "left", "top", "bottom")) pos else "right"
}

title_hjust <- function(spec) {
  switch(tolower(as.character(spec$title_align %||% "left")), center = 0.5, right = 1, 0)
}

theme_moa <- function(style = "bw", size = 12, spec = NULL) {
  size <- font_value(spec, "axis", size)
  base <- if (identical(style, "classic")) {
    theme_classic(base_size = size, base_family = base_family)
  } else if (identical(style, "minimal")) {
    theme_minimal(base_size = size, base_family = base_family)
  } else {
    theme_bw(base_size = size, base_family = base_family)
  }
  out <- base + theme(
    plot.title = element_text(
      face = "bold",
      hjust = title_hjust(spec),
      size = font_value(spec, "title", size * 1.2)
    ),
    legend.position = legend_position(spec),
    panel.grid.minor = element_blank()
  )
  legend_size <- font_value(spec, "legend", NA_real_)
  if (!is.na(legend_size)) {
    out <- out + theme(
      legend.text = element_text(size = legend_size),
      legend.title = element_text(size = legend_size + 1)
    )
  }
  out
}

# 离主体有一大段空档的点不进椭圆。点仍画出，只是不圈。
ellipse_member <- function(x, y) {
  n <- length(x)
  if (n < 3) return(rep(FALSE, n))
  dist <- sqrt((x - median(x))^2 + (y - median(y))^2)
  ord <- order(dist)
  sd <- dist[ord]
  keep_n <- n
  if (n >= 4) {
    for (i in 3:(n - 1)) {
      gap <- sd[i + 1] - sd[i]
      separated <- if (sd[i] <= 1e-8) gap > 1e-6 else gap > sd[i]
      if (separated) {
        keep_n <- i
        break
      }
    }
  }
  if (keep_n < 3) return(rep(FALSE, n))
  keep <- rep(FALSE, n)
  keep[ord[seq_len(keep_n)]] <- TRUE
  keep
}

# 与 ggplot2 stat_ellipse 相同的半径。用旋转后的外接范围放宽坐标，避免椭圆被裁出图框。
# per_group=FALSE 时按全体样本算一个椭圆（SIMCA 的 Hotelling T2）。
ellipse_limits <- function(df, type = "norm", level = 0.95, with_ellipse = TRUE, per_group = TRUE) {
  xlim <- range(df$x, na.rm = TRUE)
  ylim <- range(df$y, na.rm = TRUE)
  slices <- list()
  if (with_ellipse) {
    if (per_group) {
      for (gname in unique(df$group)) {
        g <- df[df$group == gname & is.finite(df$x) & is.finite(df$y), , drop = FALSE]
        if (nrow(g) < 3 || sd(g$x) <= 1e-8 || sd(g$y) <= 1e-8) next
        g <- g[ellipse_member(g$x, g$y), , drop = FALSE]
        if (nrow(g) < 3 || grepl("^QC$", gname, ignore.case = TRUE)) next
        slices[[length(slices) + 1]] <- g
      }
    } else {
      g <- df[is.finite(df$x) & is.finite(df$y), , drop = FALSE]
      if (nrow(g) >= 4 && sd(g$x) > 1e-8 && sd(g$y) > 1e-8) slices[[1]] <- g
    }
  }
  for (g in slices) {
    n <- nrow(g)
    radius <- if (identical(type, "t")) sqrt(2 * stats::qf(level, 2, max(1, n - 1))) else sqrt(stats::qchisq(level, 2))
    covm <- stats::cov(cbind(g$x, g$y))
    eg <- eigen(covm, symmetric = TRUE)
    a <- radius * sqrt(max(eg$values[1], 0))
    b <- radius * sqrt(max(eg$values[2], 0))
    theta <- atan2(eg$vectors[2, 1], eg$vectors[1, 1])
    dx <- sqrt((a * cos(theta))^2 + (b * sin(theta))^2)
    dy <- sqrt((a * sin(theta))^2 + (b * cos(theta))^2)
    cx <- mean(g$x)
    cy <- mean(g$y)
    xlim <- range(c(xlim, cx - dx, cx + dx), na.rm = TRUE)
    ylim <- range(c(ylim, cy - dy, cy + dy), na.rm = TRUE)
  }
  pad_x <- max(diff(xlim) * 0.06, 1e-6)
  pad_y <- max(diff(ylim) * 0.06, 1e-6)
  c(xlim[1] - pad_x, xlim[2] + pad_x, ylim[1] - pad_y, ylim[2] + pad_y)
}

wrap_label <- function(x, width = 28) {
  vapply(as.character(x), function(s) {
    if (!nzchar(s)) return(s)
    paste(strwrap(s, width = width), collapse = "\n")
  }, character(1), USE.NAMES = FALSE)
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("usage: Rscript render_edit.R spec.json")
}
spec <- jsonlite::fromJSON(args[[1]], simplifyVector = TRUE)

plot_type <- tolower(as.character(spec$plot_type %||% ""))
output_png <- as.character(spec$output_png)
dir.create(dirname(output_png), recursive = TRUE, showWarnings = FALSE)
title <- as.character(if (is.null(spec$title) || length(spec$title) == 0 || is.na(spec$title[[1]])) "" else spec$title[[1]])

save_gg <- function(plot, png, width = 7, height = 5.4) {
  # 默认 png/pdf 设备读不了 CJK 的 CID 字体。PNG 用 ragg，PDF 用 cairo。
  png_device <- if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else "png"
  ggsave(png, plot, width = width, height = height, dpi = 300, bg = "white", device = png_device)
  svg <- sub("\\.png$", ".svg", png)
  pdf <- sub("\\.png$", ".pdf", png)
  if (nzchar(svg) && svg != png) {
    tryCatch(
      ggsave(svg, plot, width = width, height = height, bg = "white", device = grDevices::svg),
      error = function(e) invisible(NULL)
    )
  }
  if (nzchar(pdf) && pdf != png && isTRUE(capabilities("cairo"))) {
    tryCatch(
      ggsave(pdf, plot, width = width, height = height, bg = "white", device = grDevices::cairo_pdf),
      error = function(e) invisible(NULL)
    )
  }
  invisible(png)
}

write_edit_record <- function(png, record) {
  writeLines(
    jsonlite::toJSON(record, auto_unbox = TRUE, pretty = TRUE, na = "null"),
    sub("\\.png$", ".edit_record.json", png)
  )
}

read_table <- function(path) {
  read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
}

first_sample_col <- function(df) {
  name <- colnames(df)[1]
  if (name %in% c("", "Unnamed: 0", "X", "sample", "Sample")) {
    return(df[[1]])
  }
  df[[1]]
}

score_frame <- function(spec) {
  path <- as.character(spec$scores_csv)
  raw <- read_table(path)
  sample <- as.character(first_sample_col(raw))
  nums <- raw[, vapply(raw, is.numeric, logical(1)), drop = FALSE]
  if (ncol(nums) < 1) stop("得分表没有数值列")
  comps <- spec$components
  if (is.null(comps) || length(comps) < 2) comps <- c(1, 2)
  ix <- max(1, min(ncol(nums), as.integer(comps[[1]])))
  iy <- max(1, min(ncol(nums), as.integer(comps[[2]])))
  if (ix == iy && ncol(nums) >= 2) iy <- if (ix == 1) 2 else 1
  out <- data.frame(
    sample = sample,
    x = as.numeric(nums[[ix]]),
    y = as.numeric(nums[[iy]]),
    stringsAsFactors = FALSE
  )
  out$x_name <- colnames(nums)[ix]
  out$y_name <- colnames(nums)[iy]
  meta_path <- as.character(spec$metadata_csv %||% "")
  color_by <- as.character(spec$color_by %||% "Group")
  out$group <- "Sample"
  out$size_value <- NA_real_
  size_by <- as.character(spec$size_by %||% "")
  if (nzchar(meta_path) && file.exists(meta_path)) {
    meta <- read_table(meta_path)
    if ("Sample" %in% colnames(meta)) {
      key <- as.character(meta$Sample)
      if (color_by %in% colnames(meta)) {
        mapped <- setNames(as.character(meta[[color_by]]), key)
        hit <- mapped[out$sample]
        out$group <- ifelse(is.na(hit), out$group, hit)
      }
      if (nzchar(size_by) && size_by %in% colnames(meta)) {
        sized <- setNames(suppressWarnings(as.numeric(meta[[size_by]])), key)
        out$size_value <- as.numeric(sized[out$sample])
      }
    }
  }
  out
}

axis_label <- function(plot_type, index, fallback) {
  if (identical(plot_type, "plsda")) return(sprintf("t[%d]", index))
  if (grepl("^PC", fallback, ignore.case = TRUE)) return(fallback)
  if (grepl("comp", fallback, ignore.case = TRUE)) return(sprintf("t[%d]", index))
  sprintf("PC%d", index)
}

simca_title_lines <- function(plot_title, plot_type, color_by) {
  tag <- if (identical(plot_type, "plsda")) "PLS-DA" else "PCA-X"
  plain <- tolower(plot_title)
  line1 <- if (!nzchar(plot_title) || plain %in% c(
    "pca plot", "pls-da plot", "pca score plot", "pls-da score plot", "pca", "pls-da"
  )) {
    paste0("M1 (", tag, ")")
  } else if (grepl("\\((PCA-X|PLS-DA|OPLS-DA)\\)\\s*$", plot_title, ignore.case = TRUE)) {
    plot_title
  } else {
    paste0(plot_title, " (", tag, ")")
  }
  key <- tolower(color_by %||% "")
  line2 <- if (key %in% c("", "group", "class", "classes")) {
    "Colored according to classes in M1"
  } else {
    paste0("Colored according to ", color_by)
  }
  c(line1, line2)
}

draw_scores <- function(spec) {
  d <- score_frame(spec)
  style <- tolower(as.character(spec$score_style %||% "simca"))
  use_ggplot <- startsWith(style, "ggplot")
  plot_type <- as.character(spec$plot_type)
  color_name <- as.character(spec$color_by %||% "Group")
  plot_title <- title
  subtitle <- NULL
  caption <- NULL
  if (use_ggplot) {
    x_lab <- axis_label(plot_type, 1, unique(d$x_name)[1])
    y_lab <- axis_label(plot_type, 2, unique(d$y_name)[1])
    if (!nzchar(plot_title)) {
      plot_title <- if (identical(plot_type, "plsda")) "PLS-DA plot" else "PCA plot"
    }
  } else {
    x_lab <- "t[1]"
    y_lab <- "t[2]"
    lines <- simca_title_lines(plot_title, plot_type, color_name)
    plot_title <- lines[[1]]
    subtitle <- lines[[2]]
    caption <- "Ellipse: Hotelling's T2 (95%)"
  }
  eligible <- d %>%
    group_by(group) %>%
    filter(n() >= 3, sd(x) > 1e-8, sd(y) > 1e-8, !grepl("^QC$", group, ignore.case = TRUE)) %>%
    filter(ellipse_member(x, y)) %>%
    ungroup()
  show_ellipse <- !identical(spec$ellipse, FALSE)
  p <- ggplot(d, aes(x, y, color = group))
  if (show_ellipse && use_ggplot && nrow(eligible) > 0) {
    p <- p + stat_ellipse(
      data = eligible,
      aes(fill = group),
      geom = "polygon",
      type = "norm",
      level = 0.95,
      alpha = 0.16,
      linewidth = 0.4,
      show.legend = FALSE
    )
  } else if (show_ellipse && !use_ggplot && nrow(d) >= 4) {
    # SIMCA：全体样本一个灰色 Hotelling 椭圆，不按组分圈。
    p <- p + stat_ellipse(
      data = d,
      aes(x = x, y = y),
      inherit.aes = FALSE,
      type = "t",
      level = 0.95,
      color = "grey35",
      linewidth = 0.7,
      show.legend = FALSE
    )
  }
  if (any(is.finite(d$size_value))) {
    p <- p + geom_point(aes(size = size_value), alpha = 0.9)
  } else {
    p <- p + geom_point(size = 2.4, alpha = 0.9)
  }
  pal <- spec$palette
  if (!is.null(pal) && length(pal) > 0) {
    values <- unlist(pal)
    values <- values[!is.na(values) & nzchar(values)]
    if (length(values) > 0) {
      p <- p + scale_color_manual(values = values, drop = FALSE)
      if (use_ggplot) {
        p <- p + scale_fill_manual(values = values, guide = "none")
      }
    }
  }
  show_labels <- isTRUE(spec$show_labels %||% FALSE)
  label_size <- font_value(spec, "label", 7.1) / ggplot2::.pt
  if (show_labels && use_ggplot) {
    if (requireNamespace("ggrepel", quietly = TRUE)) {
      p <- p + ggrepel::geom_text_repel(
        aes(label = sample),
        size = label_size,
        max.overlaps = 30,
        min.segment.length = 0,
        show.legend = FALSE,
        family = base_family
      )
    } else {
      p <- p + geom_text(aes(label = sample), size = label_size, vjust = -0.6, check.overlap = TRUE, show.legend = FALSE)
    }
  } else if (show_labels) {
    span <- diff(range(d$x, na.rm = TRUE))
    p <- p + geom_text(
      aes(label = sample),
      hjust = 0,
      nudge_x = max(span * 0.015, 1e-4),
      size = label_size,
      show.legend = FALSE,
      family = base_family
    )
  }
  lim <- ellipse_limits(
    d,
    type = if (use_ggplot) "norm" else "t",
    with_ellipse = show_ellipse,
    per_group = use_ggplot
  )
  p <- p + coord_cartesian(xlim = lim[1:2], ylim = lim[3:4], expand = FALSE)
  legend_title <- as.character(spec$color_by %||% "Group")
  if (use_ggplot) {
    p <- p + labs(
      title = plot_title,
      x = x_lab,
      y = y_lab,
      color = legend_title,
      size = as.character(spec$size_by %||% "size")
    )
    p <- p + theme_moa("classic", spec = spec) + theme(panel.grid = element_blank())
  } else {
    p <- p + labs(
      title = plot_title,
      subtitle = subtitle,
      caption = caption,
      x = NULL,
      y = NULL,
      color = legend_title,
      size = as.character(spec$size_by %||% "size")
    )
    p <- p + xlab(expression(t[1])) + ylab(expression(t[2]))
    p <- p + guides(color = guide_legend(override.aes = list(shape = 15, size = 3)))
    p <- p + theme_moa("bw", spec = spec) + theme(
      plot.subtitle = element_text(hjust = 0.5, size = font_value(spec, "title", 12) * 0.82),
      plot.caption = element_text(hjust = 1, size = 8),
      panel.grid.major = element_line(color = "grey85", linewidth = 0.3)
    )
  }
  save_gg(p, output_png, width = 6.6, height = 5.2)
  write_edit_record(output_png, list(
    edit_kind = as.character(spec$edit_kind %||% "style"),
    score_style = if (use_ggplot) "ggplot" else "simca",
    ellipse = show_ellipse,
    legend_position = legend_position(spec),
    x_name = unique(d$x_name)[1],
    y_name = unique(d$y_name)[1],
    n = nrow(d),
    source_csv = as.character(spec$scores_csv),
    source_unchanged = TRUE,
    coordinates_recomputed = FALSE
  ))
}

draw_volcano <- function(spec) {
  df <- read_table(as.character(spec$volcano_csv))
  if (!all(c("log2FC", "neglog10p") %in% colnames(df))) stop("火山图缺少 log2FC / neglog10p")
  p_cut <- spec$p_cut
  fc_cut <- spec$fc_cut
  p_stat <- as.character(spec$p_stat %||% "pvalue")
  used_p <- ""
  if (!is.null(p_cut) && length(p_cut) == 1 && !is.na(p_cut)) {
    if (p_stat == "padj" && "padj" %in% colnames(df)) {
      sig_p <- df$padj < as.numeric(p_cut)
      used_p <- "padj"
    } else if ("pvalue" %in% colnames(df)) {
      sig_p <- df$pvalue < as.numeric(p_cut)
      used_p <- "pvalue"
    } else if ("padj" %in% colnames(df)) {
      sig_p <- df$padj < as.numeric(p_cut)
      used_p <- "padj"
    } else {
      sig_p <- df$neglog10p >= -log10(as.numeric(p_cut))
      used_p <- "neglog10p"
    }
  } else if ("Significant" %in% colnames(df)) {
    sig_p <- as.logical(df$Significant)
  } else {
    sig_p <- rep(TRUE, nrow(df))
  }
  if (!is.null(fc_cut) && length(fc_cut) == 1 && !is.na(fc_cut)) {
    sig <- sig_p & abs(df$log2FC) >= as.numeric(fc_cut)
  } else {
    sig <- sig_p
  }
  sig[is.na(sig)] <- FALSE
  df$class <- factor(
    ifelse(!sig, "Not significant", ifelse(df$log2FC >= 0, "Up", "Down")),
    levels = c("Up", "Down", "Not significant")
  )
  colors <- spec$colors
  up <- if (!is.null(colors$upregulated)) as.character(colors$upregulated) else "#E64B35"
  down <- if (!is.null(colors$downregulated)) as.character(colors$downregulated) else "#4DBBD5"
  ns <- if (!is.null(colors$nonsignificant)) as.character(colors$nonsignificant) else "#B0B0B0"
  thr <- if (!is.null(colors$threshold_color)) as.character(colors$threshold_color) else "#666666"
  plot_title <- if (nzchar(title)) title else "Volcano Plot"
  p <- ggplot(df, aes(log2FC, neglog10p, color = class)) +
    geom_point(size = 1.6, alpha = 0.85) +
    scale_color_manual(values = c("Up" = up, "Down" = down, "Not significant" = ns), drop = FALSE) +
    theme_moa("bw", spec = spec) +
    labs(title = plot_title, x = "log2 fold change", y = expression(-log[10]~italic(p)), color = NULL)
  if (!is.null(fc_cut) && length(fc_cut) == 1 && !is.na(fc_cut)) {
    p <- p + geom_vline(xintercept = c(-as.numeric(fc_cut), as.numeric(fc_cut)), linetype = 2, color = thr)
  }
  if (!is.null(p_cut) && length(p_cut) == 1 && !is.na(p_cut)) {
    p <- p + geom_hline(yintercept = -log10(as.numeric(p_cut)), linetype = 2, color = thr)
  }
  save_gg(p, output_png, width = 6.2, height = 5.2)
  classified <- sub("\\.png$", ".classified.csv", output_png)
  keep <- intersect(c("Feature", "log2FC", "pvalue", "padj", "neglog10p", "class"), colnames(df))
  write.csv(df[, keep, drop = FALSE], classified, row.names = FALSE)
  record <- list(
    edit_kind = as.character(spec$edit_kind %||% "style"),
    p_stat = used_p,
    p_cut = if (is.null(p_cut) || length(p_cut) == 0 || is.na(p_cut[[1]])) NA else as.numeric(p_cut[[1]]),
    fc_cut = if (is.null(fc_cut) || length(fc_cut) == 0 || is.na(fc_cut[[1]])) NA else as.numeric(fc_cut[[1]]),
    n_up = sum(df$class == "Up", na.rm = TRUE),
    n_down = sum(df$class == "Down", na.rm = TRUE),
    n_not_significant = sum(df$class == "Not significant", na.rm = TRUE),
    source_csv = as.character(spec$volcano_csv),
    source_unchanged = TRUE,
    classified_csv = classified
  )
  write_edit_record(output_png, record)
}

draw_vip_bar <- function(spec) {
  vip <- read_table(as.character(spec$vip_csv))
  if (!all(c("Feature", "VIP") %in% colnames(vip))) stop("VIP 表缺少 Feature / VIP")
  vol_path <- as.character(spec$volcano_csv %||% "")
  if (nzchar(vol_path) && file.exists(vol_path)) {
    vol <- read_table(vol_path)
    if (all(c("Feature", "log2FC") %in% colnames(vol))) {
      vip <- vip %>% left_join(vol[, c("Feature", "log2FC")], by = "Feature")
    }
  }
  if (!"log2FC" %in% colnames(vip)) vip$log2FC <- NA_real_
  top_n <- as.integer(spec$top_n %||% 30)
  if (is.na(top_n) || top_n < 1) top_n <- 30
  threshold <- as.numeric(spec$vip_threshold %||% 1)
  if (is.na(threshold)) threshold <- 1
  ranked <- vip %>% filter(is.finite(VIP)) %>% arrange(desc(VIP))
  ranked$pass <- ranked$VIP >= threshold
  apply_filter <- isTRUE(spec$apply_filter %||% FALSE)
  plotted <- if (apply_filter) ranked %>% filter(pass) else ranked
  plotted <- head(plotted, top_n)
  if (nrow(plotted) < 1) stop("没有 VIP 达到该阈值的特征，未改原始 vip_scores.csv")
  filtered_path <- sub("\\.png$", ".filtered.csv", output_png)
  keep_cols <- intersect(c("Feature", "VIP", "log2FC", "pass"), colnames(ranked))
  write.csv(ranked[, keep_cols, drop = FALSE], filtered_path, row.names = FALSE)
  vip <- plotted
  vip$direction <- ifelse(is.na(vip$log2FC), "unknown", ifelse(vip$log2FC >= 0, "up", "down"))
  colors <- spec$colors
  up <- if (!is.null(colors$upregulated)) as.character(colors$upregulated) else "#E64B35"
  down <- if (!is.null(colors$downregulated)) as.character(colors$downregulated) else "#4DBBD5"
  unk <- if (!is.null(colors$bar_color)) as.character(colors$bar_color) else "#3C5488"
  thr_color <- if (!is.null(colors$threshold_color)) as.character(colors$threshold_color) else "#666666"
  vip$label <- make.unique(short_id(as.character(vip$Feature)))
  vip$label <- factor(vip$label, levels = rev(vip$label))
  plot_title <- if (nzchar(title)) title else "VIP Scores"
  p <- ggplot(vip, aes(VIP, label, fill = direction)) +
    geom_col(width = 0.72) +
    geom_vline(xintercept = threshold, linetype = 2, color = thr_color) +
    scale_fill_manual(values = c(up = up, down = down, unknown = unk), guide = "none") +
    theme_moa("classic", size = 11, spec = spec) +
    labs(title = plot_title, x = "VIP score", y = NULL)
  save_gg(p, output_png, width = 7.2, height = max(4.2, 0.22 * nrow(vip) + 1.4))
  write_edit_record(output_png, list(
    edit_kind = as.character(spec$edit_kind %||% "style"),
    vip_threshold = threshold,
    apply_filter = apply_filter,
    n_pass = sum(ranked$pass),
    n_plotted = nrow(vip),
    source_csv = as.character(spec$vip_csv),
    source_unchanged = TRUE,
    filtered_csv = filtered_path
  ))
}

short_id <- function(x) {
  x <- sub("\\|.*$", "", x)
  x <- sub("\\s*\\(VIP\\s*=.*$", "", x, ignore.case = TRUE)
  ifelse(nchar(x) > 22, paste0(substr(x, 1, 20), "..."), x)
}

draw_heatmap <- function(spec) {
  raw <- read_table(as.character(spec$matrix_csv))
  ids <- as.character(first_sample_col(raw))
  apply_filter <- isTRUE(spec$apply_filter %||% FALSE)
  threshold <- suppressWarnings(as.numeric(spec$vip_threshold %||% NA))
  n_source <- nrow(raw)
  n_vip <- n_source
  if (apply_filter && length(threshold) == 1 && !is.na(threshold)) {
    vip_path <- as.character(spec$vip_csv %||% "")
    if (!nzchar(vip_path) || !file.exists(vip_path)) stop("热图按 VIP 筛选需要 vip_scores.csv，未改原始矩阵")
    vip <- read_table(vip_path)
    if (!all(c("Feature", "VIP") %in% colnames(vip))) stop("VIP 表缺少 Feature / VIP")
    passed <- vip$Feature[is.finite(vip$VIP) & vip$VIP >= threshold]
    base <- sub("\\|.*$", "", ids)
    hit <- ids %in% passed | base %in% passed
    raw <- raw[hit, , drop = FALSE]
    ids <- ids[hit]
    n_vip <- sum(hit)
    if (nrow(raw) < 1) stop("没有 VIP 达到该阈值的特征，未改原始热图矩阵")
  }
  mat <- raw
  rownames(mat) <- make.unique(short_id(ids))
  mat <- mat[, vapply(mat, is.numeric, logical(1)), drop = FALSE]
  mat <- as.matrix(mat)
  mat[is.na(mat)] <- 0
  max_rows <- as.integer(spec$max_rows %||% 24)
  if (!is.na(max_rows) && nrow(mat) > max_rows) {
    score <- apply(mat, 1, var, na.rm = TRUE)
    keep <- order(score, decreasing = TRUE)[seq_len(max_rows)]
    mat <- mat[keep, , drop = FALSE]
  }
  filtered_path <- sub("\\.png$", ".filtered.csv", output_png)
  write.csv(data.frame(Feature = rownames(mat), stringsAsFactors = FALSE), filtered_path, row.names = FALSE)
  ann <- NULL
  meta_path <- as.character(spec$metadata_csv %||% "")
  if (nzchar(meta_path) && file.exists(meta_path)) {
    meta <- read_table(meta_path)
    if ("Sample" %in% colnames(meta) && "Group" %in% colnames(meta)) {
      mapped <- setNames(as.character(meta$Group), as.character(meta$Sample))
      groups <- mapped[colnames(mat)]
      groups[is.na(groups)] <- "NA"
      ann <- data.frame(Group = groups, row.names = colnames(mat), stringsAsFactors = FALSE)
    }
  }
  plot_title <- if (nzchar(title)) title else "Top VIP Heatmap"
  cmap <- as.character(spec$cmap %||% "")
  ramp <- if (grepl("RdBu", cmap, ignore.case = TRUE)) {
    c("#2166AC", "white", "#B2182B")
  } else {
    c("#3C5488", "white", "#E64B35")
  }
  hcol <- spec$colors
  if (!is.null(hcol$heatmap_low) && !is.null(hcol$heatmap_high)) {
    ramp <- c(as.character(hcol$heatmap_low), as.character(hcol$heatmap_mid %||% "white"), as.character(hcol$heatmap_high))
  }
  # 三色都是发散色标。Agent B 的矩阵是行 z-score，数据跨 0 时让中间色正好落在 0。
  value_range <- range(mat, na.rm = TRUE, finite = TRUE)
  centered <- length(value_range) == 2 && all(is.finite(value_range)) && value_range[1] < 0 && value_range[2] > 0
  breaks <- if (centered) {
    half <- max(abs(value_range))
    seq(-half, half, length.out = 101)
  } else {
    NA
  }
  paint <- function() {
    par(family = base_family)
    pheatmap(
      mat,
      annotation_col = ann,
      scale = "none",
      cluster_rows = nrow(mat) > 1,
      cluster_cols = ncol(mat) > 1,
      show_rownames = TRUE,
      show_colnames = FALSE,
      fontsize = font_value(spec, "legend", 10),
      fontsize_row = font_value(spec, "label", 8),
      main = plot_title,
      color = colorRampPalette(ramp)(100),
      breaks = breaks
    )
  }
  if (requireNamespace("ragg", quietly = TRUE)) {
    ragg::agg_png(output_png, width = 2400, height = 1800, res = 300, background = "white")
  } else {
    png(output_png, width = 2400, height = 1800, res = 300, type = "cairo")
  }
  paint()
  dev.off()
  for (device_name in c("svg", "pdf")) {
    path <- sub("\\.png$", paste0(".", device_name), output_png)
    if (path == output_png) next
    try({
      if (device_name == "pdf") grDevices::cairo_pdf(path, width = 8, height = 6) else grDevices::svg(path, width = 8, height = 6)
      paint()
      grDevices::dev.off()
    }, silent = TRUE)
  }
  write_edit_record(output_png, list(
    edit_kind = as.character(spec$edit_kind %||% "style"),
    apply_filter = apply_filter,
    vip_threshold = if (length(threshold) == 1 && !is.na(threshold)) threshold else NA,
    n_source = n_source,
    n_after_vip = n_vip,
    n_plotted = nrow(mat),
    color_center_zero = centered,
    source_csv = as.character(spec$matrix_csv),
    source_unchanged = TRUE,
    filtered_csv = filtered_path
  ))
}

kegg_frame <- function(spec) {
  df <- read_table(as.character(spec$kegg_csv))
  if (!"Description" %in% colnames(df)) stop("KEGG 表缺少 Description")
  if (!"Count" %in% colnames(df)) df$Count <- 1
  if (!"p.adjust" %in% colnames(df)) {
    if ("pvalue" %in% colnames(df)) df$p.adjust <- df$pvalue else df$p.adjust <- 1
  }
  top_n <- as.integer(spec$top_n %||% 15)
  if (is.na(top_n) || top_n < 1) top_n <- 15
  n_source <- nrow(df)
  apply_filter <- isTRUE(spec$apply_filter %||% FALSE)
  fdr_cut <- suppressWarnings(as.numeric(spec$fdr_cut %||% NA))
  n_fdr <- n_source
  if (apply_filter && length(fdr_cut) == 1 && !is.na(fdr_cut)) {
    df <- df %>% filter(is.finite(p.adjust), p.adjust < fdr_cut)
    n_fdr <- nrow(df)
  }
  if (nrow(df) < 1) stop("没有通路通过该 FDR 阈值，未改原始 kegg_compound_enrich.csv")
  df <- df %>% arrange(p.adjust) %>% head(top_n)
  df$Description <- wrap_label(df$Description)
  df$neglog <- -log10(pmax(df$p.adjust, 1e-300))
  list(df = df, n_source = n_source, n_fdr = n_fdr, fdr_cut = fdr_cut, apply_filter = apply_filter)
}

draw_kegg <- function(spec) {
  packed <- kegg_frame(spec)
  df <- packed$df
  kind <- as.character(spec$plot_type)
  plot_title <- title
  if (!nzchar(plot_title)) {
    plot_title <- switch(
      kind,
      kegg_barplot = "KEGG Compound Enrichment Barplot",
      kegg_dotplot = "KEGG Compound Enrichment Dotplot",
      "KEGG Compound Pathway Enrichment"
    )
  }
  # 三种图颜色方向一致：越显著越接近 enrich_high。
  colors <- spec$colors
  strong <- as.character(colors$enrich_high %||% "red")
  weak <- as.character(colors$enrich_low %||% "blue")
  bar_fill <- as.character(colors$bar_color %||% "#3C5488")
  if (identical(kind, "kegg_barplot")) {
    p <- ggplot(df, aes(reorder(Description, Count), Count)) +
      geom_col(fill = bar_fill, width = 0.72) +
      coord_flip() +
      theme_moa("classic", size = 11, spec = spec) +
      labs(title = plot_title, x = NULL, y = "Count")
  } else if (identical(kind, "kegg_dotplot")) {
    p <- ggplot(df, aes(neglog, reorder(Description, neglog), size = Count, color = p.adjust)) +
      geom_point(alpha = 0.9) +
      scale_color_gradient(low = strong, high = weak) +
      theme_moa("bw", size = 11, spec = spec) +
      labs(title = plot_title, x = expression(-log[10]~FDR), y = NULL, color = "FDR", size = "Count")
  } else {
    p <- ggplot(df, aes(Count, reorder(Description, -p.adjust), size = Count, color = neglog)) +
      geom_point(alpha = 0.85) +
      scale_color_gradient(low = weak, high = strong) +
      theme_moa("minimal", size = 11, spec = spec) +
      labs(
        title = plot_title,
        x = "Number of Compounds",
        y = NULL,
        color = "-log10(FDR)",
        size = "Count"
      )
  }
  save_gg(p, output_png, width = 8.2, height = max(4.6, 0.28 * nrow(df) + 1.6))
  filtered_path <- sub("\\.png$", ".filtered.csv", output_png)
  keep <- intersect(c("ID", "Description", "Count", "pvalue", "p.adjust", "qvalue"), colnames(df))
  write.csv(df[, keep, drop = FALSE], filtered_path, row.names = FALSE)
  write_edit_record(output_png, list(
    edit_kind = as.character(spec$edit_kind %||% "style"),
    apply_filter = packed$apply_filter,
    fdr_cut = if (length(packed$fdr_cut) == 1 && !is.na(packed$fdr_cut)) packed$fdr_cut else NA,
    n_source = packed$n_source,
    n_after_fdr = packed$n_fdr,
    n_plotted = nrow(df),
    source_csv = as.character(spec$kegg_csv),
    source_unchanged = TRUE,
    filtered_csv = filtered_path
  ))
}

if (plot_type %in% c("pca", "plsda")) {
  draw_scores(spec)
} else if (plot_type == "volcano") {
  draw_volcano(spec)
} else if (plot_type == "vip_bar") {
  draw_vip_bar(spec)
} else if (plot_type == "heatmap_vip") {
  draw_heatmap(spec)
} else if (plot_type %in% c("kegg_bubble", "kegg_dotplot", "kegg_barplot")) {
  draw_kegg(spec)
} else {
  stop(paste("unsupported plot_type", plot_type))
}

if (!file.exists(output_png)) stop(paste("R 未写出", output_png))
