import requests
import time
import traceback
import uuid

from promptflow.connections import CustomConnection
from promptflow.core.tool import ToolProvider, tool
from promptflow.core.tools_manager import register_builtins

debug = False


class AzureFormRecognizer(ToolProvider):
    """
    Doc reference :
    https://learn.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/quickstarts/get-started-sdks-rest-api?view=form-recog-3.0.0&preserve-view=true&pivots=programming-language-rest-api
    """

    def __init__(self, connection: CustomConnection):
        super().__init__()
        self.api_endpoint = connection.api_endpoint
        self.api_key = connection.api_key
        self.api_version = connection.api_version

    def pool_result(self, operation_url, headers, max_retry=100):
        traceId = headers["X-ClientTraceId"]
        for _ in range(max_retry):
            request = requests.get(operation_url, headers=headers)
            if request.status_code != 200:
                raise ValueError(f"Invalid response status {request.status_code} for {operation_url}")

            result = request.json()
            status = result["status"]
            if status == "succeeded":
                return result["analyzeResult"]
            elif status in ["running", "notStarted"]:
                print(f"{traceId} Waiting...")
                time.sleep(1)
            else:
                raise ValueError(f"Invalid operation status {status} for {operation_url}")

        raise RuntimeError("Max retry reached")

    @tool
    def analyze_document(self, document_url: str, model_id="prebuilt-layout"):
        traceId = str(uuid.uuid4())
        try:
            print(f"{traceId}: Analyze document")
            path = f"/formrecognizer/documentModels/{model_id}:analyze?api-version={self.api_version}"
            constructed_url = self.api_endpoint + path
            if debug:
                print(f"{traceId} {constructed_url}")

            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-type": "application/json",
                "X-ClientTraceId": traceId,
            }
            if debug:
                print(f"{traceId} {headers}")

            body = {"urlSource": document_url}
            request = requests.post(constructed_url, headers=headers, json=body)
            if request.status_code != 202:
                raise ValueError(f"Error {request.status_code}")

            if debug:
                print(f"{traceId} {request.headers}")

            operation_url = request.headers["Operation-Location"]
            result = self.pool_result(operation_url, headers)
            return result
        except Exception:
            error_msg = traceback.format_exc()
            return f"{traceId} Exception {error_msg}"


register_builtins(AzureFormRecognizer)
