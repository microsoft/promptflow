// See https://aka.ms/new-console-template for more information
using Mono.Options;
using Newtonsoft.Json;
using PromptFlow;

// these variables will be set when the command line is parsed
string flow = "../../../flow.dag.yaml";
string input = "../../../data.jsonl";

// these are the available options, note that they set the variables
var options = new OptionSet {
    { "input=", "input data.", (string r) => input = r },
};

try
{
    options.Parse(args);
}
catch (OptionException e)
{
    Console.WriteLine("Met error in parsing arguments, use default argument to run:");
    Console.WriteLine(e.ToString());
}

Console.WriteLine($"Entry script started with arguments: input=\"{input}\".");

Executor executor = new(flow);

foreach (var inputLine in System.IO.File.ReadAllLines(input))
{
    var temp = JsonConvert.DeserializeObject<Dictionary<string, string>>(inputLine)
        ?? throw new ArgumentException($"Can't deserialize as Dict[str, str] {inputLine} correctly");
    var outputs = executor.Execute(temp);

    Console.WriteLine("\nFlow executed with output: ");
    foreach (var output in outputs)
    {
        Console.WriteLine($"{output.Key}: {output.Value}");
    }
}

Console.WriteLine("\nEntry script finished.");
