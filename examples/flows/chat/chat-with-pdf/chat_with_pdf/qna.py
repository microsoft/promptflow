import faiss
from jinja2 import Environment, FileSystemLoader
import os
import sys

sys.path.append(os.path.dirname(__file__))
from utils.langchain_faiss import LangChainFaissEngine
from utils.aoai import AOAIEmbedding, AOAIChat, render_with_token_limit
from utils.logging import log


def qna(question: str, index_path: str, history: list):
    engine = LangChainFaissEngine(
        index=faiss.IndexFlatL2(1536), embedding=AOAIEmbedding()
    )
    engine.load_data_index_from_disk(path=index_path)
    snippets = engine.search_by_text(question, top_k=5)

    template = Environment(
        loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)))
    ).get_template("qna_prompt.md")
    token_limit = int(os.environ.get("PROMPT_TOKEN_LIMIT"))
    max_completion_tokens = int(os.environ.get("MAX_COMPLETION_TOKENS"))

    # Try to render the template with token limit and reduce snippet count if it fails
    while True:
        try:
            prompt = render_with_token_limit(
                template, token_limit, question=question, context=enumerate(snippets)
            )
            break
        except ValueError:
            snippets = snippets[:-1]
            log(f"Reducing snippet count to {len(snippets)} to fit token limit")

    chat = AOAIChat()
    stream = chat.stream(
        messages=history + [{"role": "user", "content": prompt}],
        max_tokens=max_completion_tokens,
    )
    context = [s.text for s in snippets]

    return stream, context
