import * as sqlite3 from "sqlite3";
import * as sqlite from "sqlite";
import * as path from "path";
import * as os from "os";

class PfStorage {
  private static db: sqlite.Database;

  public static async getDb(): Promise<sqlite.Database> {
    if (!PfStorage) {
      PfStorage.db = await sqlite.open({
        filename: path.join(os.homedir(), ".promptflow/pf.sqlite"),
        driver: sqlite3.Database,
      });
    }
    return PfStorage.db;
  }
}

export const ensureDb = async (): Promise<sqlite.Database> => {
  return PfStorage.getDb();
};
