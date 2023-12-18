from promptflow import flow, load_prompt


from hello import my_python_tool

@flow
def my_flow(text: str): 
    hello_prompt = load_prompt("hello.jinja2").format(text=text)
    llm_output = my_python_tool(
        prompt=hello_prompt,
        deployment_name="curie",
        max_tokens=120,
    )
    return llm_output


