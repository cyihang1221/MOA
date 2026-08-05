import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import fitz
from time import sleep


KEYWORDS = [
    # 数据转换
    "ProteoWizard", "ThermoRawFileParser", "msconvert", "OpenMS FileConverter",
    # 特征提取
    "XCMS-Centwave", "MZMine-GirdMass", "MZMine-ADAP", "OpenMS-PeakPicking",
    "OpenMS-FeatureFinderMetabo", "KPIC", "PITracer", "TracMass", "PeakOnly",
    # 冗余特征过滤
    "CAMERA", "RAMClust", "mzAnnotation",
    # 同位素识别
    "IsoXpress", "OpenMS-IsotopeTools", "TarMet", "AssayR",
    # 谱峰对齐
    "XCMS-Obiwarp", "XCMS-LOESS", "MZMine-JointAligner", "OpenMS-PeakGroup",
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
    "HMDB", "KEGG", "Reactome", "BioCyc"
]

DB = "pubmed"  # arxiv / pubmed
MAX_RESULTS = 1000
OUTPUT_DIR = "extracted_paper_method"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

Path(OUTPUT_DIR).mkdir(exist_ok=True)


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
        url = f"{base}esearch.fcgi?db=pubmed&term={keyword.replace(' ', '+')}&retmode=json&retstart={start}&retmax={retmax}"

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
                    "title": f"PMID_{pmid}",
                    "pmid": pmid,
                    "pmc": f"PMC{pmc_id}" if pmc_id else None
                })

            start += retmax
            sleep(0.5)

        except Exception as e:
            print(f"⚠️ 获取失败：{e}")
            break

    return papers


# ---------------------- 下载PDF ----------------------
def download_pdf(url, save_path):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except:
        return False
    

# ---------------------- 提取方法部分 ----------------------
def extract_method_section(full_text):
    try:
        method_match = re.search(
            r"(\nMethods|\nMaterials and Methods|\nMethod|\nExperimental|\nMaterials and Methods|\nMethods and Material|\nMethods and Materials|\nExperimental Procedures|\nMethodology|\nMaterial and methods|\nMaterials and methods|\nMaterial and Methods|\nEXPERIMENTAL PROCEDURES|\nMATERIALS AND METHODS|\nMATERIAL AND METHODS|\nMETHODS)",
            full_text
        )

        if not method_match:
            return "NO_METHOD"

        start = method_match.start()

        end = start + 10000  # 预设方法部分最大长度为10000字符
        return full_text[start:end]

    except Exception as e:
        return f"EXTRACT_ERROR: {str(e)}"


# ---------------------- 处理PDF ----------------------
def process_paper(pdf_path, title):
    try:
        with fitz.open(pdf_path) as doc:
            text = ""
            for i in range(min(10, len(doc))):
                page = doc[i]
                t = page.get_text()
                if t:
                    text += t

        method_text = extract_method_section(text)

        if method_text == "NO_METHOD":
            return False
        else:
            safe_title = str(title)[:50].replace("/","_").replace("\\","_").replace(":","_").replace("*","_")
            save_path = Path(OUTPUT_DIR) / f"{safe_title}.txt"

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(method_text)

            print(f"✅ 完成: {title[:60]}")
            return True
        
    except Exception as e:
        print(f"❌ 处理失败: {str(e)}")
        return False


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

        try:
            # 调用API搜索
            if DB == "pubmed":
                papers = search_pubmed_api(keyword, MAX_RESULTS)
            else:
                print("❌ 不支持的数据库")
                return

            print(f"✅ 找到 {len(papers)} 篇相关文献")

            # 下载并处理每一篇
            for i, p in enumerate(papers):
                print(f"\n----- 文献 {i+1}/{len(papers)} -----")
                try:
                    pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{p['pmc']}/"
                    tmp_path = Path(OUTPUT_DIR) / f"{p['pmc']}.pdf"

                    if download_pdf(pdf_url, tmp_path):
                        process_paper(tmp_path, p["title"])

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
    