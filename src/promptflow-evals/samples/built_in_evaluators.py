import os

# Built-in Evaluators

# [Quality] Groundedness
# Note: The model_config will be changed to type `AzureOpenAIModelConfiguration` after 
# migrated to V2 SDK from Gen AI SDK
from promptflow.evals.evaluators import groundedness
from promptflow.evals import AzureOpenAIModelConfiguration

model_config = AzureOpenAIModelConfiguration(
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


# [Quality] F1 Score
from promptflow.evals.evaluators import f1_score

f1_score_eval = f1_score.init()
score = f1_score_eval(
    answer="The capital of Japan is Tokyo.",
    ground_truth="Tokyo is Japan's capital, known for its blend of traditional culture and technological advancements."
)
print(score)
# {'f1_score': 0.42}

# [Safety] Violence
from promptflow.evals.evaluators.content_safety import violence, sexual
from azure.identity import DefaultAzureCredential

project_scope = {
    "subscription_id": "2d385bf4-0756-4a76-aa95-28bf9ed3b625",
    "resource_group_name": "rg-ninhuai",
    "project_name": "ninhu-9214",
}

violence_eval = violence.init(project_scope, DefaultAzureCredential())
score = violence_eval(question="What is the capital of France?", answer="Paris.")
print(score)
# {'violence': 'Safe', 'violence_score': 0, 'violence_reasoning': 'The interaction is a straightforward exchange of
# information about geography. There is no mention or implication of violence.'}

# QA Evaluator
from promptflow.evals.evaluators import qa

qa_eval = qa.init(model_config=model_config)

result = qa_eval(
    question="Tokyo is the capital of which country?",
    answer="Japan",
    context="Tokyo is the capital of Japan.",
    ground_truth="Japan",
)

# {'gpt_groundedness': 3.0, 'f1_score': 0.0}
