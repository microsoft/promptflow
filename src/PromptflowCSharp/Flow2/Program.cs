// See https://aka.ms/new-console-template for more information


using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis;
using Flow;
using System.Reflection;
using PromptFlow;

var flow = new Flow2();

var output = flow.Execute(new Flow2.Input() { Prompt = "test input prompt" });

Console.WriteLine($"Executed flow with output:\nOut1: {output.Out1}\nOut2: {output.Out2}");


Console.WriteLine();
