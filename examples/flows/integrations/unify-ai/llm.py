import os

from dotenv import load_dotenv
from unify import Unify

from promptflow.tracing import trace


@trace
def my_llm_tool(
    prompt: str,
    # for Unify AI, Model and Provider are to be specified by user.
    model_name: str,
    provider_name: str,
    max_tokens: int = 1200,
    temperature: float = 1.0,
) -> str:
    if "UNIFY_AI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    if "UNIFY_AI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: UNIFY_AI_API_KEY")
    messages = [{"content": prompt, "role": "system"}]
    api_key = os.environ.get("UNIFY_AI_API_KEY", None)
    unify_client = Unify(
        api_key=api_key,
        model=model_name,
        provider=provider_name,
    )
    response = unify_client.generate(
        messages=messages,
        max_tokens=int(max_tokens),
        temperature=float(temperature),
    )

    # get first element because prompt is single.
    return response


if __name__ == "__main__":
    result = my_llm_tool(
        prompt="Write a simple Hello, world! program that displays the greeting message.",
        model_name="llama-3.1-8b-chat",
        provider_name="together-ai",
    )
    print(result)
