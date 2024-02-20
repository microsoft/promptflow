import random
import time

from promptflow import tool
from promptflow._sdk.entities import AzureOpenAIConnection
from promptflow.tools.common import parse_chat


def get_client(connection: AzureOpenAIConnection):
    api_key = connection.api_key
    conn = dict(
        api_key=connection.api_key,
    )
    if api_key.startswith("sk-"):
        from openai import OpenAI as Client
    else:
        from openai import AzureOpenAI as Client
        conn.update(
            azure_endpoint=connection.api_base,
            api_version=connection.api_version,
        )
    return Client(**conn)


@tool
def get_synonym(
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
    connection: AzureOpenAIConnection = None,
    **kwargs,
) -> str:
    """Generates a synonym for a given word or phrase using a specified deployment.

    :param prompt: The word or phrase to generate synonyms for.
    :type prompt: str
    :param deployment_name: The custom deployment name, as specified by the user.
    :type deployment_name: str
    :param suffix: A string to append after the generated synonym, if any.
    :type suffix: str
    :param max_tokens: The maximum number of tokens to generate.
    :type max_tokens: int
    :param temperature: Controls randomness in generation. Higher values mean more randomness.
    :type temperature: float
    :param top_p: The probability mass for top tokens to consider for generation.
    :type top_p: float
    :param n: The number of synonyms to generate.
    :type n: int
    :param logprobs: The number of log probabilities to return.
    :type logprobs: int
    :param echo: Whether to include the prompt in the returned result.
    :type echo: bool
    :param stop: Tokens that signify the end of generation.
    :type stop: list
    :param presence_penalty: The penalty for token presence.
    :type presence_penalty: float
    :param frequency_penalty: The penalty for token frequency.
    :type frequency_penalty: float
    :param best_of: Controls the diversity of generated synonyms.
    :type best_of: int
    :param logit_bias: Biases for or against specific tokens.
    :type logit_bias: dict
    :param user: Identifier for the user requesting synonyms.
    :type user: str
    :param connection: The connection to Azure OpenAI.
    :type connection: AzureOpenAIConnection
    """
    messages = parse_chat(prompt)
    response = get_client(connection).chat.completions.create(
        messages=messages,
        model=deployment_name,
        max_tokens=int(max_tokens),
        temperature=float(temperature),
        top_p=float(top_p),
        n=int(n),
        # fix bug "[] is not valid under any of the given schemas-'stop'"
        stop=stop if stop else None,
        presence_penalty=float(presence_penalty),
        frequency_penalty=float(frequency_penalty),
        # Logit bias must be a dict if we passed it to openai api.
        logit_bias=logit_bias if logit_bias else {},
        user=user
    )
    return response.choices[0].message.content
