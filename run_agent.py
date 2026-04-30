import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=False)
from src.agent import Agent

base_dir = os.path.dirname(os.path.abspath(__file__))
workspace = os.path.join(base_dir, "workspace")
database_file_dir = os.path.join(base_dir, "database_file")

raw_dir = os.path.join(workspace, "raw")
mzml_dir = os.path.join(workspace, "converted_mzml")
mgf_dir = os.path.join(workspace, "converted_mgf")
reference_mgf = os.path.join(database_file_dir, "spectraverse-1.0.1.mgf")
result_dir = os.path.join(workspace, "library_match_results")

ms2deepscore_model = os.getenv(
    "MS2DEEPSCORE_MODEL_PATH",
    os.path.join(base_dir, "softwares", "ms2deepscore", "ms2deepscore_model.pt")
)

data_list = f"""
{raw_dir}: 原始 .raw 质谱数据目录
{mzml_dir}: 转换后的 mzML 输出目录
{mgf_dir}: 转换后的 MGF 输出目录
{reference_mgf}: 参考谱库 MGF 文件
{ms2deepscore_model}: MS2DeepScore 模型路径
{result_dir}: 最终匹配结果输出目录
"""

goal_description = f"""
任务：**只使用 MS2DeepScore 一种方法**，对整个谱图进行完整的一站式库匹配。

严格按以下步骤执行，不要使用其他任何库匹配方法：

1. 使用 convert_raw_to_mzml_ThermoRawFileParser 将 {raw_dir} 下的所有 .raw 转为 mzML，输出到 {mzml_dir}。
2. 使用 mzml_directory_to_mgf 将 {mzml_dir} 下的所有 mzML 转为 MGF，输出到 {mgf_dir}。
3. 使用 library_match_full_workflow 完成完整匹配，参数必须如下：
   - raw_input_dir = {raw_dir}
   - mzml_output_dir = {mzml_dir}
   - mgf_output_dir = {mgf_dir}
   - reference_mgf_path = {reference_mgf}
   - model_path = "{ms2deepscore_model}"
   - output_dir = {result_dir}

只允许调用一次 library_match_full_workflow，不要重复调用，不要尝试 cosine、jaccard、spec2vec、blink 等其他方法。
完成后请输出清晰的完成摘要，并说明结果文件位置。
"""

agent = Agent(
    data_list=data_list,
    database_file_dir=database_file_dir,
    goal_description=goal_description,
    workspace=workspace,
    PERSIST_DIR=os.path.join(base_dir, "softwares_database_RAG"),
    SOURCE_DIR=os.path.join(base_dir, "softwares_database"),
)
agent.run()