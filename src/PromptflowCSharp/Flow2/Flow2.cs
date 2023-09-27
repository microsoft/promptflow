using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;

namespace Flow
{
    public class Flow2
    {
        public class Input
        {
            public string Prompt { get; set; } = string.Empty;
        }

        public class Output
        {
            public string Out1 { get; set; } = string.Empty;
            public string Out2 { get; set; } = string.Empty;
        }


        public Flow2()
        {

        }

        [PromptFlow.Tool]
        public static String CallSimpleLLM(String prompt)
        {
            Console.WriteLine("Call simple inline LLM with prompt " + prompt);
            return prompt;
        }

        public Output Execute(Input inputs)
        {
            var out1 = CallSimpleLLM(inputs.Prompt);
            var out2 = SampleTool.SimpleLLM.CallSimpleLLM(out1 as string);
            return new Output()
            {
                Out1 = out1,
                Out2 = out2,
            };
        }
    }
}
