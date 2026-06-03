"""核心：高级 RAG 文档助手 (会议纪要/内部文档)。

- 入库：文件 -> SHA-256 去重(同一份不重复索引) -> 切分 -> 向量库
- 检索：混合检索(BM25+向量) -> 重排 -> TopK   (见 retriever.AdvancedRetriever)
- 生成：LCEL 链，提示词约束"只依据资料、降幻觉"
"""
import os
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from src.rag.vector_store import VectorStore
from src.rag.retriever import AdvancedRetriever, vector_only_retriever
from src.models.factory import chat_model
from src.utils.config import rag_conf, agent_conf, abs_of
from src.utils.paths import get_abs_path
from src.utils.files import list_files, read_text, sha256_of_text
from src.utils.logger import logger


class MeetingKB:
    def __init__(self):
        self.store = VectorStore(rag_conf["meeting_collection"])
        self.ledger_path = abs_of("meeting_hash_ledger")
        prompt_text = read_text(get_abs_path(agent_conf["rag_prompt_path"]))
        self.chain = PromptTemplate.from_template(prompt_text) | chat_model | StrOutputParser()
        self._retriever = None        # 懒构建并缓存高级检索器

    # ---------- 内容哈希(SHA-256)去重台账 ----------
    def _seen(self) -> set[str]:
        if not os.path.exists(self.ledger_path):
            return set()
        return {ln.strip() for ln in read_text(self.ledger_path).splitlines() if ln.strip()}

    def _mark(self, hash_hex: str):
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(hash_hex + "\n")

    def _corpus_files(self) -> list[str]:
        """语料 = 上传知识库文本(kb_dir)。检索只命中你上传的文件。"""
        kb = abs_of("kb_dir")
        return list_files(kb, (".txt", ".md")) if os.path.isdir(kb) else []

    # ---------- 入库 ----------
    def ingest(self) -> dict:
        seen = self._seen()
        new = skipped = chunks = 0
        for fp in self._corpus_files():
            content = read_text(fp)
            h = sha256_of_text(content)
            if h in seen:
                skipped += 1
                continue
            n = self.store.add_document(content, doc_id=h, metadata={"source": os.path.basename(fp)})
            self._mark(h)
            seen.add(h)
            new += 1
            chunks += n
        self._retriever = None        # 语料变了，下次重建检索器
        result = {"new": new, "skipped": skipped, "chunks": chunks}
        logger.info(f"[MeetingKB] 入库完成: {result}")
        return result

    # ---------- 构建检索器 (BM25 需要全部分块在内存) ----------
    def load_chunks(self) -> list[Document]:
        from src.utils import db
        docs = []
        if db.USE_DB:
            from src.rag.kb_service import _load_registry
            for d in _load_registry().values():
                txt = db.kv_get(f"kb_text:{d['id']}", "")
                if txt:
                    docs.append(Document(page_content=txt, metadata={"source": d.get("name", "")}))
        else:
            for fp in self._corpus_files():
                docs.append(Document(page_content=read_text(fp),
                                     metadata={"source": os.path.basename(fp)}))
        return self.store.splitter.split_documents(docs)

    def retriever(self) -> AdvancedRetriever:
        if self._retriever is None:
            self._retriever = AdvancedRetriever(self.store, self.load_chunks())
        return self._retriever

    # ---------- 问答 ----------
    def search(self, query: str) -> str:
        return self.search_with_sources(query)[0]

    def search_with_sources(self, query: str) -> tuple[str, list[str]]:
        """返回 (答案, 命中来源文件列表)，供答案溯源。"""
        docs = self.retriever().invoke(query)
        if not docs:
            return "No relevant content found in the documents.", []
        context = "\n\n".join(
            f"[Snippet {i}] source:{d.metadata.get('source', '')}\n{d.page_content}"
            for i, d in enumerate(docs, 1)
        )
        answer = self.chain.invoke({"input": query, "context": context})
        sources = list(dict.fromkeys(d.metadata.get("source", "") for d in docs if d.metadata.get("source")))
        return answer, sources


if __name__ == "__main__":
    kb = MeetingKB()
    print(kb.ingest())
    print(kb.search("跨境物流方案最后决定用什么模式"))
