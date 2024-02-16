import logging
import logging.config
import re
from pathlib import Path
from typing import List

import promptflow
import yaml
from openai import AzureOpenAI
from promptflow.connections import AzureOpenAIConnection
from tenacity import (
    RetryError,
    Retrying,
    after_log,
    before_sleep_log,
    stop_after_attempt,
    wait_random_exponential,
)


class Logger:
    """
    A class for setting up and getting a logger object.

    Attributes:
        config_file (str): Path to the YAML file containing the logger configuration.
        logger (logging.Logger): The logger object.
    """

    def __init__(self):
        """
        Initializes the Logger class.

        Args:
            config_file (str): Path to YAML file containing the logger configuration.
        """
        config_file = Path(__file__).parent.joinpath("log_config.yaml").resolve()
        with open(config_file, "r") as f:
            config = yaml.safe_load(f.read())
            logging.config.dictConfig(config)
        self.logger = logging.getLogger(__name__)

    def get_logger(self):
        """
        Returns the logger object.

        Returns:
            logging.Logger: The logger object.
        """
        return self.logger


logger = Logger().get_logger()


def parse_output(output: str, max: float) -> float:
    """
    Function that extracts numerical score from the beginning of string

    Args:
        output (str): String to search
        max (float): Maximum score allowed

    Returns:
        float: The extracted score
    """
    # match with either non-negative float or integer
    # if number has non-whitespace characture before that, it won't match
    matched: List[str] = re.findall(r"(?<!\S)\d+(?:\.\d+)?", output)
    if matched:
        if len(matched) == 1:
            score = float(matched[0])
            if score > max:
                raise ValueError(
                    f"Parsed number: {score} was larger than max score: {max}"
                )
        else:
            raise ValueError(
                f"More than one number detected in input. Input to parser was: {output}"
            )
    else:
        raise ValueError(
            f'No number detected in input. Input to parser was "{output}". '
        )
    return score


@promptflow.tool
def geval_summarization(
    prompt_with_src_and_gen: str,
    max_score: float,
    connection: AzureOpenAIConnection,
    deployment_name: str = "gpt-4",
) -> float:
    """Using GPT, evaluate a generated summary with respect to a source document from
    which it was generated. This function should be used for four dimensions of
    summarization evaluation inline with the SummEval benchmark: fluency, coherence,
    consistency, relevance.

    Args:
        prompt_with_src_and_gen (str): The prompt containing the source document and generated summary.
        max_score (float): The maximum score allowed.
        connection (AzureOpenAIConnection): The connection object for Azure OpenAI.
        deployment_name (str, optional): The name of the deployment. Defaults to "gpt-4".

    Returns:
        float: The evaluation score
    """
    # make sure you use the same api version/model with the one used for meta evaluation
    logger.info(
        f"OpenAI API Base: {connection.api_base} - Version: {connection.api_version}"
        f" - Deployment: {deployment_name}"
    )
    client = AzureOpenAI(
        azure_endpoint=connection.api_base,
        api_version=connection.api_version,
        api_key=connection.api_key,
    )

    message = {"role": "system", "content": prompt_with_src_and_gen}
    try:
        for attempt in Retrying(
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.INFO),
            after=after_log(logger, logging.INFO),
            wait=wait_random_exponential(multiplier=1, min=1, max=120),
            stop=stop_after_attempt(10),
        ):
            with attempt:
                response = client.chat.completions.create(
                    model=deployment_name,
                    messages=[message],
                    temperature=2,
                    max_tokens=5,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stop=None,
                    n=20,
                )
    except RetryError:
        logger.exception(f"geval openai call failed\nInput prompt was: {message}")
        raise

    all_responses = []
    for i in range(len(response.choices)):
        try:
            content = response.choices[i].message.content
            all_responses.append(content)
        except KeyError:
            # `content` won't exist in returned json when openai content_filter is triggered
            logger.exception(
                f"""data with key missing was: {response.choices[i]}\nInput prompt was: {message}"""
            )

    return aggregate_llm_scores(all_responses, max_score=max_score)


def aggregate_llm_scores(llm_responses: List[str], max_score: int) -> float:
    """Parse and average valid scores from the generated responses of
    the G-Eval LLM call.

    Args:
        llm_responses (List[str]): List of scores from multiple LLMs
        max_score (float): The maximum score allowed.

    Returns:
        float: The average of all the valid scores
    """
    all_scores = []
    error_count = 0
    for generated in llm_responses:
        try:
            parsed = parse_output(generated, max_score)
            all_scores.append(parsed)
        except ValueError as e:
            logger.warning(e)
            error_count += 1
    if error_count:
        logger.warning(
            f"{error_count} out of 20 scores were discarded due to corrupt g-eval generation"
        )
    score = sum(all_scores) / len(all_scores)
    return score
