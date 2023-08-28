from promptflow import PFClient
import json
import os

def test_local():
    pf = PFClient()

    file_path = os.path.dirname(os.path.abspath(__file__))

    # batch run of maths-to-code
    flow = "/".join([file_path, "../../maths-to-code"])
    data = "/".join([file_path, "../../maths-to-code/test_data/math_data.jsonl"])
   
    print("\n\n===   Running batch run of maths-to-code   ===\n")
    base_run = pf.run(
        flow = flow, 
        data = data, 
        column_mapping={"math_question": "${data.question}"},
    )

    pf.stream(base_run)

    # evaluate against the batch run and groundtruth data
    eval_flow = "/".join([file_path, "../../maths-to-code_accuracy_eval"])
    # base_run = "maths_to_code_default_20230814_172017_265375"   

    print("\n\n###   Evaluating against the batch run   ###\n")
    """
    data = "/".join([file_path, "../../maths-to-code_accuracy_eval/test_data/test.jsonl"])
    eval_run = pf.run(
        flow = eval_flow, 
        data = data, 
        column_mapping={"groundtruth": "${data.groundtruth}", "prediction": "${data.answer}"},
    )
    """

    eval_run = pf.run(
        flow = eval_flow, 
        data = data, 
        run = base_run,
        column_mapping={"groundtruth": "${data.answer}", "prediction": "${run.outputs.answer}"},
    )

    pf.stream(eval_run)

    metrics = pf.get_metrics(eval_run)
    print(json.dumps(metrics, indent=4))

if __name__ == "__main__":
    test_local()