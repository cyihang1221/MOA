import os
from typing import List, Dict
from langchain_openai import ChatOpenAI


class LLM_Client:
    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """初始化客户端，从环境变量加载。"""
        self.model = os.getenv("LLM_MODEL_ID")
        apiKey = os.getenv("LLM_API_KEY")
        baseUrl = os.getenv("LLM_BASE_URL")
        timeout = int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.llm = ChatOpenAI(
            model=self.model, 
            api_key=apiKey, 
            base_url=baseUrl, 
            timeout=timeout,
            temperature=0.0  # default
        )

    def think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream_to_stdout: bool = True,
    ):
        """调用大语言模型进行思考，并返回其响应。"""
        try:
            response = self.llm.stream(
                input=messages,
                temperature=temperature  # 对于代码生成任务，使用0，保证确定性
            )

            # 处理流式响应
            collected_content = []
            for chunk in response:
                content = chunk.content
                if content:
                    if stream_to_stdout:
                        print(content, end="", flush=True)
                    collected_content.append(content)
            if stream_to_stdout and collected_content:
                print()  # 流式输出结束后换行
            
            return "".join(collected_content)  # 将列表中存储的所有小块内容拼接成完整字符串并返回

        except Exception as e:  # 捕获异常类并绑定为变量
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None
