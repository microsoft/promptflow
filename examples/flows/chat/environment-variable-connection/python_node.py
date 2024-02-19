
import os
from promptflow import tool
from dotenv import load_dotenv
from jinja2 import Template
from pathlib import Path
from openai import AzureOpenAI

BASE_DIR = Path(__file__).absolute().parent
def load_prompt(jinja2_template: str, question: str, chat_history: list) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        tmpl = Template(f.read(), trim_blocks=True, keep_trailing_newline=True)
        prompt = tmpl.render(question=question, chat_history=chat_history)
        return prompt

@tool
def my_python_tool(question: str, chat_history: list = []) -> str:
    # build API call from scratch using this example: https://github.com/openai/openai-python/blob/main/examples/azure.py
    prompt = load_prompt("chat.jinja2", question, chat_history)
    # if "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        # load_dotenv()
    api_version = "2023-07-01-preview"

    if "AZURE_OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_API_KEY")
    
    if "AZURE_OPENAI_ENDPOINT" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_ENDPOINT")
    
    # gets the API Key from environment variable AZURE_OPENAI_API_KEY
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )
    
    response = client.chat.completions.create(
        model="gpt-4", # The deployment name you chose when you deployed the GPT-3.5-Turbo or GPT-4 model.
        messages=[
            {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
            {"role": "user", "content": question}
        ],
        max_tokens=800
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    question = "who is the president of the united states?"
    chat_history = []
    response = my_python_tool(question, chat_history)
    print(response)
