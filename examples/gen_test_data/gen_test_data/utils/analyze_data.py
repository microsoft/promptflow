import json
from argparse import ArgumentParser
from pathlib import Path


def analyze_batch_run_res(file_path):
    gen_success_count = 0
    gen_failure_count = 0
    run_failed_count = 0
    gen_failure_steps = {}
    gen_failure_reasons = {}

    with open(file_path, "r") as f:
        for line in f:
            data = json.loads(line)

            if data["debug_info"] == "(Failed)":
                run_failed_count += 1
                continue

            if data["debug_info"]["generation_summary"]["success"]:
                gen_success_count += 1
            else:
                gen_failure_count += 1
                failed_step = data["debug_info"]["generation_summary"]["failed_step"]
                failed_reason = data["debug_info"]["generation_summary"]["failed_reason"]

                if failed_step in gen_failure_steps:
                    gen_failure_steps[failed_step] += 1
                    gen_failure_reasons[failed_step].append(failed_reason)
                else:
                    gen_failure_steps[failed_step] = 1
                    gen_failure_reasons[failed_step] = [failed_reason]

    print(f"Gen success count: {gen_success_count}")
    print(f"Gen failure count: {gen_failure_count}")
    print(f"Run failure count: {run_failed_count}")
    print("Gen failures by step:")
    for step, count in gen_failure_steps.items():
        print(f"{step}: {count}")
    print("**Gen failures by reason:")
    for step, reasons in gen_failure_reasons.items():
        print(f"{step}: {reasons}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--jsonl_file", type=Path, required=True)
    args = parser.parse_args()
    analyze_batch_run_res(args.jsonl_file)
