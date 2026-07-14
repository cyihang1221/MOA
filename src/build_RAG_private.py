# 领域知识检索增强  RAG 检索器      知识库构建
# 使用 LlamaIndex 将代谢组学软件文档/论文（softwares_database/）构建为向量索引
# 支持多种 Embedding 后端：OpenAI、阿里 DashScope、HuggingFace (BAAI/bge-small-en-v1.5)
# 索引持久化到 softwares_database_RAG/，避免重复构建
# 每次检索返回相似度最高的 1 个文档片段

import os.path
import os
from llama_index.core import (
    VectorStoreIndex,   # 用于创建和管理向量索引的核心类
    SimpleDirectoryReader,  # 用于从指定目录加载文档数据的读取器
    StorageContext, # 用于管理索引的持久化存储上下文
    load_index_from_storage,    # 用于从持久化存储中加载现有索引的函数
    Settings    # 用于配置全局设置（如嵌入模型）的对象
)

# 导入不同提供商的嵌入（Embedding）模型类，用于将文本转换为向量。
from llama_index.embeddings.openai import OpenAIEmbedding           # OpenAI
from llama_index.embeddings.dashscope import DashScopeEmbedding     # 阿里云百炼平台（DashScope）
from llama_index.embeddings.huggingface import HuggingFaceEmbedding # Hugging Face


def preload_retriever(local_engine=False, PERSIST_DIR=None, SOURCE_DIR=None):
# 用于预加载或创建一个检索器对象

    """
    :param local_engine: 是否使用本地模型
    :param PERSIST_DIR: 该目录保存已构建好的向量索引文件
    :param SOURCE_DIR: 该目录保存用于构建向量索引的原始文本数据文件
    """

    if not local_engine:    # 则使用云端模型 三选一
        if os.getenv("LLM_MODEL_TYPE") == "openai":
            Settings.embed_model = OpenAIEmbedding(api_key=os.getenv("LLM_API_KEY"))  # 配置全局的 Settings.embed_model 为 OpenAI 的嵌入模型
        elif os.getenv("LLM_MODEL_TYPE") == "DashScope":
            Settings.embed_model = DashScopeEmbedding(api_key=os.getenv("LLM_API_KEY"))
        else:
            Settings.embed_model = HuggingFaceEmbedding(  
                model_name="BAAI/bge-small-en-v1.5"  # 使用本地模型时，配置嵌入模型为 HuggingFace 上的开源模型
            )  # 首次运行时，HuggingFaceEmbedding 会自动从 HuggingFaceHub 下载模型文件保存到本地缓存目录（默认 ~/.cache/huggingface/），后续运行时直接加载本地缓存的模型文件

    if not os.path.exists(PERSIST_DIR):  # 检查索引文件是否存在，避免重复创建索引文件
        documents = SimpleDirectoryReader(SOURCE_DIR).load_data()  # load the documents and create the index

        # 使用加载的文档和配置好的嵌入模型创建一个 VectorStoreIndex 对象。
        # 这一步会将文档切分并转换为向量存储在内存中。
        index = VectorStoreIndex.from_documents(documents, embeddings=Settings.embed_model)

        # 将创建好的索引对象持久化保存到 PERSIST_DIR 目录中
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        # 如果 PERSIST_DIR 已存在，说明索引已构建。
        # 则创建一个 StorageContext 并从该上下文中加载现有的索引。
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)  # load the existing index
        index = load_index_from_storage(storage_context)

    # 将向量索引转换成「检索器对象」，后续使用 retriever.retrieve("查询语句") 调用
    # 检索多个文档片段以确保 LLM 能看到完整的分析管道（如冗余特征过滤 + 分子网络等所有阶段）
    retriever = index.as_retriever(similarity_top_k=5)  
    
    return retriever    #返回配置好的检索器对象

def retrive(retriever, retriever_prompt=""):
    """执行 RAG 检索操作，返回所有检索到的文档片段（合并为一个字符串）。

    与 similarity_top_k 配合：top_k=5 时最多返回 5 个文档片段。
    返回多个文档能让 LLM 看到完整的分析管道（预处理 → 冗余过滤 → 统计 → 分子网络等），
    从而生成覆盖所有阶段的完整计划。
    """
    if not retriever_prompt.strip():
        return "No context"

    try:
        response = retriever.retrieve(retriever_prompt)

        if not response:
            return "No relevant information found"

        # 返回所有检索到的文档片段，用分隔符标记不同文档
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
    