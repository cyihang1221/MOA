import os.path
import os
import re
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def preload_retriever(local_engine=False, PERSIST_DIR=None, SOURCE_DIR=None, similarity_top_k=5):
    """
    预加载或创建 RAG 检索器。

    :param local_engine: 是否使用本地模型
    :param PERSIST_DIR: 向量索引持久化目录
    :param SOURCE_DIR: 原始文档目录
    :param similarity_top_k: 检索返回的文档片段数量（V3.0 默认 5，V1.0 为 1）
    """
    if not local_engine:
        if os.getenv("LLM_MODEL_TYPE") == "openai":
            Settings.embed_model = OpenAIEmbedding(api_key=os.getenv("LLM_API_KEY"))
        elif os.getenv("LLM_MODEL_TYPE") == "DashScope":
            Settings.embed_model = DashScopeEmbedding(api_key=os.getenv("LLM_API_KEY"))
        else:
            Settings.embed_model = HuggingFaceEmbedding(
                model_name="BAAI/bge-small-en-v1.5"
            )

    if not os.path.exists(PERSIST_DIR):
        documents = SimpleDirectoryReader(SOURCE_DIR, recursive=True).load_data()
        index = VectorStoreIndex.from_documents(documents, embeddings=Settings.embed_model)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)

    retriever = index.as_retriever(similarity_top_k=similarity_top_k)
    return retriever


# DashScope text-embedding-v2 的 token 限制
EMBED_MAX_TOKENS = 2048
# 安全余量：使用 90% 的 token 预算（1843 tokens），
# 为 token 估算误差和 embedding 模型开销留缓冲
EMBED_SAFE_TOKENS = int(EMBED_MAX_TOKENS * 0.9)

# CJK 统一字符范围（中文/日文/韩文）
_CJK_RE = re.compile(
    r'[一-鿿㐀-䶿豈-﫿'  # CJK Unified
    r'　-〿＀-￯'                 # CJK 标点/全角
    r'぀-ゟ゠-ヿ'                 # 日文假名
    r'가-힯\ud800-􏰀-\udfff]'   # 韩文 + 代理对
)
# ASCII 字母和空白
_ASCII_RE = re.compile(r'[a-zA-Z\s]')


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数（字符类型感知）。

    不同字符类型的 token 密度差异很大：
    - CJK 字符（中文/日文/韩文）：约 1.5 字符/token → 系数 0.67
    - ASCII 字母/空白：约 4 字符/token → 系数 0.25
    - 其他（数字、符号、换行等）：约 3 字符/token → 系数 0.33

    旧实现使用 1:1 字符→token 映射，对中文文本严重低估风险
    （2048 中文字符 ≈ 3070 tokens，远超 2048 限制），
    导致 DashScope embedding API 返回空向量。
    """
    cjk_chars = len(_CJK_RE.findall(text))
    ascii_chars = len(_ASCII_RE.findall(text))
    other_chars = len(text) - cjk_chars - ascii_chars

    tokens = cjk_chars / 1.5 + ascii_chars / 4.0 + other_chars / 3.0
    return int(tokens)


def _truncate_prompt(prompt: str, max_tokens: int = EMBED_SAFE_TOKENS) -> str:
    """截断过长的检索 prompt，避免超出 embedding 模型的 token 限制。

    DashScope text-embedding-v2 限制 2048 tokens。
    先估算 token 数，超限时按比例截断（保留前半部分，截掉尾部）。
    使用字符类型感知的 _estimate_tokens() 替代简单的字符计数。
    """
    estimated = _estimate_tokens(prompt)
    if estimated <= max_tokens:
        return prompt

    # 按 token 比例截断：保留 (max_tokens / estimated * 0.9) 比例的字符
    # 额外 0.9 系数防止估算误差导致仍超限
    keep_ratio = (max_tokens / estimated) * 0.9
    keep_chars = int(len(prompt) * keep_ratio)
    return prompt[:keep_chars] + "\n...(truncated)"


def retrive(retriever, retriever_prompt=""):
    """
    执行 RAG 检索，返回所有检索到的文档片段（合并为字符串）。

    当 similarity_top_k > 1 时，返回多个文档片段，
    用分隔符标记不同文档，让 LLM 看到更完整的知识。
    """
    if not retriever_prompt.strip():
        return "No context"

    # 安全截断，确保不超过 embedding 模型的 token 限制
    retriever_prompt = _truncate_prompt(retriever_prompt)

    try:
        response = retriever.retrieve(retriever_prompt)

        if not response:
            return "No relevant information found"

        texts = []
        for i, node in enumerate(response):
            text = node.get_text()
            if text and text.strip():
                texts.append(f"--- RAG Document {i+1} ---\n{text}")

        if not texts:
            return "No relevant information found"

        return "\n\n".join(texts)

    except Exception as e:
        print(f"检索失败: {e}")
        return "Retrieval error"
