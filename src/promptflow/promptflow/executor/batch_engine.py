from promptflow.executor.flow_executor import FlowExecutor


class BatchEngine:
    def __init__(self, flow_executor: FlowExecutor):
        self.flow_executor = flow_executor

    def run(self):
        batch_result = self.flow_executor.exec_bulk()
        return batch_result
