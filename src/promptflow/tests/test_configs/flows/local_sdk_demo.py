import os

import promptflow as pf
from promptflow.connections import AzureOpenAIConnection
from promptflow.sdk.entities import EvalInputs, BulkInputs


def main():
    flows_dir = "."
    data_path = f"{flows_dir}/webClassification3.jsonl"
    connections = {
        "azure_open_ai_connection": AzureOpenAIConnection(
            api_key=os.environ["AOAI_API_KEY"],
            api_base=os.environ["AOAI_API_BASE"],
            api_type="azure",
            api_version="2023-03-15-preview",
        )
    }

    baseline = pf.run(flow=f"{flows_dir}/web_classification", data=BulkInputs(data_path), connections=connections)
    v1 = pf.run(flow=f"{flows_dir}/web_classification_v1", data=BulkInputs(data_path), connections=connections)
    v2 = pf.run(flow=f"{flows_dir}/web_classification_v2", data=BulkInputs(data_path), connections=connections)

    classification_accuracy_eval = pf.load_flow(
        f"{flows_dir}/classification_accuracy_evaluation"
    )

    inputs_mapping = {"groundtruth": "data.answer", "prediction": "variants.output.category"}
    baseline_accuracy_eval_input = EvalInputs(data_path, baseline.name, inputs_mapping=inputs_mapping)
    baseline_accuracy = pf.run(flow=f"{flows_dir}/classification_accuracy_evaluation", inputs=baseline_accuracy_eval_input, connections=connections)

    v1_accuracy_eval_input = EvalInputs(data_path, v1.name, inputs_mapping=inputs_mapping)
    v1_accuracy = pf.run(flow=f"{flows_dir}/classification_accuracy_evaluation", inputs=v1_accuracy_eval_input, connections=connections)

    v2_accuracy_eval_input = EvalInputs(data_path, v2.name, inputs_mapping=inputs_mapping)
    v2_accuracy = pf.run(flow=f"{flows_dir}/classification_accuracy_evaluation", inputs=v2_accuracy_eval_input, connections=connections)

    accuracy_compare = {
        "baseline": baseline_accuracy["metrics"]["accuracy"],
        "v1": v1_accuracy["metrics"]["accuracy"],
        "v2": v2_accuracy["metrics"]["accuracy"],
    }

    print(accuracy_compare)

    print(pf.show_metrics(baseline, v1, v2))

    pf.show_details(baseline, v1, v2)


if __name__ == "__main__":
    main()
