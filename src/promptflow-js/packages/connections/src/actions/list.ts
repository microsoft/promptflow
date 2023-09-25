import { ConnectionDto, ensureDb } from "@promptflow-js/core";

export const list = async (): Promise<ConnectionDto[]> => {
  const db = await ensureDb();

  const connections = await db.all(
    "SELECT connectionName, connectionType, configs, customConfigs FROM connection",
  );

  return connections;
};
