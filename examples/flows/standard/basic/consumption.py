from promptflow import load_flow

my_flow = load_flow(source="./flow.dag.yaml")
result = my_flow(text="Java Hello World!")



result = my_flow(text="Java Hello World!")