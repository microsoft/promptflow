import os
from typing import Iterable, List, Optional, Tuple
from dataclasses import dataclass, asdict

from faiss import Index
from langchain import FAISS
from langchain.docstore.in_memory import InMemoryDocstore
from langchain.embeddings.base import Embeddings
from langchain.docstore.document import Document

from .aoai import AOAIEmbedding as Embedding


@dataclass
class SearchResultEntity:
    text: str = None
    vector: List[float] = None
    score: float = None
    original_entity: dict = None
    metadata: dict = None

    def as_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(dict_object: dict):
        return SearchResultEntity(**dict_object)


INDEX_FILE_NAME = "index.faiss"
DATA_FILE_NAME = "index.pkl"


class LangchainEmbedding(Embeddings):
    def __init__(self, embedding: Embedding):
        self.__embedding = embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return []

    def embed_query(self, text: str) -> List[float]:
        return self.__embedding.embed(text)


class LangChainFaissEngine:
    def __init__(self, index: Index, embedding: Embedding):
        self.__index = index
        self.__embedding = embedding
        self.__init_langchain_faiss()

    def batch_insert_texts(
        self, texts: Iterable[str], metadatas: Optional[List[dict]] = None
    ) -> None:
        self.__langchain_faiss.add_texts(texts, metadatas)

    def batch_insert_texts_with_embeddings(
        self,
        texts: Iterable[str],
        embeddings: Iterable[List[float]],
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        if len(texts) != len(embeddings):
            raise ValueError("numbers of texts and embeddings do not match")
        count = len(embeddings)
        text_embeddings = [(texts[i], embeddings[i]) for i in range(count)]
        self.__langchain_faiss.add_embeddings(text_embeddings, metadatas)

    def search_by_text(
        self, query_text: str, top_k: int = 5
    ) -> List[SearchResultEntity]:
        query_embedding = self.__embedding.generate(query_text)
        return self.search_by_embedding(query_embedding, top_k)

    def search_by_embedding(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[SearchResultEntity]:
        index_dimension = self.__langchain_faiss.index.d
        if len(query_embedding) != index_dimension:
            raise ValueError(
                f"query embedding dimension {len(query_embedding)}"
                f" does not match index dimension {index_dimension}"
            )
        docs = self.__langchain_faiss.similarity_search_with_score_by_vector(
            query_embedding, top_k
        )
        return self.__parse_docs(docs)

    def clear(self):
        self.__init_langchain_faiss()

    def merge_from(self, other_engine):
        self.__langchain_faiss.merge_from(other_engine.__langchain_faiss)

    def load_data_index_from_disk(self, path: str):
        index_file = os.path.join(path, INDEX_FILE_NAME)
        data_file = os.path.join(path, DATA_FILE_NAME)

        if (not os.path.exists(index_file)) and (not os.path.exists(data_file)):
            self.__init_langchain_faiss()
        else:
            self.__langchain_faiss = FAISS.load_local(
                path, LangchainEmbedding(self.__embedding)
            )

    def save_data_index_to_disk(self, path: str):
        self.__langchain_faiss.save_local(path)

    def get_store_files_size(self, path: str) -> int:
        index_file = os.path.join(path, INDEX_FILE_NAME)
        data_file = os.path.join(path, DATA_FILE_NAME)
        return os.path.getsize(index_file) + os.path.getsize(data_file)

    @staticmethod
    def get_index_file_relative_path():
        return INDEX_FILE_NAME

    @staticmethod
    def get_data_file_relative_path():
        return DATA_FILE_NAME

    def __init_langchain_faiss(self) -> FAISS:
        self.__index.reset()
        self.__langchain_faiss = FAISS(
            self.__embedding.generate, self.__index, InMemoryDocstore({}), {}
        )

    @staticmethod
    def __parse_docs(docs: List[Tuple[Document, float]]) -> List[SearchResultEntity]:
        res = [
            SearchResultEntity(
                text=item[0].page_content,
                metadata=item[0].metadata,
                score=float(item[1]),
            )
            for item in docs
        ]
        return res
