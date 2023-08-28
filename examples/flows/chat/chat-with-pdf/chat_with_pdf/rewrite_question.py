from jinja2 import Environment, FileSystemLoader
import os
from utils.logging import log
from utils.oai import OAIChat, render_with_token_limit


def rewrite_question(question: str, history: list):
    template = Environment(
        loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)))
    ).get_template("rewrite_question_prompt.md")
    token_limit = int(os.environ["PROMPT_TOKEN_LIMIT"])
    max_completion_tokens = int(os.environ["MAX_COMPLETION_TOKENS"])

    # Try to render the prompt with token limit and reduce the history count if it fails
    while True:
        try:
            prompt = render_with_token_limit(
                template, token_limit, question=question, history=history
            )
            break
        except ValueError:
            history = history[:-1]
            log(f"Reducing chat history count to {len(history)} to fit token limit")

    chat = OAIChat()
    rewritten_question = chat.generate(
        messages=[{"role": "user", "content": prompt}], max_tokens=max_completion_tokens
    )
    log(f"Rewritten question: {rewritten_question}")

    return rewritten_question
