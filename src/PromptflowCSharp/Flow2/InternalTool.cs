using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Flow
{
    internal class InternalTool
    {
        [PromptFlow.Tool]
        public static String CallSimpleLLM(String prompt)
        {
            Console.WriteLine("Call simple internal LLM with prompt " + prompt);
            return "Internal Processed " + prompt;
        }

    }
}
