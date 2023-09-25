import { Command } from "commander";

export const connectionCommand = (pf: Command): void => {
  pf.command("connection").addCommand(
    new Command("list").action(() => {
      console.log("List connections works!");
    }),
  );
};
