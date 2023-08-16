import PyPDF2
import faiss
import os

from utils.aoai import AOAIEmbedding
from utils.langchain_faiss import LangChainFaissEngine
from utils.logging import log
from utils.lock import acquire_lock


def create_faiss_index(pdf_path: str) -> str:
    index_persistent_path = ".index/" + pdf_path + ".index"
    lock_path = index_persistent_path + ".lock"
    log("Index path: " + os.path.abspath(index_persistent_path))

    chunk_size = int(os.environ.get("CHUNK_SIZE", 1024))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", 0))
    log(f"Chunk size: {chunk_size}, chunk overlap: {chunk_overlap}")

    with acquire_lock(lock_path):
        if os.path.exists(index_persistent_path):
            log("Index already exists, bypassing index creation")
            return index_persistent_path

        log("Building index")
        pdf_reader = PyPDF2.PdfReader(pdf_path)

        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()

        words = text.split()

        # Chunk the words into segments of X words with Y-word overlap, X=CHUNK_SIZE, Y=OVERLAP_SIZE
        segments = []
        for i in range(0, len(words), chunk_size - chunk_overlap):
            segment = " ".join(words[i : i + chunk_size])
            segments.append(segment)

        log(f"Number of segments: {len(segments)}")

        engine = LangChainFaissEngine(
            index=faiss.IndexFlatL2(1536), embedding=AOAIEmbedding()
        )
        engine.batch_insert_texts(segments)

        engine.save_data_index_to_disk(index_persistent_path)

        log("Index built: " + index_persistent_path)
        return index_persistent_path
