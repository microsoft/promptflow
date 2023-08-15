# flake8: noqa: E402

import argparse
from dotenv import load_dotenv
import os
import sys

from qna import qna
from rewrite_question import rewrite_question
from build_index import create_faiss_index
from download import download
from utils.lock import acquire_lock


def chat_with_pdf(question: str, pdf_url: str, history: list):

    with acquire_lock("create_folder.lock"):
        if not os.path.exists(".pdfs"):
            os.mkdir(".pdfs")
        if not os.path.exists(".index/.pdfs"):
            os.makedirs(".index/.pdfs")

    pdf_path = download(pdf_url)
    index_path = create_faiss_index(pdf_path)
    q = rewrite_question(question, history)
    stream, context = qna(q, index_path, history)

    return stream, context


def print_stream_and_return_full_answer(stream):
    answer = ""
    for str in stream:
        print(str, end="", flush=True)
        answer = answer + str + ""
    print(flush=True)

    return answer


def main():
    parser = argparse.ArgumentParser(description="Ask questions about a PDF file")
    parser.add_argument("url", help="URL to the PDF file")
    args = parser.parse_args()

    load_dotenv()

    history = []
    while True:
        question = input("\033[92m" + "$User (type q! to quit): " + "\033[0m")
        if question == "q!":
            break

        print("\033[92m" + "$Bot: " + "\033[0m", end=" ", flush=True)
        stream, context = chat_with_pdf(question, args.url, history)

        answer = print_stream_and_return_full_answer(stream)
        history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]


if __name__ == "__main__":
    main()
