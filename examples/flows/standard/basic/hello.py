import os
from openai.version import VERSION as OPENAI_VERSION

from dotenv import load_dotenv
from promptflow.core import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


def to_bool(value) -> bool:
    return str(value).lower() == "true"


def get_client():
    if OPENAI_VERSION.startswith("0."):
        raise Exception(
            "Please upgrade your OpenAI package to version >= 1.0.0 or using the command: pip install --upgrade openai."
        )
    api_key = os.environ["AZURE_OPENAI_API_KEY"]
    conn = dict(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    if api_key.startswith("sk-"):
        from openai import OpenAI as Client
    else:
        from openai import AzureOpenAI as Client
        conn.update(
            azure_endpoint=os.environ.get("AZURE_OPENAI_API_BASE", "azure"),
            api_version=os.environ.get("OPENAI_API_VERSION", "2023-07-01-preview"),
        )
    return Client(**conn)


@tool
def my_python_tool(
    prompt: str,
    # for AOAI, deployment name is customized by user, not model name.
    deployment_name: str,
    suffix: str = None,
    max_tokens: int = 120,
    temperature: float = 1.0,
    top_p: float = 1.0,
    n: int = 1,
    logprobs: int = None,
    echo: bool = False,
    stop: list = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    best_of: int = 1,
    logit_bias: dict = {},
    user: str = "",
    **kwargs,
) -> str:
    if "AZURE_OPENAI_API_KEY" not in os.environ or "AZURE_OPENAI_API_BASE" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    if "AZURE_OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_API_KEY")

    # TODO: remove below type conversion after client can pass json rather than string.
    echo = to_bool(echo)

    response = get_client().completions.create(
        prompt=prompt,
        model=deployment_name,
        # empty string suffix should be treated as None.
        suffix=suffix if suffix else None,
        max_tokens=int(max_tokens),
        temperature=float(temperature),
        top_p=float(top_p),
        n=int(n),
        logprobs=int(logprobs) if logprobs else None,
        echo=echo,
        # fix bug "[] is not valid under any of the given schemas-'stop'"
        stop=stop if stop else None,
        presence_penalty=float(presence_penalty),
        frequency_penalty=float(frequency_penalty),
        best_of=int(best_of),
        # Logit bias must be a dict if we passed it to openai api.
        logit_bias=logit_bias if logit_bias else {},
        user=user,
    )

    # get first element because prompt is single.
    return response.choices[0].text
