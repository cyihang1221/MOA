import os
import sys
import traceback
from pathlib import Path

from src.llm_client import LLM_Client
from src.json_parse import extract_first_json_object, parse_tool_call
from src.prompt import PromptGenerator
import asyncio
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from src.mcp_server.server import mcp
from src.platform_utils import mcp_stdio_parameters, should_fallback_to_msconvert


class Agent:
    def __init__(self, data_list, database_file_dir, goal_description, workspace=None, PERSIST_DIR=None, SOURCE_DIR=None):
        # 基础配置
        self.data_list = data_list
        self.goal_description = goal_description
        self.database_file_dir = database_file_dir
        self.workspace = workspace

        # 初始化状态变量
        self.tasks = []
        self.history_summary = []
        self.tools_info = asyncio.run(self.get_all_mcp_tools_info(mcp))
        
        # 初始化核心组件
        self.llm_client = LLM_Client()
        self.prompt_generator = PromptGenerator(goal_description=self.goal_description, PERSIST_DIR=PERSIST_DIR, SOURCE_DIR=SOURCE_DIR)  # 实例化PromptGenerator类时，会创建RAG检索器


    async def get_all_mcp_tools_info(self, mcp_server: FastMCP) -> list:
        """
        自动提取当前 mcp_server 中所有注册的工具信息，包括工具元数据 (name and description) 和参数列表 inputSchema
        参数列表 inputSchema 由 函数参数解析而来，例如：async def convert_raw_to_mzml_ThermoRawFileParser_tool(input_dir: str, output_dir: str):
        """    
        tools_info = await mcp_server.list_tools()     
        return tools_info


    def plan_phase(self):
        """计划生成阶段"""
        print(f"\n===== : 生成分析计划 =====")
        # 生成提示词并调用LLM
        prompt = self.prompt_generator.plan_prompt(data_list=self.data_list, tools_info=self.tools_info)
        messages = [{"role": "user", "content": str(prompt)}]
        print("✅ 正在调用 LLM 生成计划")
        resp = self.llm_client.think(messages)

        # 解析计划
        plan_data = extract_first_json_object(resp or "")
        self.tasks = plan_data.get("plan", [])  # 取plan键的值，若plan键不存在，返回指定的默认值[]
        self.history_summary.append({"role":"user","content":f"Your plan for {self.goal_description} is {self.tasks}."})
        print(f"✅ 计划生成完成，共 {len(self.tasks)} 个子任务")


    async def execution_phase(self):
        """执行阶段"""
        params = mcp_stdio_parameters()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                while self.tasks:
                    task = self.tasks.pop(0)
                    print(f"\n===== 执行任务: {task} =====")
                    prompt = self.prompt_generator.tool_match_prompt(task=task, tools_info=self.tools_info, workspace=self.workspace, history_summary=self.history_summary)
                    messages = [{"role": "user", "content": str(prompt)}]
                    print(f"===== : 工具查询结果 =====")
                    raw_response = self.llm_client.think(messages)
                    tool_name, tool_args = parse_tool_call(raw_response or "")

                    if should_fallback_to_msconvert(tool_name):
                        tool_name = "convert_raw_to_mzml_msconvert"
                        print("ℹ️ 未检测到 ThermoRawFileParser，改用 convert_raw_to_mzml_msconvert")

                    if tool_name and tool_args:
                        print(f"正在调用工具 {tool_name}（R/Docker 步骤可能需数分钟，请查看下方进度输出）...")
                        try:
                            result = await session.call_tool(tool_name, tool_args)
                            self.history_summary.append({"role":"tool","content":str(result)})
                            print(f"\nExecuted {tool_name}, result: {result}")
                        except Exception as e:
                            err_msg = f"Tool call failed: {tool_name}, error={repr(e)}"
                            self.history_summary.append({"role": "tool", "content": err_msg})
                            print(f"\n❌ {err_msg}")
                            print(traceback.format_exc())
                    else:
                        err_msg = f"Tool match parse failed, raw response: {raw_response!r}"
                        self.history_summary.append({"role": "assistant", "content": err_msg})
                        print(f"\n❌ {err_msg}")


    def run(self):
        """主执行入口"""
        try:
            self.plan_phase()
            asyncio.run(self.execution_phase())
            print("\n🎉 所有任务完成!")
        except Exception as e:
            print(f"\n❌ 任务中断: {str(e)}")
            print(traceback.format_exc())
