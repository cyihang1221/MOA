import os
import json
from src.llm_client import LLM_Client
from src.prompt import PromptGenerator
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from src.mcp_server.server import mcp


class Agent:
    def __init__(self, data_list, metadata_csv, goal_description, outputspace=None, PERSIST_DIR=None, SOURCE_DIR=None):
        # 基础配置
        self.data_list = data_list
        self.metadata_csv = metadata_csv
        self.goal_description = goal_description
        self.outputspace = outputspace

        # 初始化状态变量
        self.tasks = []
        self.history_summary = []
        self.tools_info = asyncio.run(self.get_all_mcp_tools_info(mcp))
        
        # 初始化核心组件
        self.llm_client = LLM_Client()
        self.prompt_generator = PromptGenerator(goal_description=self.goal_description, outputspace=self.outputspace, 
                                                PERSIST_DIR=PERSIST_DIR, SOURCE_DIR=SOURCE_DIR)  # 实例化PromptGenerator类时，会创建RAG检索器


    async def get_all_mcp_tools_info(self, mcp_server: FastMCP) -> list:
        """
        自动提取当前 mcp_server 中所有注册的工具信息，包括工具元数据 (name and description) 和参数列表 inputSchema
        参数列表 inputSchema 由函数参数解析而来，例如：async def convert_raw_to_mzml_ThermoRawFileParser_tool(input_dir: str, output_dir: str):
        """    
        tools_info = await mcp_server.list_tools()     
        return tools_info


    def _extract_json(self, response):
        """提取响应中的JSON内容"""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            return json.loads(response[start:end])  # json.loads()将符合JSON格式的str解析成Python对应的原生数据类型（这里是字典）；loads是“load string”的缩写，专门处理字符串，区别于json.load()
        except:
            return {}


    def plan_phase(self):
        """计划生成阶段"""
        print(f"\n===== : 生成分析计划 =====")
        # 生成提示词并调用LLM
        prompt = self.prompt_generator.plan_prompt(data_list=self.data_list, metadata_csv=self.metadata_csv, tools_info=self.tools_info)
        messages = [{"role": "user", "content": str(prompt)}]
        print("✅ 正在调用 LLM 生成计划")
        resp = self.llm_client.think(messages)

        # 解析计划
        plan_data = self._extract_json(resp)
        self.tasks = plan_data.get("plan", [])  # 取plan键的值，若plan键不存在，返回指定的默认值[]
        self.history_summary.append({"role":"user","content":f"Your plan for {self.goal_description} is {self.tasks}."})
        print(f"✅ 计划生成完成，共 {len(self.tasks)} 个子任务")


    async def execution_phase(self):
        """执行阶段"""
        params = StdioServerParameters(command="python", args=["-m", "src.mcp_server.server"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                while self.tasks:
                    task = self.tasks.pop(0)
                    print(f"\n===== 执行任务: {task} =====")
                    prompt = self.prompt_generator.tool_match_prompt(task=task, tools_info=self.tools_info, history_summary=self.history_summary)
                    messages = [{"role": "user", "content": str(prompt)}]
                    print(f"===== : 工具查询结果 =====")
                    response = self.llm_client.think(messages)
                    response = json.loads(response)
                    
                    if "tool_call" in response:
                        tool_name = response["tool_call"]["name"]
                        tool_args = response["tool_call"]["arguments"]
                        result = await session.call_tool(tool_name, tool_args)

                        self.history_summary.append({"role":"tool","content":str(result)})
                        print(f"\nExecuted {tool_name}, result: {result}")


    def run(self):
        """主执行入口"""
        try:
            self.plan_phase()
            asyncio.run(self.execution_phase())
            print("\n🎉 所有任务完成!")
        except Exception as e:
            print(f"\n❌ 任务中断: {str(e)}")
