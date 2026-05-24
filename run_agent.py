import os
from src.agent import Agent
from dotenv import load_dotenv, find_dotenv


base_dir = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(base_dir, "softwares_database_RAG")
SOURCE_DIR = os.path.join(base_dir, "softwares_database")


# 输入信息
workspace = os.path.join(base_dir, "workspace")
data_list = f"{os.path.join(workspace, 'raw')}: These files are mass spectrometry data in raw format."
metadata_csv = f"{os.path.join(workspace, 'metadata.csv')}: This CSV file contains sample metadata, including columns for sample ID and experimental group."
database_file_dir = os.path.join(base_dir, "database_file")

goal_description = "对thermo仪器产生的raw格式文件进行分析得到差异代谢物，并对差异代谢物质进行注释，数据格式转换使用msconvert。"


# 加载 .env 文件中的环境变量
load_dotenv(find_dotenv(), override=False)  # 把.env文件内容放进os.environ; override=False表示.env里的值不会覆盖“已经存在的环境变量”


# 初始化并运行
agent = Agent(
    data_list=data_list,
    metadata_csv=metadata_csv,
    database_file_dir=database_file_dir,
    goal_description=goal_description,
    workspace=workspace,
    PERSIST_DIR=PERSIST_DIR,
    SOURCE_DIR=SOURCE_DIR
)
agent.run()
