using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace PromptFlow
{
    [System.AttributeUsage(System.AttributeTargets.Method)]
    public class ToolAttribute: System.Attribute
    {
        public ToolAttribute() { }
    }
}
