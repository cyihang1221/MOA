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
  if (!requireNamespace("plotly", quietly = TRUE)) {
    return(invisible(FALSE))
  }
  if (is.null(scores) || ncol(scores) < 1) {
    return(invisible(FALSE))
  }
  tryCatch({
    xi <- min(comp[1], ncol(scores))
    yi <- min(comp[length(comp)], ncol(scores))
    if (xi == yi && ncol(scores) >= 2) {
      yi <- 2
    }
    cn <- colnames(scores)
    groups <- as.character(groups)
    sample_names <- rownames(scores)
    palette <- c("#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4")

    p <- plotly::plot_ly()
    unique_groups <- unique(groups)
    for (i in seq_along(unique_groups)) {
      g <- unique_groups[[i]]
      idx <- groups == g
      p <- plotly::add_trace(
        p,
        x = scores[idx, xi, drop = TRUE],
        y = scores[idx, yi, drop = TRUE],
        type = "scatter",
        mode = "markers",
        name = g,
        marker = list(
          size = 10,
          opacity = 0.85,
          color = palette[((i - 1) %% length(palette)) + 1]
        ),
        text = sample_names[idx],
        hovertemplate = paste0(
          "%{text}<br>",
          cn[xi], ": %{x:.3f}<br>",
          cn[yi], ": %{y:.3f}",
          "<extra>", g, "</extra>"
        )
      )
    }

    p <- plotly::layout(
      p,
      title = list(text = title),
      xaxis = list(
        title = cn[xi],
        showgrid = TRUE,
        gridcolor = "#ebebeb",
        zeroline = FALSE
      ),
      yaxis = list(
        title = cn[yi],
        showgrid = TRUE,
        gridcolor = "#ebebeb",
        zeroline = FALSE
      ),
      template = "plotly_white",
      autosize = TRUE,
      margin = list(l = 60, r = 30, t = 70, b = 60),
      paper_bgcolor = "white",
      plot_bgcolor = "white",
      legend = list(title = list(text = "Group"))
    )

    json_path <- sub("\\.png$", ".plotly.json", png_path, ignore.case = TRUE)
    json <- plotly::plotly_json(p, jsonedit = FALSE, pretty = FALSE)
    if (inherits(json, "json")) {
      json <- as.character(json)
    }
    writeLines(json, json_path, useBytes = TRUE)
    invisible(TRUE)
  }, error = function(e) {
    message("[plotly] PCA sidecar failed: ", conditionMessage(e))
    invisible(FALSE)
  })
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
