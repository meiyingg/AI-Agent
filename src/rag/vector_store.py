"""通用向量库封装。

- 设了 DATABASE_URL → Neon **pgvector**(langchain PGVector,永久,跨重启);
- 没设 → 本地 **Chroma**(原行为)。

对外接口两边一致:add_document / delete_document / get_retriever / search_docs / splitter。
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.models.factory import embed_model
from src.utils.config import rag_conf, abs_of
from src.utils.logger import logger
from src.utils import db


class VectorStore:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_conf["chunk_size"],
            chunk_overlap=rag_conf["chunk_overlap"],
            separators=rag_conf["separators"],
            length_function=len,
        )
        if db.USE_DB:
            from langchain_postgres import PGVector
            self.backend = "pgvector"
            self.vs = PGVector(
                embeddings=embed_model,
                collection_name=collection_name,
                connection=db.ready(),        # SQLAlchemy engine(并确保 vector 扩展已建)
                use_jsonb=True,
            )
        else:
            from langchain_chroma import Chroma
            self.backend = "chroma"
            self.vs = Chroma(
                collection_name=collection_name,
                embedding_function=embed_model,
                persist_directory=abs_of("chroma_dir"),
            )
        logger.info(f"[VectorStore:{collection_name}] backend = {self.backend}")

    def add_document(self, text: str, doc_id: str, metadata: dict = None) -> int:
        """切分一段文本并写入；用 doc_id 作为稳定 id 前缀。
        先删旧分块再写,保证同一 doc_id 重复上传时不残留旧分块(天然去重)。"""
        if not text.strip():
            return 0
        doc = Document(page_content=text, metadata={**(metadata or {}), "doc_id": doc_id})
        chunks = self.splitter.split_documents([doc])
        if not chunks:
            return 0
        ids = [f"{doc_id}-{i}" for i in range(len(chunks))]
        self.delete_document(doc_id)
        self.vs.add_documents(chunks, ids=ids)
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        """按 doc_id 删除该文档的所有分块。"""
        try:
            if self.backend == "pgvector":
                from sqlalchemy import text
                with db.get_engine().begin() as conn:
                    conn.execute(
                        text("DELETE FROM langchain_pg_embedding WHERE cmetadata->>'doc_id' = :d"),
                        {"d": doc_id},
                    )
            else:
                self.vs._collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            logger.error(f"[VectorStore:{self.collection_name}] 删除失败 doc_id={doc_id}: {e}")

    def get_retriever(self, k: int = None):
        return self.vs.as_retriever(search_kwargs={"k": k or rag_conf["top_k"]})

    def search_docs(self, query: str, k: int = None) -> list[Document]:
        try:
            return self.get_retriever(k).invoke(query)
        except Exception as e:
            logger.error(f"[VectorStore:{self.collection_name}] 检索失败: {e}")
            return []
