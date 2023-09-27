using System;
using System.CodeDom;
using System.CodeDom.Compiler;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;

namespace PromptFlow
{
    public class Parser
    {
        private CodeCompileUnit targetUnit;
        public Parser()
        {
            targetUnit = new CodeCompileUnit();
            CodeNamespace samples = new CodeNamespace("Flow");
            samples.Imports.Add(new CodeNamespaceImport("System"));
            targetUnit.Namespaces.Add(samples);
        }

        public void Generate(string fileName)
        {
            CodeDomProvider provider = CodeDomProvider.CreateProvider("CSharp");
            CodeGeneratorOptions options = new CodeGeneratorOptions();
            options.BracingStyle = "C";
            using (StreamWriter sourceWriter = new StreamWriter(fileName))
            {
                provider.GenerateCodeFromCompileUnit(
                    targetUnit, sourceWriter, options);
            }
        }


    }
}
