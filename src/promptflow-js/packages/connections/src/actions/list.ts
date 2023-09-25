import { ConnectionDto, ensureDb } from "@promptflowjs/core";

export const list = async (): Promise<ConnectionDto[]> => {
  const db = await ensureDb();

  const connections = db.all(
    "SELECT connectionName, connectionType, configs, customConfigs FROM connections",
  );

  return connections;
};
