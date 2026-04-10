"""
Compares captured Prompt Flow outputs against the new MAF workflow using
SimilarityEvaluator from the Azure AI Evaluation SDK.

Scores are 1–5 (5 = most similar). Rows below SIMILARITY_THRESHOLD are
flagged for manual review and the full results are saved to parity_results.csv.

Usage:
    python parity_check.py

Prerequisites:
    pip install azure-ai-evaluation pandas
    CSV format: columns 'question' and 'pf_output' (see test_inputs.csv.example)
    Optional: set MAF_WORKFLOW_FILE to your workflow file path
              (default: phase-2-rebuild/01_linear_flow.py).
"""

import asyncio
import os
from pathlib import Path
import sys

import pandas as pd
from dotenv import load_dotenv
from azure.ai.evaluation import SimilarityEvaluator

SCRIPT_DIR = Path(__file__).resolve().parent
GUIDE_ROOT = SCRIPT_DIR.parent
INPUT_CSV_PATH = SCRIPT_DIR / "test_inputs.csv"
OUTPUT_CSV_PATH = SCRIPT_DIR / "parity_results.csv"
ENV_PATH = GUIDE_ROOT / ".env"
SIMILARITY_THRESHOLD = 3.5  # Scores below this are flagged for review (scale: 1–5)

if str(GUIDE_ROOT) not in sys.path:
    sys.path.insert(0, str(GUIDE_ROOT))

from workflow_loader import load_workflow


async def run_parity_check():
    load_dotenv(dotenv_path=ENV_PATH)

    workflow = load_workflow()

    # SimilarityEvaluator requires model_config in GA (1.16+).
    model_config = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
    }

    evaluator = SimilarityEvaluator(model_config=model_config, threshold=3)

    if not INPUT_CSV_PATH.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT_CSV_PATH}\n"
            "Copy test_inputs.csv.example to test_inputs.csv and replace it with your "
            "captured Prompt Flow outputs before running parity_check.py."
        )

    test_data = pd.read_csv(INPUT_CSV_PATH)
    results = []

    for _, row in test_data.iterrows():
        question = row["question"]
        pf_answer = row["pf_output"]

        maf_result = await workflow.run(question)
        maf_answer = maf_result.get_outputs()[0]

        # evaluator() is a synchronous callable that makes network requests.
        # Wrap in asyncio.to_thread() to avoid blocking the event loop.
        # evaluator() returns {"similarity": float, "gpt_similarity": float}.
        # Use "similarity" — "gpt_similarity" is deprecated in GA.
        score_dict = await asyncio.to_thread(
            evaluator,
            query=question,
            response=maf_answer,
            ground_truth=pf_answer,
        )
        results.append({
            "question": question,
            "pf_output": pf_answer,
            "maf_output": maf_answer,
            "similarity": score_dict["similarity"],
        })

    df = pd.DataFrame(results)
    mean_score = df["similarity"].mean()
    print(f"\nMean similarity: {mean_score:.2f} / 5.0")

    regressions = df[df["similarity"] < SIMILARITY_THRESHOLD]
    if regressions.empty:
        print("All outputs meet the quality threshold. Ready for Phase 4.")
    else:
        print(f"\n{len(regressions)} answer(s) to review:")
        print(regressions[["question", "similarity"]].to_string(index=False))

    df.to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"\nFull results saved to {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    asyncio.run(run_parity_check())
