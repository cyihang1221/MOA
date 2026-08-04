# convert data 
```bash
# Use docker and ProteoWizard msconvert to convert raw format mass spectrometry data files to mzML format and perform peak picking
for raw in <absolute path to local data directory, e.g., $(pwd)/data>/*.raw; do
  name=$(basename "$raw" .raw)
  
  docker run --rm \
    -v <absolute path to local data directory, e.g., $(pwd)/data>:/data \
    -v <absolute path to output directory, e.g., $(pwd)/output>:/output \
    chambm/pwiz-skyline-i-agree-to-the-vendor-licenses \
    wine msconvert.exe "/data/${name}.raw" \
      --mzML \
      --64 \
      --filter "peakPicking vendor msLevel=1-" \
      -o /output \
      --outfile "/output/${name}.mzML"
done
```


# peak detection
```r
# step 1: 获取 mzML 格式文件列表
library(xcms)  # version 4.4.0
library(MSnbase)  # version 2.32.0

mzml_files <- list.files(
  path = <mzML 格式文件目录>, 
  pattern = <文件名称规则, e.g., "*.mzML">, 
  full.names = TRUE)

xdata <- MSnbase::readMSData(
  mzml_files, 
  mode = "onDisk")

# step 2: 峰检测（peak detection）
xdata <- findChromPeaks(
  xdata, 
  param = CentWaveParam(
    peakwidth = c(5, 30),  # 峰宽范围（ 秒）
    snthresh = 10,  # 信噪比阈值
    ppm = 10,  # 质量偏差容限
    prefilter = c(3, 1000)  # 连续扫描点数与强度阈值
  ) 
)
```

# ============================ extract feature ============================
# RT correction/RT alignment/peak alignment
```r
library(xcms)

xdata <- adjustRtime(xdata, param = ObiwarpParam(binSize = 1))
```

# peak group
```r
library(xcms) 

xdata <- groupChromPeaks(
  xdata, 
  param = PeakDensityParam(
    sampleGroups = factor(rep(1, length(fileNames(xdata)))),  # sampleGroups 定义在 PeakDensityParam 内部
    bw = 30, # 带宽（ 秒）
    minFraction = 0.5,  # 最小出现频率
    minSamples = 1  # 最小样本数
  )
)
```

# Missing_peak_filling
```r
library(xcms) 

xdata <- fillChromPeaks(xdata, param = FillChromPeaksParam())
```
# ============================ extract feature ============================

6. 09_extract_peak_table
```r
library(xcms) 

feature_table <- featureValues(
  xdata,
  value = "into"  # 积分面积
)
feature_def <- featureDefinitions(xdata)
write.csv(feature_table, "feature_matrix.csv")
feature_def_df <- feature_def[, !sapply(feature_def, is.list)]  # 只保留非 list 列
write.csv(feature_def_df, "feature_info.csv", row.names = FALSE)


7. 10_Missing_value_filling
```python
# 缺失值处理
import pandas as pd
from sklearn.impute import KNNImputer

peak_data = pd.read_csv("feature_matrix.csv", index_col=0)  # 读取峰表
missing_threshold = 0.5
peak_data_filtered = peak_data.loc[peak_data.isnull().mean(axis=1) < missing_threshold]  # 去除缺失值过多的特征（>50%缺失）
imputer = KNNImputer(n_neighbors=5, weights="uniform")  # KNN填充缺失值

peak_data_imputed = pd.DataFrame(
  imputer.fit_transform(peak_data_filtered),
  index=peak_data_filtered.index,
  columns=peak_data_filtered.columns
) 

peak_data_imputed.to_csv("peak_data_imputed.csv")


8. 11_pqn_normalization
```python
import pandas as pd

data = pd.read_csv("peak_data_imputed.csv", index_col=0)
qc_sample_names = [col for col in peak_data_imputed.columns if 'QC' in col]
ref_profile = data[qc_sample_names].median(axis=1)  # 对QC样本取中位数
ratios = data.div(ref_profile, axis=0)  # 按行相除
correction_factors = ratios.median(axis=0)  # 按列取中位数
normalized_data = data.div(correction_factors, axis=1)  # 按列相除
pqn_normalized_data.to_csv("pqn_normalized_data.csv")


9. 12_PCA_analysis
```r
# 多变量统计分析: PCA分析
library(ggplot2)
library(ggfortify)

normalized_data <- read.csv("pqn_normalized_data.csv", row.names = 1)
pca_result <- prcomp(t(normalized_data), scale = TRUE, center = TRUE)  # 执行PCA
variance_explained <- round(pca_result$sdev^2 / sum(pca_result$sdev^2) * 100, 2)  # 计算方差解释度
pca_scores <- as.data.frame(pca_result$x)  # 绘制PCA得分图
pca_scores$Group <- sample_info$Group

ggplot(pca_scores, aes(x = PC1, y = PC2, color = Group, shape = Batch)) +
  geom_point(size = 3, alpha = 0.8) +
  stat_ellipse(level = 0.95, linetype = 2, size = 0.5) +
  labs(x = paste0("PC1 (", variance_explained[1], "%)"),
       y = paste0("PC2 (", variance_explained[2], "%)"),
       title = "PCA Score Plot") +
  theme_minimal()
