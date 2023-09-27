// See https://aka.ms/new-console-template for more information


using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis;
using Flow;
using System.Reflection;
using PromptFlow;

var flow = new Flow2();

flow.Execute(new Flow2.Input() { Prompt = "test input prompt" });

var function = flow.Execute;
var body = function.GetMethodInfo().GetMethodBody();

SyntaxTree tree = CSharpSyntaxTree.ParseText("../../../Flow2.cs");
CompilationUnitSyntax root = tree.GetCompilationUnitRoot();
var nodes = root.DescendantNodes().ToList();
var property = root.DescendantNodes()
                       .OfType<MethodDeclarationSyntax>()
                       .Where(md => md.Identifier.ValueText.Equals("Execute"))
                       .FirstOrDefault();
var compilation = CSharpCompilation.Create("HelloWorld")
    .AddReferences(MetadataReference.CreateFromFile(
        typeof(string).Assembly.Location))
    .AddSyntaxTrees(tree);
Parser parser = new Parser();
parser.Generate("../../../Temp.cs");

Console.WriteLine();
