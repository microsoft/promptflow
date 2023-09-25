import { Command } from "commander";

const pfCliProgram = new Command();

pfCliProgram.name("pf");

pfCliProgram.option("-v, --version", "output the current version");
