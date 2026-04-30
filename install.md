conda create -n MOA python=3.10
conda activate MOA
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
conda install -y r-base=4.4.3 r-devtools=2.4.5 r-biocmanager
BiocManager::install(version = "3.20", ask = FALSE, update = FALSE)

conda install -c bioconda bioconductor-xcms
conda install -c bioconda thermorawfileparser  # thermorawfileparser 是命令行工具
conda install -c bioconda mzmine  # 是 Java 软件，不是 R 包
conda install -c bioconda openms  # 开源的质谱数据分析软件平台（C++），不是 R 包
conda install -c bioconda bioconductor-camera  # R 包，library(CAMERA)

library(remotes)  # 从 github 在线安装
remotes::install_github("cbroeckl/RAMClustR", build_vignettes = TRUE, dependencies = TRUE)
remotes::install_github('aberHRML/mzAnnotation')
remotes::install_github("hcji/KPIC2")  # library(KPIC)




pip install ms-entropy
pip install git+https://github.com/biorack/blink.git
conda install -c nlesc -c bioconda -c conda-forge spec2vec   #Spec2Vec

python -m pip uninstall -y ms2deepscore matchms scikit-learn numpy scipy numba
python -m pip install --no-cache-dir \
  "numpy==1.26.4" \
  "scipy==1.11.4" \
  "scikit-learn==1.4.2" \
  "numba==0.59.1" \
  "matchms==0.27.0" \
  "ms2deepscore"

python -m pip install fastapi uvicorn python-dotenv langchain-openai

###启动前端服务
python -m uvicorn src.webapp:app --host 127.0.0.1 --port 8010

###浏览器访问
http://127.0.0.1:8010