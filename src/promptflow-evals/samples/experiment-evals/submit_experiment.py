import asyncio
import time
import uuid
from pathlib import Path

from promptflow._sdk._constants import ExperimentStatus
from promptflow._sdk._errors import RunOperationError
from promptflow._sdk._load_functions import load_common
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._experiment import Experiment, ExperimentTemplate


async def main():
    # outputs = await simulate_interaction()
    yaml_source_path = Path(__file__).parent / "evals-experiment.yaml"
    template = load_common(ExperimentTemplate, source=yaml_source_path)
    experiment = Experiment.from_template(template)
    client = PFClient()
    exp = client._experiments.create_or_update(experiment)
    session = str(uuid.uuid4())
    try:
        exp = client._experiments.start(exp, session=session)
    except RunOperationError:
        client._experiments.start(exp)
    while exp.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]:
        experiment = client._experiments.get(experiment.name)
        time.sleep(10)
    print(exp.status)
    for name, run in exp.runs.items():
        print(name, run.status)


if __name__ == "__main__":
    asyncio.run(main())
    print("done!")
