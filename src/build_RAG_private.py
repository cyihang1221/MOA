import os
import os.path

from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)


def _create_embed_model(local_engine: bool = False):
    """按配置延迟加载嵌入模型，避免在 DashScope/OpenAI 模式下导入 torch/transformers。"""
    if local_engine:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        return HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

    model_type = (os.getenv("LLM_MODEL_TYPE") or "").strip().lower()
    if model_type == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(api_key=os.getenv("LLM_API_KEY"))
    if model_type == "dashscope":
        from llama_index.embeddings.dashscope import DashScopeEmbedding

        return DashScopeEmbedding(api_key=os.getenv("LLM_API_KEY"))

    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


def preload_retriever(local_engine=False, PERSIST_DIR=None, SOURCE_DIR=None):
    """
    :param local_engine: 为 True 时强制使用本地 HuggingFace 嵌入
    :param PERSIST_DIR: 已构建向量索引目录
    :param SOURCE_DIR: 原始文本数据目录
    """
    Settings.embed_model = _create_embed_model(local_engine=local_engine)

    if not os.path.exists(PERSIST_DIR):
        documents = SimpleDirectoryReader(SOURCE_DIR).load_data()
        index = VectorStoreIndex.from_documents(documents, embeddings=Settings.embed_model)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)

    return index.as_retriever(similarity_top_k=1)


def _sanitize_embed_query(text: str, max_len: int = 2000) -> str:
    """DashScope 嵌入要求长度在 [1, 2048]；过长或为空会导致 API 失败。"""
    cleaned = (text or "").strip()
    if not cleaned:
        cleaned = "metabolomics mass spectrometry data analysis"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def format_history_for_rag(history_summary, max_len: int = 1200) -> str:
    if not history_summary:
        return "none"
    import json

    try:
        text = json.dumps(history_summary, ensure_ascii=False, default=str)
    except TypeError:
        text = str(history_summary)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def retrive(retriever, retriever_prompt=""):
    query = _sanitize_embed_query(retriever_prompt)

    try:
        response = retriever.retrieve(query)
        if not response:
            return "No relevant information found"
        return response[0].get_text()
    except Exception as e:
        print(f"检索失败: {e}")
        return "Retrieval error"
