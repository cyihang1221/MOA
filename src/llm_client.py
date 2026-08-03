import os
from typing import List, Dict
from openai import OpenAI


class LLM_Client:
    """通用 LLM 调用客户端，支持 OpenAI 兼容接口。"""

    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        self.model = os.getenv("LLM_MODEL_ID")
        apiKey = os.getenv("LLM_API_KEY")
        baseUrl = os.getenv("LLM_BASE_URL")
        timeout = int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def think(self, messages: List[Dict[str, str]], temperature: float = 0):
        """调用大语言模型进行思考，返回流式响应拼接结果。"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )

            collected_content = []
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected_content.append(content)
            print()
            return "".join(collected_content)

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None
