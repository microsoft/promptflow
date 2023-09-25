import { Command } from "commander";
import { connectionCommand } from "./commands/connection";

console.log("Hello from Promptflow CLI!");

const pf = new Command();

pf.name("pf");
connectionCommand(pf);
pf.parse(process.argv);
