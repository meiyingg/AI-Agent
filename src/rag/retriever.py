"""高级检索管道：混合检索 (BM25 + 向量) -> DashScope 重排。

为什么这么做：
- 纯向量检索对"型号/参数/专有名词"这类关键词召回不稳；
- BM25 补强关键词匹配，向量补强语义匹配，加权融合 (EnsembleRetriever)；
- 再用 Reranker 对融合结果二次精排，取最相关的 TopK，进一步降误召回。
"""
# langchain 1.x 把这些检索器移到了 langchain_classic；兼容旧版回退到 langchain.retrievers
try:
    from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
except ImportError:
    from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from src.utils.config import rag_conf, rerank_conf
from src.utils.logger import logger


def build_dashscope_reranker(top_n: int):
    """构造 DashScope 重排压缩器；不可用时返回 None (自动降级为不重排)。"""
    if not rerank_conf.get("enabled", True):
        return None
    try:
        from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
        return DashScopeRerank(model=rerank_conf.get("model", "gte-rerank"), top_n=top_n)
    except Exception as e:
        logger.warning(f"[retriever] DashScope 重排不可用，降级为不重排: {e}")
        return None


def vector_only_retriever(vector_store, k: int = None):
    """基线：纯向量检索 (用于评测对比)。"""
    return vector_store.get_retriever(k or rag_conf["top_k"])


class AdvancedRetriever:
    """混合检索 + 重排。.invoke(query) 返回最终 Document 列表。"""

    def __init__(self, vector_store, chunks: list[Document]):
        hybrid_k = rag_conf["hybrid_top_k"]

        # 1) 关键词检索 BM25
        bm25 = BM25Retriever.from_documents(chunks)
        bm25.k = hybrid_k

        # 2) 语义检索 (向量)
        vec = vector_store.get_retriever(hybrid_k)

        # 3) 加权融合
        self.hybrid = EnsembleRetriever(
            retrievers=[bm25, vec],
            weights=[rag_conf["bm25_weight"], rag_conf["vector_weight"]],
        )

        # 4) 重排 (可选, 失败则降级)
        reranker = build_dashscope_reranker(rerank_conf.get("top_n", rag_conf["top_k"]))
        if reranker is not None:
            self.retriever = ContextualCompressionRetriever(
                base_compressor=reranker, base_retriever=self.hybrid)
            self.mode = "hybrid+rerank"
        else:
            self.retriever = self.hybrid
            self.mode = "hybrid"
        logger.info(f"[AdvancedRetriever] 模式: {self.mode}, 语料分块数: {len(chunks)}")

    def invoke(self, query: str) -> list[Document]:
        try:
            return self.retriever.invoke(query)
        except Exception as e:
            # DashScope 重排查询时偶发返回空('NoneType.results') → 降级回混合检索, 不崩
            if self.mode == "hybrid+rerank":
                logger.warning(f"[AdvancedRetriever] 重排失败, 降级混合检索: {e}")
                try:
                    return self.hybrid.invoke(query)
                except Exception as e2:
                    logger.error(f"[AdvancedRetriever] 混合检索也失败: {e2}")
                    return []
            logger.error(f"[AdvancedRetriever] 检索失败: {e}")
            return []
