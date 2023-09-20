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