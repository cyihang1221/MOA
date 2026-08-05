# 暂未成功运行
"""通过【MS+软件名】关键词检索PMC全文，获取文献html文本，通过标签提取方法部分，去标签，调用LLM分析方法细节并保存结果"""

import json
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
import fitz
from time import sleep
from src.llm_client import LLM_Client
from dotenv import load_dotenv, find_dotenv


# ---------------------- 基础设置 ----------------------
KEYWORDS = [ 
    # 数据转换 
    "ProteoWizard", "ThermoRawFileParser", "msconvert", 
    # 特征提取 
    "XCMS", "MZMine", "OpenMS", "KPIC", "PITracer", "TracMass", "PeakOnly", 
    # 冗余特征过滤 
    "CAMERA", "RAMClust", "mzAnnotation", 
    # 同位素识别 
    "IsoXpress", "TarMet", "AssayR", 
    # 谱峰对齐 
    "FFT-based", "DTW-based", 
    # 批次效应校正 
    "WaveICA", "MetNormalizer", "MetaboGroupS", 
    # 缺失值填充 
    "kNN", "MissForest", "Bayesian PCA", 
    # 统计分析 
    "metaX", "mixOmics", "scikit-learn", "SIMCA", "DeepLearning-based", 
    # 库匹配定性 
    "Jaccard", "Cosine", "Spectral entropy", "Spec2Vec", "MS2DeepScore", "BLINK", "MS-BERT", 
    # 未知物定性 
    "CFM-ID", "SIRIUS", "MS-Finder", "DeepMASS", "CSU-MS2", "MetDNA", "E-SGMN", "NEIMS", 
    # 网络分析 
    "GNPS", "FBMN", "MS2LDA", "MolNetEnhancer", 
    # 富集分析 
    "MetaboAnalyst", "mummichog", "GSEA", "ChemRICH", 
    # 通路分析 
    "HMDB", "KEGG", "Reactome", "BioCyc" ]

DB = "pubmed"  # arxiv / pubmed
MAX_RESULTS = 200
OUTPUT_DIR = "extracted_paper_method_V4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

Path(OUTPUT_DIR).mkdir(exist_ok=True)


# ---------------------- LLM 配置 ----------------------
load_dotenv(find_dotenv(), override=False)  
llm_client = LLM_Client()


# ---------------------- PubMed 检索 ----------------------
def get_pmc_ids(pmids):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

    pmc_map = {}

    for pmid in pmids:
        url = f"{base}?dbfrom=pubmed&db=pmc&id={pmid}&retmode=json"

        try:
            r = requests.get(url, timeout=10).json()
            pmc_id = None

            for linkset in r.get("linksets", []):
                for db in linkset.get("linksetdbs", []):
                    if db.get("linkname") == "pubmed_pmc":
                        links = db.get("links", [])
                        if links:
                            pmc_id = links[0]

            pmc_map[pmid] = pmc_id

        except:
            pmc_map[pmid] = None

        sleep(0.3)  # 防封

    return pmc_map


def search_pubmed_api(keyword, max_results):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    papers = []
    retmax = 100
    start = 0

    while len(papers) < max_results:
        # 检索PMC全文
        term = urllib.parse.quote(keyword)
        url = f"{base}esearch.fcgi?db=pmc&term={term}&retmode=json&retstart={start}&retmax={retmax}"

        try:
            data = requests.get(url, timeout=10).json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                break

            # ✅ 用 elink 查 PMC
            pmc_map = get_pmc_ids(ids)

            for pmid in ids:
                if len(papers) >= max_results:
                    break

                pmc_id = pmc_map.get(pmid)

                papers.append({
                    "title": f"PMID{pmid}",
                    "pmid": pmid,
                    "pmc": f"PMC{pmc_id}" if pmc_id else None
                })

            start += retmax
            sleep(0.5)

        except Exception as e:
            print(f"⚠️ 获取失败：{e}")
            break

    return papers


# ---------------------- 下载论文html网页 .txt ----------------------
def download_txt(url, save_path):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except:
        return False
    

# ---------------------- 提取方法部分 ----------------------
def extract_material_method(full_text):
    try:
        material_method_match = re.search(
            r"(>Methods</h2>|>METHODS</h2>|>Method</h2>|>METHOD</h2>|>Materials and Methods</h2>|>Material and Methods</h2>|>Material and Method</h2>|>Material and methods</h2>|>Materials and methods</h2>|>Material and method</h2>|>MATERIALS AND METHODS</h2>|>MATERIAL AND METHODS</h2>|>MATERIAL AND METHOD</h2>)",  # 根据标签标题定位方法部分
            full_text
        )

        if not material_method_match:
            return "NO_METHOD"

        start = material_method_match.start()

        end = start + 30000  # 预设方法部分最大长度为30000字符
        return full_text[start:end]

    except Exception as e:
        return f"EXTRACT_ERROR: {str(e)}"


# ---------------------- 处理PDF ----------------------
def process_paper(txt_path, title, keyword=None):
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
        raw_text = extract_material_method(text)

        # 去除HTML标签，保留文本内容
        soup = BeautifulSoup(raw_text, "html.parser")
        material_method_text = soup.get_text(separator="\n")  # 用换行分隔段落

        if material_method_text == "NO_METHOD":
            return False
        else:
            # 保存原始的方法文本
            material_method_text = material_method_text.replace("\n", " ").strip()
            safe_title = str(title)[:50].replace("/","_").replace("\\","_").replace(":","_").replace("*","_")
            save_path0 = Path(OUTPUT_DIR) / "original_methods" / f"{keyword}_{safe_title}.txt"
            Path(save_path0).parent.mkdir(parents=True, exist_ok=True)  # 自动创建所有不存在的父文件夹
            with open(save_path0, "w", encoding="utf-8") as f:
                f.write(material_method_text)

            # ============  LLM 提取方法细节 ============
            method_summary_prompt = {
                "role": "You are a helpful assistant for summarizing the materials and methods section of a paper. You should strictly follow the rules to summarize the method section.",
                "rules": [
                    "You should only respond in JSON format with my fixed format.",
                    "Your JSON response should only be enclosed in double quotes.",
                    "You should not write anything else except for your JSON response.",
                    "You should make your answer as detailed as possible.",
                    "You should firstly judge whether the content is related to the method of the software tool. If it is not related, you should respond with an empty JSON object.",
                ],
                "materials and methods section text": material_method_text,
                "fixed format for JSON response": {
                    "sample_description": "a detailed description of the sample used in the research",
                    f"{keyword}_configuration_description": f"a detailed description of the configuration of the software {keyword} used in the research, including the parameters and settings used in the method section",
                    "process_procedure_description": "a detailed description of the process procedure used in the research, including the software name, parameters and settings used in the method section",
                }
            }

            messages = [{"role": "user", "content": str(method_summary_prompt)}]
            response = llm_client.think(messages)
            response = json.loads(response)
            # ============  LLM 提取方法细节 ============
            
            save_path1 = Path(OUTPUT_DIR)  / "all.txt"  # 所有方法细节汇总
            save_path2 = Path(OUTPUT_DIR) / f"{keyword}.txt"  # 按软件分类的细节汇总

            with open(save_path1, "a", encoding="utf-8") as f:
                f.write(str(response) + "\n")

            with open(save_path2, "a", encoding="utf-8") as f:
                tmp = f"========== sample_description&software_configuration_description entry ==========\nsample_description: {response['sample_description']}\nsoftware_configuration_description: {response[f'{keyword}_configuration_description']}\n\n"
                f.write(tmp)

            print(f"✅ 完成: {title[:60]}")
            return True


# ---------------------- 主函数 ----------------------
def main():
    total_keywords = len(KEYWORDS)
    print(f"🚀 开始批量检索 {total_keywords} 个代谢组学软件工具")
    print(f"📦 检索库: {DB}")
    print(f"📌 每个关键词最多获取: {MAX_RESULTS} 篇\n")

    # 循环遍历每一个软件关键词
    for idx, keyword in enumerate(KEYWORDS, 1):
        print(f"\n==================================================")
        print(f"🔎 【{idx}/{total_keywords}】正在检索软件: {keyword}")
        print(f"==================================================\n")

        pubmed_query = f"(mass spectrometry OR mass spectrum OR MS OR LC-MS OR LC-MS/MS OR GC-MS) AND ({keyword}) AND \"PMC Full Text\"[Filter]"  # 直接在检索语句中加入 "PMC Full Text" 过滤器，确保只检索有PMC全文的文献

        try:
            # 调用API搜索
            if DB == "pubmed":
                papers = search_pubmed_api(pubmed_query , MAX_RESULTS)
            else:
                print("❌ 不支持的数据库")
                return

            print(f"✅ 找到 {len(papers)} 篇相关文献")

            # 下载并处理每一篇
            for i, p in enumerate(papers):
                print(f"\n----- 文献 {i+1}/{len(papers)} -----")
                try:
                    txt_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{p['pmc']}/"
                    tmp_path = Path(OUTPUT_DIR) / "original_html" / f"{keyword}_{p['pmc']}.txt"
                    Path(tmp_path).parent.mkdir(parents=True, exist_ok=True)  # 自动创建所有不存在的父文件夹

                    if download_txt(txt_url, tmp_path):
                        process_paper(tmp_path, p["pmc"], keyword)

                except Exception as e:
                    print(f"❌ 文献处理失败: {str(e)}")
                sleep(1)

        except Exception as e:
            print(f"❌ 关键词 {keyword} 检索失败: {str(e)}")

        # 每个关键词之间休息，防止请求过快被封
        sleep(2)

    print("\n🎉 所有软件关键词检索全部完成！")

if __name__ == "__main__":
    main()
    