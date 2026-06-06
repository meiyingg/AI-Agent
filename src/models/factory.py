"""模型工厂：用工厂模式集中创建对话模型与向量化模型。

好处：全工程只在这里依赖具体厂商 (Tongyi / DashScope)。
若要换成 OpenAI 等，只改本文件，其余代码无需改动 (解耦)。
"""
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from src.utils.config import model_conf
from src.utils.usage import CostCallbackHandler


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        ...


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> BaseChatModel:
        # streaming=True：让 .stream(stream_mode="messages") 真正逐 token 吐字(打字机)；
        # 对 .invoke() 无副作用(仍返回完整消息)。
        return ChatTongyi(model=model_conf["chat_model_name"], streaming=True,
                          callbacks=[CostCallbackHandler(default_model=model_conf["chat_model_name"])])


class ReasoningModelFactory(BaseModelFactory):
    """推理模型 (qwq-plus)：流式返回 reasoning_content(原生思考链) 且支持工具调用。

    给"要展示思考过程"的 Agent 用；比 qwen-max 慢，但能看到模型真正的推理。
    """
    def generator(self) -> BaseChatModel:
        return ChatTongyi(model=model_conf["reasoning_model_name"], streaming=True,
                          callbacks=[CostCallbackHandler(default_model=model_conf["reasoning_model_name"])])


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Embeddings:
        return DashScopeEmbeddings(model=model_conf["embedding_model_name"])


# 全局单例
chat_model: BaseChatModel = ChatModelFactory().generator()
reasoning_model: BaseChatModel = ReasoningModelFactory().generator()
embed_model: Embeddings = EmbeddingsFactory().generator()
