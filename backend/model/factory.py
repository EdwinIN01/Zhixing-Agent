from dotenv import load_dotenv
import os
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain.chat_models import init_chat_model
from openai import api_key

load_dotenv()

multimodal_model=init_chat_model(
    model_provider="openai",
    model="qwen3-omni-flash",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatTongyi(model="qwen-max",api_key=os.getenv("DASHSCOPE_API_KEY"))


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model="text-embedding-v3",dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"))

class VisualFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return multimodal_model


class RerankFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        from dashscope.rerank.text_rerank import TextReRank
        return TextReRank()




chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
visual_model = VisualFactory().generator()
rerank_model = RerankFactory().generator()