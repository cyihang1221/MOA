# MOA / MassAgent 环境安装

本仓库已导出当前可用的完整依赖：

| 文件 | 用途 |
|------|------|
| `requirements.txt` | 当前 conda 环境 `MOA` 的 **pip 全量导出**（已合并 `change.md` 中的 `plotly==6.0.1`、`vl-convert-python`，以及谱学栈版本钉死） |
| `environment.yml` | **推荐**创建方式：conda 关键包 + `pip -r requirements.txt` |
| `environment.full.yml` | 当前机器上的 **conda 包精确快照**（Linux x86_64；在其他系统/架构上可能无法解析） |

> `change.md` 是功能变更说明，不是依赖清单；其中提到的 pip 依赖已写入 `requirements.txt`。

---

## 方式 A（推荐）：environment.yml 一键创建

```bash
conda env create -f environment.yml
conda activate MOA
```

若 `pip install -r requirements.txt` 因 CUDA / torch 失败，可先注释掉 `requirements.txt` 里的 `nvidia-*` / `torch` / `triton` 行，再用 CPU 版 PyTorch 安装，或按下方「分步安装」处理。

---

## 方式 B：分步安装（与历史手工步骤一致，更稳）

```bash
conda create -n MOA python=3.10
conda activate MOA
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

conda install -y r-base=4.4.3 r-devtools=2.4.5 r-biocmanager
# Bioconductor 3.20
Rscript -e 'BiocManager::install(version = "3.20", ask = FALSE, update = FALSE)'

conda install -c bioconda bioconductor-xcms
conda install -y -c conda-forge r-mixomics r-pheatmap r-plotly
conda install -c bioconda thermorawfileparser  # 命令行工具
conda install -c bioconda mzmine               # Java 软件
conda install -c bioconda openms               # C++ 平台
conda install -c bioconda bioconductor-camera  # R: library(CAMERA)
```

### GitHub R 包（environment.yml 不会自动装）

```r
library(remotes)
remotes::install_github("cbroeckl/RAMClustR", build_vignettes = TRUE, dependencies = TRUE)
remotes::install_github("aberHRML/mzAnnotation")
remotes::install_github("hcji/KPIC2")  # library(KPIC)
```

### 谱学 / 网络相关 Python 包（若 requirements 未装全）

```bash
pip install ms-entropy
pip install git+https://github.com/biorack/blink.git
conda install -c nlesc -c bioconda -c conda-forge spec2vec

# 版本钉死（与当前 MOA 环境一致；勿升到 numpy 2.x）
python -m pip uninstall -y ms2deepscore matchms scikit-learn numpy scipy numba
python -m pip install --no-cache-dir \
  "numpy==1.26.4" \
  "scipy==1.11.4" \
  "scikit-learn==1.4.2" \
  "numba==0.59.1" \
  "matchms==0.27.0" \
  "ms2deepscore"
```

### 前端 / Agent 相关（已含于 requirements.txt；change.md 补充）

```bash
python -m pip install fastapi uvicorn python-dotenv langchain-openai \
  "plotly==6.0.1" vl-convert-python
```

### 谱库注释 / KEGG 富集 R 包

```bash
# Spectra / MetaboAnnotation / KEGGREST 一般已随 Bioconductor 安装；
# 若缺 MsBackendMgf / MsBackendMsp：
Rscript -e 'BiocManager::install(c("MsBackendMgf", "MsBackendMsp"), ask=FALSE, update=FALSE)'

# clusterProfiler 等推荐 conda 二进制（BiocManager 常因编译失败）
conda activate MOA
conda install -y -c bioconda -c conda-forge \
  bioconductor-clusterprofiler \
  bioconductor-enrichplot \
  bioconductor-dose \
  bioconductor-go.db
```

---

## 方式 C：精确复现当前机器 conda 包列表

```bash
conda env create -f environment.full.yml
conda activate MOA
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

仅建议在相近的 Linux x86_64 + 相同 conda/bioconda 频道状态下使用。

---

## 启动前端

```bash
conda activate MOA
python -m uvicorn web_frontend.backend.webapp:app --host 127.0.0.1 --port 8010
```

浏览器访问：http://127.0.0.1:8010

---

## 重新导出（维护者）

```bash
conda activate MOA
# pip 全量（需自行清洗 file://）
pip freeze > requirements.raw.txt
# conda 快照
conda env export -n MOA --no-builds | grep -v '^prefix:' > environment.full.yml
```
