import os
from typing import List, Dict
from langchain_openai import ChatOpenAI


class LLM_Client:
    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """初始化客户端，从环境变量加载。"""
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

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
        *,
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
                print()
            
            return "".join(collected_content)  # 将列表中存储的所有小块内容拼接成完整字符串并返回

        except Exception as e:  # 捕获异常类并绑定为变量
            if stream_to_stdout:
                print(f"❌ 调用LLM API时发生错误: {e}")
            return None

    def stream_think(self, messages: List[Dict[str, str]], temperature: float = 0):
        """
        流式调用 LLM：按块 yield 每一段增量文本。
        用于前端 SSE 逐字显示。
        """
        response = self.llm.stream(
            input=messages,
            temperature=temperature,
        )
        for chunk in response:
            content = getattr(chunk, "content", None)
            if content:
                yield content
