#!/usr/bin/env python3
"""
MOA V3.0 — 知识驱动代谢组学智能体

三阶段架构：
  Phase 1: RAG 检索知识库 → LLM 生成结构化计划
  Phase 2: MCP 工具执行 + 每步 LLM 质检 → 失败自动修正
  Phase 3: RAG 检索文献 → LLM 生成综合分析报告

用法:
    conda activate MOA
    python run_agent_v3.py
"""

import os
import sys

# ---- 确保当前目录在 Python 路径中 ----
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)   # 切换到项目根目录，确保 MCP 子进程继承正确的 CWD
sys.path.insert(0, ROOT)

from src.agent import Agent
from dotenv import load_dotenv

# ---- 路径配置 ----
PERSIST_DIR = os.path.join(ROOT, "softwares_database_RAG")
SOURCE_DIR = os.path.join(ROOT, "softwares_database")
INPUT_DIR = os.path.join(ROOT, "inputspace")
OUTPUT_DIR = os.path.join(ROOT, "outputspace")

# ---- 加载环境变量 ----
load_dotenv(os.path.join(ROOT, ".env"), override=False)

# ---- 输入数据 ----
data_list = f"{os.path.join(INPUT_DIR, 'raw')}: Mass spectrometry data in raw format (Thermo)."
metadata_csv_path = os.path.join(INPUT_DIR, 'metadata.csv')
metadata_csv_description = "Sample metadata CSV with Sample and Group columns."

# ---- 分析目标 ----
goal_description = (
    "对thermo仪器产生的raw格式文件进行分析得到差异代谢物，"
    "并对差异代谢物质进行注释，数据格式转换使用msconvert。"
)

# ---- 启动 ----
if __name__ == "__main__":
    agent = Agent(
        data_list=data_list,
        metadata_csv_path=metadata_csv_path,
        metadata_csv_description=metadata_csv_description,
        goal_description=goal_description,
        outputspace=OUTPUT_DIR,
        PERSIST_DIR=PERSIST_DIR,
        SOURCE_DIR=SOURCE_DIR,
        max_retries=3,
        similarity_top_k=5,
    )
    agent.run()
