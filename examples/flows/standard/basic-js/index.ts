import { Flow, NodeType, InputOrOutputType } from "prompt-flow";

export const basicFlow: Flow = new Flow({ path: "./flow.dag.yaml" });

// another non-yaml proposal

export const basicFlow2: Flow = new Flow()
  .withInput({
    type: InputOrOutputType.string,
    default: "Hello, world!",
    name: "text",
  })
  .withOutput({
    type: InputOrOutputType.string,
    name: "output",
    reference: "${llm.output}",
  })
  .withNode({
    type: NodeType.prompt,
    path: "./hello.jinja2",
    name: "prompt",
    inputs: {
      text: "${inputs.text}",
    },
  })
  .withNode({
    type: NodeType.jsTool,
    path: "./hello.ts",
    name: "hello",
    inputs: {
      prompt: "${hello_prompt.output}",
      deployment_name: "text-davinci-003",
      max_tokens: "120",
    },
  });