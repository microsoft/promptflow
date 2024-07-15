import asyncio

from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ContentSafetyEvaluator
from promptflow.evals.synthetic.adversarial_simulator import AdversarialScenario, AdversarialSimulator

azure_ai_project = {
    "subscription_id": "",
    "resource_group_name": "",
    "project_name": "",
}


async def callback(
    messages: list,
    stream: bool = False,
    session_state=None,  # noqa: ANN401
    context=None,
) -> dict:
    context = None
    response_from_custom_app = {
        "answer": "I can't answer",
        "context": "",
    }
    formatted_response = {
        "content": response_from_custom_app["answer"],
        "role": "assistant",
        "context": {
            "citations": response_from_custom_app["context"],
        },
    }
    messages["messages"].append(formatted_response)
    return {"messages": messages["messages"], "stream": stream, "session_state": session_state, "context": context}


async def simulate_interaction():
    simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=DefaultAzureCredential())
    outputs = await simulator(scenario=AdversarialScenario.ADVERSARIAL_QA, max_simulation_results=3, target=callback)
    print(outputs)
    return outputs.to_eval_qa_json_lines()


async def eval_outputs(outputs):
    content_safety_evaluator = ContentSafetyEvaluator(azure_ai_project)
    result = evaluate(
        data=outputs, evaluators={"content_safety": content_safety_evaluator}, azure_ai_project=azure_ai_project
    )
    print(result)


async def orchestrate():
    outputs = await simulate_interaction()
    await eval_outputs(outputs)


asyncio.run(orchestrate())
