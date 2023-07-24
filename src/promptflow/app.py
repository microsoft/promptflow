import logging
import multiprocessing
from multiprocessing import Queue

from flask import Flask, jsonify, request

from promptflow.contracts.tool import ToolType
from promptflow.executor import FlowExecutionCoodinator
from promptflow.utils.generate_tool_meta_utils import generate_prompt_meta, generate_python_meta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

executor = FlowExecutionCoodinator.init_from_env()


@app.route("/submit_batch_request", methods=["POST"])
def submit():
    payload = request.get_json()
    result = executor.exec_request_raw(payload)
    return jsonify(result)


@app.route("/meta", methods=["POST"])
def meta():
    name = request.args.get("name", type=str)
    payload = request.get_data(as_text=True)
    tool_type = request.args.get("tool_type", type=str)
    print(tool_type)
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=generate_meta_to_queue, args=(payload, name, tool_type, q))
    p.start()
    result = q.get(timeout=1800)
    p.join()
    print(f"Result: {result}")
    print("Child process finished!")
    resp = jsonify(result)
    if "error" in result:
        resp.status_code = 500
    return resp


def generate_meta_to_queue(content, name, tool_type, queue: Queue):
    try:
        result = (
            generate_prompt_meta(name, content)
            if tool_type == ToolType.LLM
            else generate_python_meta(name, content)
            if tool_type == ToolType.PYTHON
            else generate_prompt_meta(name, content, prompt_only=True)
        )
        queue.put(result)
    except Exception as e:
        queue.put(f"Hit exception when generating meta file: {e}")


if __name__ == "__main__":
    app.run()
