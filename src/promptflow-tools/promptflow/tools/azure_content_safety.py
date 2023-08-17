import enum
import json
from enum import Enum
from typing import Dict, List, Union

import requests

from promptflow._internal import ToolProvider, tool
from promptflow.core.tools_manager import register_builtin_method, register_builtins
from promptflow.connections import AzureContentSafetyConnection


class TextCategorySensitivity(str, Enum):
    DISABLE = "disable"
    LOW_SENSITIVITY = "low_sensitivity"
    MEDIUM_SENSITIVITY = "medium_sensitivity"
    HIGH_SENSITIVITY = "high_sensitivity"


class AzureContentSafety(ToolProvider):
    """
    Doc reference :
    https://review.learn.microsoft.com/en-us/azure/cognitive-services/content-safety/quickstart?branch=pr-en-us-233724&pivots=programming-language-rest
    """

    def __init__(self, connection: AzureContentSafetyConnection):
        self.connection = connection
        super(AzureContentSafety, self).__init__()

    @tool
    def analyze_text(
        self,
        text: str,
        hate_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
        sexual_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
        self_harm_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
        violence_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
    ):
        # Initialize the ContentSafety object
        content_safety = ContentSafety(self.connection.endpoint, self.connection.api_key, self.connection.api_version)

        # Set the media type and blocklists
        media_type = MediaType.Text
        blocklists = []

        # Detect content safety
        detection_result = content_safety.detect(media_type, text, blocklists)

        # Set the reject thresholds for each category
        reject_thresholds = {
            Category.Hate: switch_category_threshold(hate_category),
            Category.SelfHarm: switch_category_threshold(self_harm_category),
            Category.Sexual: switch_category_threshold(sexual_category),
            Category.Violence: switch_category_threshold(violence_category),
        }

        # Make a decision based on the detection result and reject thresholds
        decision_result = content_safety.make_decision(detection_result, reject_thresholds)

        return convert_decision_to_json(decision_result)


register_builtins(AzureContentSafety)


@tool
def analyze_text(
    connection: AzureContentSafetyConnection,
    text: str,
    hate_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
    sexual_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
    self_harm_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
    violence_category: TextCategorySensitivity = TextCategorySensitivity.MEDIUM_SENSITIVITY,
):
    return AzureContentSafety(connection).analyze_text(
        text=text,
        hate_category=hate_category,
        sexual_category=sexual_category,
        self_harm_category=self_harm_category,
        violence_category=violence_category,
    )


register_builtin_method(analyze_text)


def switch_category_threshold(sensitivity: TextCategorySensitivity) -> int:
    switcher = {
        TextCategorySensitivity.DISABLE: -1,
        TextCategorySensitivity.LOW_SENSITIVITY: 6,
        TextCategorySensitivity.MEDIUM_SENSITIVITY: 4,
        TextCategorySensitivity.HIGH_SENSITIVITY: 2,
    }
    return switcher.get(sensitivity, f"Non-supported sensitivity: {sensitivity}")


class MediaType(enum.Enum):
    Text = 1
    Image = 2


class Category(enum.Enum):
    Hate = 1
    SelfHarm = 2
    Sexual = 3
    Violence = 4


class Action(enum.Enum):
    Accept = "Accept"
    Reject = "Reject"


class DetectionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        """
        Exception raised when there is an error in detecting the content.

        Args:
        - code (str): The error code.
        - message (str): The error message.
        """
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"DetectionError(code={self.code}, message={self.message})"


class Decision(object):
    def __init__(self, suggested_action: Action, action_by_category: Dict[Category, Action]) -> None:
        """
        Represents the decision made by the content moderation system.

        Args:
        - suggested_action (Action): The suggested action to take.
        - action_by_category (dict[Category, Action]): The action to take for each category.
        """
        self.suggested_action = suggested_action
        self.action_by_category = action_by_category


def convert_decision_to_json(decision: Decision):
    result_json = {}
    result_json["suggested_action"] = decision.suggested_action.value
    category_json = {}
    for key, value in decision.action_by_category.items():
        category_json[key.name] = value.value
    result_json["action_by_category"] = category_json
    return result_json


class ContentSafety(object):
    def __init__(self, endpoint: str, subscription_key: str, api_version: str) -> None:
        """
        Creates a new ContentSafety instance.

        Args:
        - endpoint (str): The endpoint URL for the Content Safety API.
        - subscription_key (str): The subscription key for the Content Safety API.
        - api_version (str): The version of the Content Safety API to use.
        """
        self.endpoint = endpoint
        self.subscription_key = subscription_key
        self.api_version = api_version

    def build_url(self, media_type: MediaType) -> str:
        """
        Builds the URL for the Content Safety API based on the media type.

        Args:
        - media_type (MediaType): The type of media to analyze.

        Returns:
        - str: The URL for the Content Safety API.
        """
        if media_type == MediaType.Text:
            return f"{self.endpoint}/contentsafety/text:analyze?api-version={self.api_version}"
        elif media_type == MediaType.Image:
            return f"{self.endpoint}/contentsafety/image:analyze?api-version={self.api_version}"
        else:
            raise ValueError(f"Invalid Media Type {media_type}")

    def build_headers(self) -> Dict[str, str]:
        """
        Builds the headers for the Content Safety API request.

        Returns:
        - dict[str, str]: The headers for the Content Safety API request.
        """
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
            "ms-azure-ai-sender": "prompt_flow"
        }

    def build_request_body(
        self,
        media_type: MediaType,
        content: str,
        blocklists: List[str],
    ) -> dict:
        """
        Builds the request body for the Content Safety API request.

        Args:
        - media_type (MediaType): The type of media to analyze.
        - content (str): The content to analyze.
        - blocklists (list[str]): The blocklists to use for text analysis.

        Returns:
        - dict: The request body for the Content Safety API request.
        """
        if media_type == MediaType.Text:
            return {
                "text": content,
                "blocklistNames": blocklists,
            }
        elif media_type == MediaType.Image:
            return {"image": {"content": content}}
        else:
            raise ValueError(f"Invalid Media Type {media_type}")

    def detect(
        self,
        media_type: MediaType,
        content: str,
        blocklists: List[str] = [],
    ) -> dict:
        """
        Detects unsafe content using the Content Safety API.

        Args:
        - media_type (MediaType): The type of media to analyze.
        - content (str): The content to analyze.
        - blocklists (list[str]): The blocklists to use for text analysis.

        Returns:
        - dict: The response from the Content Safety API.
        """
        url = self.build_url(media_type)
        headers = self.build_headers()
        request_body = self.build_request_body(media_type, content, blocklists)
        payload = json.dumps(request_body)

        response = requests.post(url, headers=headers, data=payload)
        print(response.status_code)
        print(response.headers)
        print(response.text)

        res_content = response.json()

        if response.status_code != 200:
            raise DetectionError(res_content["error"]["code"], res_content["error"]["message"])

        return res_content

    def get_detect_result_by_category(self, category: Category, detect_result: dict) -> Union[int, None]:
        """
        Gets the detection result for the given category from the Content Safety API response.

        Args:
        - category (Category): The category to get the detection result for.
        - detect_result (dict): The Content Safety API response.

        Returns:
        - Union[int, None]: The detection result for the given category, or None if it is not found.
        """
        if category == Category.Hate:
            return detect_result.get("hateResult", None)
        elif category == Category.SelfHarm:
            return detect_result.get("selfHarmResult", None)
        elif category == Category.Sexual:
            return detect_result.get("sexualResult", None)
        elif category == Category.Violence:
            return detect_result.get("violenceResult", None)
        else:
            raise ValueError(f"Invalid Category {category}")

    def make_decision(
        self,
        detection_result: dict,
        reject_thresholds: Dict[Category, int],
    ) -> Decision:
        """
        Makes a decision based on the Content Safety API response and the specified reject thresholds.
        Users can customize their decision-making method.

        Args:
        - detection_result (dict): The Content Safety API response.
        - reject_thresholds (dict[Category, int]): The reject thresholds for each category.

        Returns:
        - Decision: The decision based on the Content Safety API response and the specified reject thresholds.
        """
        action_result = {}
        final_action = Action.Accept
        for category, threshold in reject_thresholds.items():
            if threshold not in (-1, 0, 2, 4, 6):
                raise ValueError("RejectThreshold can only be in (-1, 0, 2, 4, 6)")

            cate_detect_res = self.get_detect_result_by_category(category, detection_result)
            if cate_detect_res is None or "severity" not in cate_detect_res:
                raise ValueError(f"Can not find detection result for {category}")

            severity = cate_detect_res["severity"]
            action = Action.Reject if threshold != -1 and severity >= threshold else Action.Accept
            action_result[category] = action
            if action.value > final_action.value:
                final_action = action

        if (
            "blocklistsMatchResults" in detection_result
            and detection_result["blocklistsMatchResults"]
            and len(detection_result["blocklistsMatchResults"]) > 0
        ):
            final_action = Action.Reject

        print(final_action.name)
        print(action_result)

        return Decision(final_action, action_result)
