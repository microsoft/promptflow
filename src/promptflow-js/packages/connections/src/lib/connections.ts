import { Database } from "sqlite3";
import { open } from "sqlite";
import { homedir } from "os";
import { join } from "path";

export const connections = async (): Promise<string[]> => {
  const db = await open({
    filename: join(homedir(), ".promptflow/pf.sqlite"),
    driver: Database,
  });

  const list = await db.all("SELECT * from connection;");

  console.log(list);

  return list.map((item) => item.connectionName);
};
