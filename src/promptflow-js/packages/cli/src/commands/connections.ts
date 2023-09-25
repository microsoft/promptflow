import { Command } from "commander";
import { list as listConnections } from "@promptflow-js/connections";

export const connectionCommand = (pf: Command): void => {
  pf.command("connection").addCommand(
    new Command("list").action(async () => {
      const connections = await listConnections();

      // eslint-disable-next-line unicorn/no-null
      console.log(JSON.stringify(connections, null, 2));
    }),
  );
};
