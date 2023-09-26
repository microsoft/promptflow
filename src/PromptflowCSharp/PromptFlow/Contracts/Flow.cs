using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace PromptFlow.Contracts
{
    internal class Flow
    {
        public List<Node> Nodes { get; set; } = new();

        public Dictionary<string, Input> Inputs { get; set; } = new();
        public Dictionary<string, Output> Outputs { get; set; } = new();
        public Flow() { }
    }

    internal class Node
    {
        public string Name { get; set; } = string.Empty;
        public string Type { get; set; } = string.Empty;
        public Source Source { get; set; } = new();
        public Dictionary<string, string> Inputs { get; set; } = new();

        public Node() { }
    }

    internal class Source
    {
        public string Type { get; set; } = string.Empty;
        public string Path { get; set; } = string.Empty;

        public Source() { }
    }

    internal class Input
    {
        public string Type { get; set; } = string.Empty;
        public string Default { get; set; } = string.Empty;
    }

    internal class Output
    {
        public string Type { get; set; } = string.Empty;
        public string Reference { get; set; } = string.Empty;
    }
}
