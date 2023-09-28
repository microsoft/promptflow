namespace SampleTool
{
    public class SimpleLLM
    {
        [PromptFlow.Tool]
        public static String CallSimpleLLM(String prompt)
        {
            Console.WriteLine("Call standalone simple LLM with prompt " + prompt);
            return "External Processed " + prompt;
        }
    }
}
