import { Command } from "commander";

console.log("Hello from Promptflow CLI!");

const pf = new Command();

pf.name("pf");

pf.command("connection").addCommand(
  new Command("list").action(() => {
    console.log("List connections");
  }),
);

pf.parse(process.argv);
