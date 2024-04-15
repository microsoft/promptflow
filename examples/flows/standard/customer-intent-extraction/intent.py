import os
import pip
from langchain.chat_models import AzureChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.prompts.prompt import PromptTemplate
from langchain.schema import HumanMessage


def extract_intent(chat_prompt: str):
    if (
        "AZURE_OPENAI_API_KEY" not in os.environ
        or "AZURE_OPENAI_API_BASE" not in os.environ
    ):
        # load environment variables from .env file
        try:
            from dotenv import load_dotenv
        except ImportError:
            # This can be removed if user using custom image.
            pip.main(["install", "python-dotenv"])
            from dotenv import load_dotenv

        load_dotenv()

    # AZURE_OPENAI_ENDPOINT conflict with AZURE_OPENAI_API_BASE when use with langchain
    if "AZURE_OPENAI_ENDPOINT" in os.environ:
        os.environ.pop("AZURE_OPENAI_ENDPOINT")
    chat = AzureChatOpenAI(
        deployment_name=os.environ.get("CHAT_DEPLOYMENT_NAME", "gpt-35-turbo"),
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        openai_api_base=os.environ["AZURE_OPENAI_API_BASE"],
        openai_api_type="azure",
        openai_api_version="2023-07-01-preview",
        temperature=0,
    )
    reply_message = chat([HumanMessage(content=chat_prompt)])
    return reply_message.content


def generate_prompt(customer_info: str, history: list, user_prompt_template: str):

    chat_history_text = "\n".join(
        [message["role"] + ": " + message["content"] for message in history]
    )

    prompt_template = PromptTemplate.from_template(user_prompt_template)
    chat_prompt_template = ChatPromptTemplate.from_messages(
        [HumanMessagePromptTemplate(prompt=prompt_template)]
    )
    return chat_prompt_template.format_prompt(
        customer_info=customer_info, chat_history=chat_history_text
    ).to_string()


if __name__ == "__main__":
    import json

    with open("./data/denormalized-flat.jsonl", "r") as f:
        data = [json.loads(line) for line in f.readlines()]

    # only ten samples
    data = data[:10]

    # load template from file
    with open("user_intent_zero_shot.jinja2", "r") as f:
        user_prompt_template = f.read()

    # each test
    for item in data:
        chat_prompt = generate_prompt(
            item["customer_info"], item["history"], user_prompt_template
        )
        reply = extract_intent(chat_prompt)
        print("=====================================")
        # print("Customer info: ", item["customer_info"])
        # print("+++++++++++++++++++++++++++++++++++++")
        print("Chat history: ", item["history"])
        print("+++++++++++++++++++++++++++++++++++++")
        print(reply)
        print("+++++++++++++++++++++++++++++++++++++")
        print(f"Ground Truth: {item['intent']}")
        print("=====================================")
