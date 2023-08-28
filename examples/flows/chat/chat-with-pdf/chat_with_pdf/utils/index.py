import os
from typing import Iterable, List, Optional
from dataclasses import dataclass
from faiss import Index
import faiss
import pickle
import numpy as np

from .oai import OAIEmbedding as Embedding


@dataclass
class SearchResultEntity:
    text: str = None
    vector: List[float] = None
    score: float = None
    original_entity: dict = None
    metadata: dict = None


INDEX_FILE_NAME = "index.faiss"
DATA_FILE_NAME = "index.pkl"


class FAISSIndex:
    def __init__(self, index: Index, embedding: Embedding) -> None:
        self.index = index
        self.docs = {}  # id -> doc, doc is (text, metadata)
        self.embedding = embedding

    def insert_batch(
        self, texts: Iterable[str], metadatas: Optional[List[dict]] = None
    ) -> None:
        documents = []
        vectors = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas else {}
            vector = self.embedding.generate(text)
            documents.append((text, metadata))
            vectors.append(vector)

        self.index.add(np.array(vectors, dtype=np.float32))
        self.docs.update(
            {i: doc for i, doc in enumerate(documents, start=len(self.docs))}
        )

        pass

    def query(self, text: str, top_k: int = 10) -> List[SearchResultEntity]:
        vector = self.embedding.generate(text)
        scores, indices = self.index.search(np.array([vector], dtype=np.float32), top_k)
        docs = []
        for j, i in enumerate(indices[0]):
            if i == -1:  # This happens when not enough docs are returned.
                continue
            doc = self.docs[i]
            docs.append(
                SearchResultEntity(text=doc[0], metadata=doc[1], score=scores[0][j])
            )
        return docs

    def save(self, path: str) -> None:
        faiss.write_index(self.index, os.path.join(path, INDEX_FILE_NAME))
        # dump docs to pickle file
        with open(os.path.join(path, DATA_FILE_NAME), "wb") as f:
            pickle.dump(self.docs, f)
        pass

    def load(self, path: str) -> None:
        self.index = faiss.read_index(os.path.join(path, INDEX_FILE_NAME))
        with open(os.path.join(path, DATA_FILE_NAME), "rb") as f:
            self.docs = pickle.load(f)
        pass
