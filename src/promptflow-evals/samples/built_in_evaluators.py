from azure.identity import DefaultAzureCredential
from promptflow.evals.evaluators import groundedness
from promptflow.entities import AzureOpenAIConnection
import os

# Built-in Evaluators

# Groundedness
# Note: The model_config will be changed to type `AzureOpenAIModelConfiguration` after 
# migrated to V2 SDK from Gen AI SDK
model_config = AzureOpenAIConnection(
    name="open_ai_connection",
    api_base=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_KEY"),
    api_type="azure",
    model_name="gpt-4",
    deployment_name="gpt-4",
)

groundedness_eval = groundedness.init(model_config)
score = groundedness_eval(
    answer="The Alpine Explorer Tent is the most waterproof.", 
    context="From the our product list, the alpine explorer tent is the most waterproof. The Adventure Dining Table has higher weight."
)
print(score)
# {'gpt_groundedness': 5.0}
