namespace Flow1
{
    public class SimpleInternalLLMTool
    {
        [PromptFlow.Tool]
        public static String CallSimpleLLM(String prompt)
        {
            Console.WriteLine("Call simple LLM with prompt " + prompt);
            return $"Processed {prompt}";
        }
    }
}
