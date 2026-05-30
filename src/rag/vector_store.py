"""通用向量库封装 (Chroma)。

一个进程内可建多个集合 (collection)：
- meetings   : 内部会议纪要
- web_intel  : 在线检索回来的行业情报
两个集合存在同一个 chroma 目录，但互不干扰。
"""
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.models.factory import embed_model
from src.utils.config import rag_conf, abs_of
from src.utils.logger import logger


class VectorStore:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.vs = Chroma(
            collection_name=collection_name,
            embedding_function=embed_model,
            persist_directory=abs_of("chroma_dir"),
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_conf["chunk_size"],
            chunk_overlap=rag_conf["chunk_overlap"],
            separators=rag_conf["separators"],
            length_function=len,
        )

    def add_document(self, text: str, doc_id: str, metadata: dict = None) -> int:
        """切分一段文本并写入；用 doc_id 作为稳定 id 前缀，
        重复 add 同一个 doc_id 会覆盖旧分块 (天然按 id 去重)。"""
        if not text.strip():
            return 0
        doc = Document(page_content=text, metadata={**(metadata or {}), "doc_id": doc_id})
        chunks = self.splitter.split_documents([doc])
        if not chunks:
            return 0
        ids = [f"{doc_id}-{i}" for i in range(len(chunks))]
        self.vs.add_documents(chunks, ids=ids)
        return len(chunks)

    def get_retriever(self, k: int = None):
        return self.vs.as_retriever(search_kwargs={"k": k or rag_conf["top_k"]})

    def search_docs(self, query: str, k: int = None) -> list[Document]:
        try:
            return self.get_retriever(k).invoke(query)
        except Exception as e:
            logger.error(f"[VectorStore:{self.collection_name}] 检索失败: {e}")
            return []
