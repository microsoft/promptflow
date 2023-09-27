import * as keytar from "keytar";
import * as crypto from "crypto";

const KEYRING_SYSTEM = "promptflow";
const KEYRING_ENCRYPTION_KEY_NAME = "encryption_key";

// todo: src/promptflow/promptflow/_sdk/_utils.py
const getEncryptionKey = async (): Promise<string> => {
  try {
    return await keytar.getPassword(
      KEYRING_SYSTEM,
      KEYRING_ENCRYPTION_KEY_NAME,
    );
  } catch (error) {
    throw new Error(`
      System system's keychain backend service not found in your operating system.
      On macOS the passwords are managed by the Keychain, on Linux they are managed by the Secret Service API/libsecret, and on Windows they are managed by Credential Vault.
    `);
  }
};

export const decrypt = async (encrypted: string): Promise<string> => {
  const encryptionKey = await getEncryptionKey();
  const iv = Buffer.alloc(16, 0);
  const fernetClient = crypto.createCipheriv("aes-256-cbc", encryptionKey, iv);
  let decrypted = fernetClient.update(encrypted, "hex", "utf8");
  decrypted += fernetClient.final("utf8");
  return decrypted;
};
