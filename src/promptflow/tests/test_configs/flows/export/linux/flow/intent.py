import os

import pip


def extract_intent(customer_info: str, history: list, user_prompt_template: str):
    from langchain import LLMChain
    from langchain.chat_models import AzureChatOpenAI
    from langchain.prompts.chat import ChatPromptTemplate, HumanMessagePromptTemplate

    try:
        from dotenv import load_dotenv
    except ImportError:
        # This can be removed if user using custom image.
        pip.main(["install", "python-dotenv"])
        from dotenv import load_dotenv

    load_dotenv()
    chat_history_text = "\n".join(
        [message["role"] + ": " + message["content"] for message in history]
    )

    chat = AzureChatOpenAI(
        deployment_name=os.environ["CHAT_DEPLOYMENT_NAME"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        openai_api_base=os.environ["AZURE_OPENAI_API_BASE"],
        openai_api_type="azure",
        openai_api_version="2023-07-01-preview",
        temperature=0,
    )

    chat_prompt_template = ChatPromptTemplate.from_messages(
        [HumanMessagePromptTemplate.from_template(user_prompt_template)]
    )

    chain = LLMChain(llm=chat, prompt=chat_prompt_template)

    reply = chain.run(customer_info=customer_info, chat_history=chat_history_text)
    return reply


if __name__ == "__main__":
    import json

    with open("./data/denormalized-flat.jsonl", "r") as f:
        data = [json.loads(line) for line in f.readlines()]

    # only ten samples
    data = data[:10]

    # load template from file
    with open("user_intent_zero_shot.md", "r") as f:
        user_prompt_template = f.read()

    # each test
    for item in data:
        reply = extract_intent(
            item["customer_info"], item["history"], user_prompt_template
        )
        print("=====================================")
        # print("Customer info: ", item["customer_info"])
        # print("+++++++++++++++++++++++++++++++++++++")
        print("Chat history: ", item["history"])
        print("+++++++++++++++++++++++++++++++++++++")
        print(reply)
        print("+++++++++++++++++++++++++++++++++++++")
        print(f"Ground Truth: {item['intent']}")
        print("=====================================")
