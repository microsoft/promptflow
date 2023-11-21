from datetime import datetime
import time
import requests
import sys
import json
from azure.identity import AzureCliCredential
import logging
from azure.ai.ml import MLClient
from event_stream import EventStream


class ColoredFormatter(logging.Formatter):
    # Color code dictionary
    color_codes = {
        'debug': '\033[0;32m',  # Green
        'info': '\033[0;36m',  # Cyan
        'warning': '\033[0;33m',  # Yellow
        'error': '\033[0;31m',  # Red
        'critical': '\033[0;35m',  # Magenta
    }

    def format(self, record):
        # Get the original message
        message = super().format(record)

        # Add color codes
        message = f"{self.color_codes.get(record.levelname.lower(), '')}{message}\033[0m"

        return message


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def apply_delta(base: dict, delta: dict):
    for k, v in delta.items():
        if k in base:
            base[k] += v
        else:
            base[k] = v


def score(url, api_key, body, stream=True, on_event=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": ("Bearer " + api_key),
        # The azureml-model-deployment header will force the request to go to a specific deployment.
        # Remove this header to have the request observe the endpoint traffic rules
        "azureml-model-deployment": "blue",
        "Accept": "text/event-stream, application/json" if stream else "application/json"
    }

    logger.info("Sending HTTP request...")
    logger.debug("POST %s", url)
    for name, value in headers.items():
        if name == "Authorization":
            value = "[REDACTED]"
        logger.debug(f">>> {name}: {value}")
    logger.debug(json.dumps(body, indent=4, ensure_ascii=False))
    logger.debug("")

    time1 = datetime.now()
    response = None
    try:
        response = requests.post(url, json=body, headers=headers, stream=stream)
        response.raise_for_status()
    finally:
        time2 = datetime.now()
        if response is not None:
            logger.info(
                "Got response: %d %s (elapsed %s)",
                response.status_code,
                response.reason,
                time2 - time1,
            )
            for name, value in response.headers.items():
                logger.debug(f"<<< {name}: {value}")

    time1 = datetime.now()
    try:
        content_type = response.headers.get('Content-Type')
        if "text/event-stream" in content_type:
            output = {}
            event_stream = EventStream(response.iter_lines())
            for event in event_stream:
                if on_event:
                    on_event(event)

                dct = json.loads(event.data)
                apply_delta(output, dct)
            return output, True
        else:
            return response.json(), False
    finally:
        time2 = datetime.now()
        logger.info("\nResponse reading elapsed: %s", time2 - time1)


class ChatApp:
    def __init__(self, ml_client, endpoint_name, chat_input_name, chat_output_name, stream=True, debug=False):
        self._chat_input_name = chat_input_name
        self._chat_output_name = chat_output_name

        self._chat_history = []
        self._stream = stream
        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info("Getting endpoint info...")
        endpoint = ml_client.online_endpoints.get(endpoint_name)
        keys = ml_client.online_endpoints.get_keys(endpoint_name)
        self._endpoint_url = endpoint.scoring_uri
        self._endpoint_key = keys.primary_key if endpoint.auth_mode == "key" else keys.access_token

        logger.info(f"Done.")
        logger.debug(f"Target endpoint: {endpoint.id}")

    @property
    def url(self):
        return self._endpoint_url

    @property
    def api_key(self):
        return self._endpoint_key

    def get_payload(self, chat_input, chat_history=[]):
        return {
            self._chat_input_name: chat_input,
            "chat_history": chat_history,
        }

    def chat_once(self, chat_input):
        def on_event(event):
            dct = json.loads(event.data)
            answer_delta = dct.get(self._chat_output_name)
            if answer_delta:
                print(answer_delta, end='')
                # We need to flush the output
                # otherwise the text does not appear on the console
                # unless a new line comes.
                sys.stdout.flush()
                # Sleep for 20ms for better animation effects
                time.sleep(0.02)

        try:
            payload = self.get_payload(chat_input=chat_input, chat_history=self._chat_history)
            output, stream = score(self.url, self.api_key, payload, stream=self._stream, on_event=on_event)
            # We don't use self._stream here since the result may not always be the same as self._stream specified.
            if stream:
                # Print a new line at the end of the content to make sure
                # the next logger line will always starts from a new line.
                pass
                # print("\n")
            else:
                print(output.get(self._chat_output_name, "<empty>"))

            self._chat_history.append({
                "inputs": {
                    self._chat_input_name: chat_input,
                },
                "outputs": output,
            })
            logger.info("Length of chat history: %s", len(self._chat_history))
        except requests.HTTPError as e:
            logger.error(e.response.text)

    def chat(self):
        while True:
            try:
                question = input("Chat with Wikipedia:> ")
                if question in ("exit", "bye"):
                    print("Bye.")
                    break
                self.chat_once(question)
            except KeyboardInterrupt:
                # When pressed Ctrl_C, exit
                print("\nBye.")
                break
            except Exception as e:
                logger.exception("An error occurred: %s", e)
                # Do not raise the errors out so that we can continue the chat


if __name__ == "__main__":
    ml_client = MLClient(
        credential=AzureCliCredential(),
        # Replace with your subscription ID, resource group name, and workspace name
        subscription_id="<your_sub_id>",
        resource_group_name="<your_resource_group_name>",
        workspace_name="<your_workspace_name>",
    )

    chat_app = ChatApp(
        ml_client=ml_client,
        # TODO: Replace with your online endpoint name
        endpoint_name="chat-with-wikipedia-stream",
        chat_input_name="question",
        chat_output_name="answer",
        stream=False,
        debug=True,
    )

    chat_app.chat()
