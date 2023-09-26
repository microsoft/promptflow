namespace SampleTool
{
    public class SimpleLLM
    {
        [PromptFlow.Tool]
        public static String CallSimpleLLM(String prompt)
        {
            Console.WriteLine("Call simple LLM with prompt " + prompt);
            return prompt;
        }
    }
}
