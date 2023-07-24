import json
from datetime import datetime
from typing import List

import requests

from promptflow.runtime.utils import FORMATTER, get_logger

logger = get_logger("prt", std_out=True, log_formatter=FORMATTER)


def _score(inputs: List[dict] = None, input_file: str = None, url: str = "http://localhost:8080"):
    if inputs:
        inputs = {k: v for input_dict in inputs for k, v in input_dict.items()}
    if input_file:
        # If provide input file, read inputs dict from it.
        inputs = json.loads(open(input_file, "r").read())
    client = PromptScoreClient(url)
    result = client.score(inputs)
    logger.info(f"Receive score result: {result!r}")

    return result


class PromptScoreClient:
    """PromptFlowRuntimeClient is a client to submit a flow to a running promptflow runtime."""

    def __init__(self, url: str):
        url = url.replace("/score", "").strip("/")
        self.url = url
        self.timeout = 180

    def score(self, request):
        """submit a flow to a running promptflow runtime."""
        start = datetime.now()
        request_url = f"{self.url}/score"
        resp = requests.post(request_url, json=request, headers={}, timeout=self.timeout)

        end = datetime.now()
        if resp.status_code != 200:
            logger.info("Error: %s %s", resp.status_code, resp.text)
            raise Exception(f"Http response got {resp.status_code}")
        result = resp.json()
        logger.info("Http response got 200, from %s, in %s", request_url, end - start)
        return result

    def health(self):
        """check if the runtime is alive"""
        resp = requests.get(f"{self.url}/health", headers={}, timeout=self.timeout)
        return resp.json()
