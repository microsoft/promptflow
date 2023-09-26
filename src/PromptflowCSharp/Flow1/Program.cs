// See https://aka.ms/new-console-template for more information
using PromptFlow;

Console.WriteLine("Entry script started.");

Executor executor = new();

var outputs = executor.Execute("../../../flow.dag.yaml", new Dictionary<string, string>()
{
    {"prompt", "test input prompt" }
});

Console.WriteLine("\nFlow executed with output: ");
foreach (var output in outputs)
{
    Console.WriteLine($"{output.Key}: {output.Value}");
}

Console.WriteLine("\nEntry script finished.");
