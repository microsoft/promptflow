import os

from dotenv import load_dotenv
from openai.version import VERSION as OPENAI_VERSION

from promptflow.tracing import trace


def get_client():
    if OPENAI_VERSION.startswith("0."):
        raise Exception(
            "Please upgrade your OpenAI package to version >= 1.0.0 or using the command: pip install --upgrade openai."
        )
    api_key = os.environ.get("OPENAI_API_KEY", None)
    if api_key:
        from openai import OpenAI

        return OpenAI()
    else:
        from openai import AzureOpenAI

        return AzureOpenAI(api_version=os.environ.get("OPENAI_API_VERSION", "2023-07-01-preview"))


@trace
def my_llm_tool(prompt: str, deployment_name: str) -> str:
    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    response = get_client().chat.completions.create(
        messages=messages,
        model=deployment_name,
    )

    # get first element because prompt is single.
    return response.choices[0].message.content


if __name__ == "__main__":
    result = my_llm_tool(
        prompt="Write a simple Hello, world! python program that displays the greeting message. Output code only.",
        deployment_name="gpt-4o",
    )
    print(result)
