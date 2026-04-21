import os.path
import os
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


def preload_retriever(local_engine=False, PERSIST_DIR=None, SOURCE_DIR=None):
    """
    :param local_engine:
    :param PERSIST_DIR: 该目录保存已构建好的向量索引文件
    :param SOURCE_DIR: 该目录保存用于构建向量索引的原始文本数据文件
    """
    if not local_engine:
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
        index = VectorStoreIndex.from_documents(documents, embeddings=Settings.embed_model)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)  # load the existing index
        index = load_index_from_storage(storage_context)

    retriever = index.as_retriever(similarity_top_k=1)  # 将向量索引转换成「检索器对象」，后续使用 retriever.retrieve("查询语句") 调用；指定检索时只返回「与查询语句最相似的 1 个文档片段」
    return retriever

def retrive(retriever, retriever_prompt=""):
    response = retriever.retrieve(retriever_prompt)
    response = response[0].get_text()
    return response

def retrive(retriever, retriever_prompt=""):
    # 空查询保护
    if not retriever_prompt.strip():
        return "No context"
    
    try:
        response = retriever.retrieve(retriever_prompt)

        # 空结果保护
        if not response:
            return "No relevant information found"
        
        # 安全取值
        return response[0].get_text()
    
    except Exception as e:
        # 全局异常捕获
        print(f"检索失败: {e}")
        return "Retrieval error"
    