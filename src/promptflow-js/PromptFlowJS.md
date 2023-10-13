# PromptFlow.js

We will make a Javascript library PromptFlow.js. User can use it to play with PromptFlow in the browser and in Node.js.

## Browser experience

### values to use the web browser experience

1. User does not have to get runtime ready or set up local environment first. Just to install a web browser.
2. Easy to share link of a flow to another person. Open and run.

### A basic sample 

```html
<html>
  <body>
    <script src="https://some.cdn.com/promptflow.js"></script>
    <script type="module"> 
    	export const helloJinja = `
    		{# Please replace the template with your own prompt. #}
				Write a simple {{text}} program that displays the greeting message when executed.
`
    </script>
    <script src="https://some.cdn.com/openai"></script>
    <script nomodule>
    	define("hello", ["OpenAI"], function(OpenAI) {
        return function myJavaScriptAMDTool (inputs) {
          var openAIClient = new OpenAI({
            apiKey: inputs.apiKey
          });
          
          //...
        }
      });
    </script>
    <script>
    	var flowYamlString = ```
    	inputs:
        text:
          type: string
          default: Hello World!
        outputs:
          output:
            type: string
            reference: \$\{llm.output\}
      nodes:
      - name: hello_prompt
        type: prompt
        source:
          type: jinja
          root: helloJinja
        inputs:
          text: \$\{inputs.text\}
      - name: llm
        type: amd
        source:
          type: code
          amd: hello
        inputs:
        	apiKey: "my-api-key"
          prompt: \$\{hello_prompt.output\}
          deployment_name: text-davinci-003
          max_tokens: "120"
        dependencies:
          openAI  	
    	```;
      var flow = PF.Flow.fromYaml(flowYamlstring);
      var inputs = {"<flow_input_name>": "<flow_input_value>"};    
      
      flow
        .test(inputs: optitions: {})
      	.then(function(res) {
          console.log(res); // { detail: "detail json", output: "output json", log: "log text" }
      	})
      	.catch(function() {
          // error handler
        })
    </script>
  </body>
</html>

```

- ***It does not require any service behind it.***
- I do feel that using YAML is not a good idea with this pure browser inline scripts approach. Let's checkout the web ui experience.

## Web UI experience

1. PromptFlow SDK

Web UI developer needs to introduce PromptFlow JS SDK.

```html
 <script src="https://some.cdn.com/promptflow.js"></script>
```

```bash
yarn add @promptflow/core @promptflow/react
```



2. User script tools:

User's template jinja file content.

```jinja2
{# Please replace the template with your own prompt. #}
Write a simple {{text}} program that displays the greeting message when executed.
```

User's tool code in TypeScript

```typescript
import { OpenAIClient, AzureKeyCredential } from "@azure/openai";
import process from "process";
import { IJsTool } from "prompt-flow";

export interface IHelloToolInputs {
  prompt: string;
  deploymentName: string;
  suffix?: string;
  maxTokens?: number;
  temperature?: number;
  topP?: number;
  n?: number;
  logprobs?: number;
  echo?: boolean;
  stop?: string[];
  presencePenalty?: number;
  frequencyPenalty?: number;
  bestOf?: number;
  logitBias?: Record<string, number>;
  user?: string;
}

export const HelloTool: IJsTool<IHelloToolInputs, string> = async ({ deploymentName, prompt, ...others }) => {
  if (!process.env.AZURE_OPENAI_API_KEY || !process.env.AZURE_OPENAI_API_BASE) {
    throw new Error("AZURE_OPENAI_API_KEY is not set");
  }

  const openai = new OpenAIClient(process.env.AZURE_OPENAI_API_BASE, new AzureKeyCredential(process.env.AZURE_OPENAI_API_KEY));
  const { choices } = await openai.getCompletions(deploymentName, [prompt], others);

  return choices?.[0]?.text;
}
```

Use vite in node js server or browser-vite in browser: [divriots/browser-vite: Vite in the browser. (github.com)](https://github.com/divriots/browser-vite) to bundle user script tools.

3. Other 3rd party reference.

Many browsers lack of full support for ES Modules. We may need some extra UI controls to introduce the 3rd party references and it will be concat to the html.

Like CodeSandbox does:

<img src="/Users/yucongj/Library/Application Support/typora-user-images/image-20231010203027844.png" alt="image-20231010203027844" style="zoom:50%;" />

<script src="https://some.cdn.com/openai"></script>



4. Flow inputs

   ```js
   var inputs = {"<flow_input_name>": "<flow_input_value>"};   
   ```

​	WebUI reads user inputs form and generate this piece of code snippet.



5. The flow

We will use the content from flow.dag.yaml to generate it.

```js
var flowYamlString = ```
    	inputs:
        text:
          type: string
          default: Hello World!
        outputs:
          output:
            type: string
            reference: \$\{llm.output\}
      nodes:
      - name: hello_prompt
        type: prompt
        source:
          type: module
          root: helloJinja
        inputs:
          text: \$\{inputs.text\}
      - name: llm
        type: amd
        source:
          type: code
          amd: hello
        inputs:
        	apiKey: "my-api-key"
          prompt: \$\{hello_prompt.output\}
          deployment_name: text-davinci-003
          max_tokens: "120"
        environment:
          python_requirements_txt: requirements.txt   	
    	```;
var flow = PF.fromYaml(flowYamlstring);
```



6. Flow test

Our web app will run this code to perform the flow test:

```typescript
import { pfclient } from "promptflow";

const result = await pfclient.test({
  flow, 
  inputs
});


```





7. Impelementation of the "test" method.

- We may need web worker to do this. Otherwise the whole page would freeze during testing.

- Step 1: parse the flow yarm to JS objects.
- Step 2: topo-sorting
- Step 3: use js dynamic import to import tool code. Then wrap each tool code to JavaScript function.
- Step 4: pipe the function calls one by one.

8. Visualize flow test result on the WebUI page

WebUI page listens to the "onFlowDidRun" event and use the "res" object to perform the result visualization. 



## Code experience

### load flow

Get a flow instance from json/yaml strings. In the future, we may support more template engines or even DSLs.

```typescript
import { FlowDAG } from "@promptflow/core";
import flowJSONString from "path/to/flow.dag.json";
import flowYAMLString from "path/to/flow.dag.yaml";

const flowFromJSON: FlowDAG = FlowDAG.fromJSON(flowJSONString);
const flowFromYaml: FlowDAG = FlowDAG.fromYaml(flowYAMLString);

```

### DAG Visualization

#### React component to visualize flow dag.

```tsx
import { FlowDAG } from "@promptflow/core";
import { FlowGraph } from "@promptflow/react";
import * as React from "react";

export const MyComponent: React.FC = () => {
    const [flowDag, setFlowDag] = React.useState<Flow | undefined>();
    const onDagDidChange = (newValue: string) => {
        setFlow(FlowDAG.fromYaml(newValue));
    };
    
    return (
    	<div>
            <MyYamlEditor onChange={onDagDidChange} />
        	<FlowGraph flowDag={flowDag} />
        </div>
    );
}
```



#### Get raw html

```typescript
import { FlowDAG } from "@promptflow/core";
import PromptFlowDOM from "@promptflow/web";
import flowYAMLString from "path/to/flow.dag.yaml";

const flowDAG: FlowDAG = FlowDAG.fromYAML(flowYAMLString);
const htmlContent: string = PromptFlowDOM.render(flowDAG);
```

### Whole playground experience

#### React component

```tsx
import { Flow } from "@promptflow/core";
import { PlayGround } from "@promptflow/react";
import * as React from "react";

export const MyWebPage: React.FC = () => {
    
}
```

