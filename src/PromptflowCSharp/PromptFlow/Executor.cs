using PromptFlow.Contracts;
using System.Collections.Generic;
using System.Reflection;
using YamlDotNet.RepresentationModel;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace PromptFlow
{
    internal class ExecutableNode
    {
        public string Name { get; set; } = String.Empty;

        public MethodInfo Method { get; set; }

        public object? Object { get; set; }

        public Dictionary<string, string> Inputs { get; set; } = new Dictionary<string, string>();

        public ExecutableNode(MethodInfo method)
        {
            Method = method;
        }
    }

    public class Executor
    {
        internal IEnumerable<Assembly> assemblies;
        Flow flowInstance;
        List<ExecutableNode> executableNodes;


        public Executor(string flow)
        {
            assemblies = AppDomain.CurrentDomain.GetAssemblies();
            var deserializer = new DeserializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .Build();

            using var reader = new StreamReader(flow);
            flowInstance = deserializer.Deserialize<Flow>(reader.ReadToEnd());
            executableNodes = new List<ExecutableNode>();
            foreach (var node in flowInstance.Nodes)
            {
                if (node.Type != "csharp")
                {
                    throw new Exception($"Support csharp node only for now but got {node.Type}");
                }
                if (node.Source.Type != "code")
                {
                    throw new Exception($"Support type code for csharp node only for now but got{node.Source.Type}");
                }
                var targetTuple = GetToolFunction(node.Source.Path);
                var executableNode = new ExecutableNode(targetTuple.Item2)
                {
                    Name = node.Name,
                    Object = targetTuple.Item1,
                    Inputs = node.Inputs,
                };
                executableNodes.Add(executableNode);
            }
        }

        private Tuple<object?, MethodInfo> GetToolFunction(string path)
        {
            string? assemblyName = null;
            string toolClassName;
            var pieces = path.Split(':');
            switch (pieces.Length)
            {
                case 1:
                    toolClassName = pieces[0];
                    break;
                case 2:
                    assemblyName = pieces[0];
                    toolClassName = pieces[1];
                    break;
                default:
                    throw new ArgumentException($"Invalid path: {path}");
            }

            Assembly targetAssembly = ((assemblyName != null) ? assemblies.Single(ass => ass.GetName().Name == assemblyName) :
                Assembly.GetEntryAssembly()) ?? throw new ArgumentException($"Can't found entry assembly.");
            Type targetClass = targetAssembly.GetType(toolClassName) ?? throw new ArgumentException($"Can't found class {toolClassName} under {targetAssembly.GetName().Name}.");
            MethodInfo targetFunction = targetClass.GetMethods().Single(m => m.GetCustomAttribute(typeof(ToolAttribute)) != null);
            if (targetFunction.IsStatic)
            {
                return new Tuple<object?, MethodInfo>(null, targetFunction);
            }
            else
            {
                var targetObject = Activator.CreateInstance(targetClass);
                return new Tuple<object?, MethodInfo>(targetObject, targetFunction);
            }
        }

        public Dictionary<string, object?> Execute(Dictionary<string, string> inputs)
        {
            Dictionary<string, object?> crossNodeIO = new();
            foreach (var key in flowInstance.Inputs.Keys)
            {
                crossNodeIO["${inputs." + key + "}"] = inputs.GetValueOrDefault(key) ?? flowInstance.Inputs[key].Default;
            }

            foreach (var node in executableNodes)
            {
                Console.WriteLine($"Executing node {node.Name}");
                var parameters = new List<object?>();
                foreach (var param in node.Method.GetParameters())
                {
                    if (param == null)
                    {
                        // not sure why this happen
                        break;
                    }
                    if (!node.Inputs.ContainsKey(param.Name ?? throw new ArgumentException($"Parameters of tool function {node.Method.Name} must have a name.")))
                    {
                        throw new ArgumentException($"Parameter {param.Name} of tool function {node.Method.Name} can't be found in inputs of node {node.Name}.");
                    }
                    var inputExpression = node.Inputs[param.Name];
                    if (!crossNodeIO.ContainsKey(inputExpression))
                    {
                        throw new ArgumentException($"Can't find input referrence {inputExpression} in current context. " +
                            $"Note that nodes will be executed in provided order for now, so maybe the referred node hasn't been executed yet.");
                    }
                    parameters.Add(crossNodeIO[inputExpression]);
                }
                var output = node.Method.Invoke(node.Object, parameters.ToArray());
                Console.WriteLine($"Executed node {node.Name} and got output: {output}");
                crossNodeIO["${" + node.Name + ".output}"] = output;
            }

            Dictionary<string, object?> outputs = new();
            foreach (var outputName in flowInstance.Outputs.Keys)
            {
                var referrence = flowInstance.Outputs[outputName].Reference;
                if (!crossNodeIO.ContainsKey(referrence))
                {
                    throw new ArgumentException($"invalid output reference {referrence}");
                }
                outputs[outputName] = crossNodeIO[referrence];
            }
            return outputs;
        }
    }
}
