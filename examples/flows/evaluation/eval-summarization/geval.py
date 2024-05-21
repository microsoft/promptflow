import logging
import logging.config
import math
from pathlib import Path
from typing import List, Tuple

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


def compute_weighted_score_over_probs(
    top_probs: List[Tuple[str, float]],
    expected_scores: List[str] = ["1", "2", "3", "4", "5"],
) -> float:
    """
    Computes the weighted score over probability of number tokens.
    number tokens defined in `expected_scores` are selected from `top_probs`
     and their probabilities are normalized for sum of probabilities to be 1
     and weighted score is calculated by multiplying the number token with its normalized probability.

    Args:
        top_probs (List[Tuple[str, float]]): A list of token, probability pairs.
        expected_scores (List[str], optional): A list of expected scores. Defaults to ["1", "2", "3", "4", "5"].

    Returns:
        float: The weighted score computed from the probability-score pairs.

    Raises:
        ValueError: If no expected scores are found in the top_probs list.
    """
    filtered_score_probs = [
        (token, prob) for token, prob in top_probs if token in expected_scores
    ]
    if not filtered_score_probs:
        raise ValueError(
            f"No expected scores {expected_scores} found in top_probs: {top_probs}"
        )
    total_probs = sum(prob for _, prob in filtered_score_probs)
    normalized_probs = [
        (token, prob / total_probs) for token, prob in filtered_score_probs
    ]
    weighted_score = sum(int(token) * prob for token, prob in normalized_probs)
    return weighted_score


@promptflow.tool
def geval_summarization(
    prompt_with_src_and_gen: str,
    connection: AzureOpenAIConnection,
    deployment_name: str = "gpt-4-turbo",
) -> float:
    """Using GPT, evaluate a generated summary with respect to a source document from
    which it was generated. This function should be used for four dimensions of
    summarization evaluation inline with the SummEval benchmark: fluency, coherence,
    consistency, relevance.

    Args:
        prompt_with_src_and_gen (str): The prompt containing the source document and generated summary.
        connection (AzureOpenAIConnection): The connection object for Azure OpenAI.
        deployment_name (str, optional): The name of the deployment. Defaults to "gpt-4-turbo".

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
                    temperature=0,
                    max_tokens=5,
                    logprobs=True,
                    top_logprobs=5,
                    frequency_penalty=0,
                    presence_penalty=0,
                    n=1,
                )
    except RetryError:
        logger.exception(f"geval openai call failed\nInput prompt was: {message}")
        raise

    top_logprobs = response.choices[0].logprobs.content[0].top_logprobs
    top_probs = [
        (top_logprob.token, math.exp(top_logprob.logprob))
        for top_logprob in top_logprobs
    ]
    try:
        weighted_score = compute_weighted_score_over_probs(top_probs)
    except ValueError:
        logger.exception(f"geval openai call failed\nInput prompt was: {message}")
        raise

    return weighted_score
