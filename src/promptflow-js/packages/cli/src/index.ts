import { Command } from "commander";
import { connectionCommand } from "./commands/connections";

const pf = new Command();

pf.name("pf");
connectionCommand(pf);
pf.parse();
