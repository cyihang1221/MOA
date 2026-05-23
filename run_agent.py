import os
from src.agent import Agent
from dotenv import load_dotenv, find_dotenv


base_dir = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(base_dir, "softwares_database_RAG")
SOURCE_DIR = os.path.join(base_dir, "softwares_database")


# 输入信息
workspace = os.path.join(base_dir, "workspace")
raw_dir = os.path.join(workspace, "raw")
mzml_dir = os.path.join(workspace, "converted_mzml")
peak_dir = os.path.join(workspace, "peak_detection_results")

data_list = f"""
{raw_dir}: 原始 .raw 质谱数据
{mzml_dir}: mzML 输出目录（msconvert 转换结果）
{peak_dir}: 峰检测结果输出目录
"""
database_file_dir = os.path.join(base_dir, "database_file")

goal_description = f"""
任务：将 raw 转为 mzML 并进行峰检测。

严格要求：
1. 必须使用工具 convert_raw_to_mzml_msconvert（Docker msconvert），不要用 ThermoRawFileParser。
   - input_dir = {raw_dir}
   - output_dir = {mzml_dir}
2. 转换完成后，使用 peak_detection_xcms_centwave 对 {mzml_dir} 下所有 mzML 做峰检测，
   结果保存到 {peak_dir}（file_pattern=*.mzML）。

注意：运行前请确保 Docker Desktop 已启动。
"""


# 加载 .env 文件中的环境变量
load_dotenv(find_dotenv(), override=False)  # 把.env文件内容放进os.environ; override=False表示.env里的值不会覆盖“已经存在的环境变量”


# 初始化并运行
agent = Agent(
    data_list=data_list,
    database_file_dir=database_file_dir,
    goal_description=goal_description,
    workspace=workspace,
    PERSIST_DIR=PERSIST_DIR,
    SOURCE_DIR=SOURCE_DIR
)
agent.run()
