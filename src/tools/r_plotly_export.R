# Helpers to write Plotly JSON sidecars next to PNG figures (for web editor).
# Sourced from Python-generated R scripts.

save_ggplot_plotly_sidecar <- function(plot_obj, png_path) {
  if (!requireNamespace("plotly", quietly = TRUE)) {
    message("[plotly] package not installed, skip ggplot sidecar")
    return(invisible(FALSE))
  }
  tryCatch({
    json_path <- sub("\\.png$", ".plotly.json", png_path, ignore.case = TRUE)
    p_ly <- plotly::ggplotly(plot_obj)
    json <- plotly::plotly_json(p_ly, jsonedit = FALSE, pretty = FALSE)
    if (inherits(json, "json")) {
      json <- as.character(json)
    }
    writeLines(json, json_path, useBytes = TRUE)
    invisible(TRUE)
  }, error = function(e) {
    message("[plotly] ggplot sidecar failed: ", conditionMessage(e))
    invisible(FALSE)
  })
}

save_pca_plsda_plotly_sidecar <- function(
  scores,
  groups,
  png_path,
  title,
  comp = c(1, 2)
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    return(invisible(FALSE))
  }
  if (is.null(scores) || ncol(scores) < 1) {
    return(invisible(FALSE))
  }
  xi <- min(comp[1], ncol(scores))
  yi <- min(comp[length(comp)], ncol(scores))
  if (xi == yi && ncol(scores) >= 2) {
    yi <- 2
  }
  cn <- colnames(scores)
  df <- data.frame(
    x = scores[, xi],
    y = scores[, yi],
    Group = as.character(groups),
    Sample = rownames(scores),
    stringsAsFactors = FALSE
  )
  p <- ggplot2::ggplot(df, ggplot2::aes(x = .data$x, y = .data$y, color = .data$Group)) +
    ggplot2::geom_point(size = 2.2, alpha = 0.85) +
    ggplot2::theme_bw() +
    ggplot2::labs(
      title = title,
      x = cn[xi],
      y = cn[yi]
    )
  save_ggplot_plotly_sidecar(p, png_path)
}

save_heatmap_plotly_sidecar <- function(mat, png_path, title = "Heatmap") {
  if (!requireNamespace("plotly", quietly = TRUE)) {
    return(invisible(FALSE))
  }
  tryCatch({
    json_path <- sub("\\.png$", ".plotly.json", png_path, ignore.case = TRUE)
    z <- as.matrix(mat)
    p <- plotly::plot_ly(
      z = z,
      x = colnames(z),
      y = rownames(z),
      type = "heatmap",
      colorscale = "RdBu",
      showscale = TRUE
    )
    p <- plotly::layout(
      p,
      title = title,
      xaxis = list(title = ""),
      yaxis = list(title = "")
    )
    json <- plotly::plotly_json(p, jsonedit = FALSE, pretty = FALSE)
    if (inherits(json, "json")) {
      json <- as.character(json)
    }
    writeLines(json, json_path, useBytes = TRUE)
    invisible(TRUE)
  }, error = function(e) {
    message("[plotly] heatmap sidecar failed: ", conditionMessage(e))
    invisible(FALSE)
  })
}
