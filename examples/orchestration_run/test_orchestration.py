from pathlib import Path

from promptflow import PFClient
from promptflow._sdk._load_functions import load_orchestration

orchestration = load_orchestration(source=Path(__file__).parent / "orchestrate_basic.yaml")
client = PFClient()
# results = client.test(flow=orchestration, inputs={
#     "url": "https://www.youtube.com/watch?v=kYqRtjDBci8", "answer": "Channel",
#     "evidence": "Both"})
results = client.run(name="my_orchestration_run26", flow=orchestration)
results
