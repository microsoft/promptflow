import { Command } from "commander";
import { list as listConnections } from "@promptflowjs/connections";

export const connectionCommand = (pf: Command): void => {
  pf.command("connection").addCommand(
    new Command("list").action(() => {
      const connections = listConnections();

      console.log(JSON.stringify(connections, null, 2));
    }),
  );
};
