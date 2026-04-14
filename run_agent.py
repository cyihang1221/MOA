import os
from src.agent import Agent
from dotenv import load_dotenv, find_dotenv


base_dir = os.path.dirname(os.path.abspath(__file__))
PERSIST_DIR = os.path.join(base_dir, "softwares_database_RAG")
SOURCE_DIR = os.path.join(base_dir, "softwares_database")


# 输入信息
workspace = os.path.join(base_dir, "workspace")
data_list = f"{os.path.join(workspace, 'raw')}: These files are mass spectrometry data in raw format."
database_file_dir = os.path.join(base_dir, "database_file")

goal_description = "使用 Bruker 仪器获取了从湄公血吸虫成虫感染的实验小鼠提取的代谢物样本的 raw 格式数据，请进行数据格式转换和峰提取，不要做其他的。"


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
