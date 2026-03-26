/**
 * Ed25519 key management and challenge-response signing for Ginie authentication.
 *
 * Uses tweetnacl for Ed25519 operations.
 * Primary storage is a downloadable encrypted key file, not localStorage.
 */

import nacl from "tweetnacl";
import {
  encodeBase64,
  decodeBase64,
  decodeUTF8,
} from "tweetnacl-util";

export interface KeyPair {
  publicKey: string; // base64
  secretKey: string; // base64
  fingerprint: string; // "1220" + hex(publicKey)
}

export interface KeyFile {
  version: 1;
  publicKey: string; // base64
  encryptedSecretKey: string; // base64 (nacl secretbox)
  nonce: string; // base64
  salt: string; // base64
  fingerprint: string;
}

/**
 * Generate an Ed25519 key pair.
 */
export function generateKeyPair(): KeyPair {
  const kp = nacl.sign.keyPair();
  const publicKey = encodeBase64(kp.publicKey);
  const secretKey = encodeBase64(kp.secretKey);
  const fingerprint = computeFingerprint(publicKey);
  return { publicKey, secretKey, fingerprint };
}

/**
 * Compute Canton-standard fingerprint: "1220" + hex(publicKey).
 */
export function computeFingerprint(publicKeyB64: string): string {
  const bytes = decodeBase64(publicKeyB64);
  const hex = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `1220${hex}`;
}

/**
 * Sign a challenge string with the secret key.
 * Returns the signature as a base64 string.
 */
export function signChallenge(
  challenge: string,
  secretKeyB64: string,
): string {
  const secretKey = decodeBase64(secretKeyB64);
  const message = decodeUTF8(challenge);
  const signature = nacl.sign.detached(message, secretKey);
  return encodeBase64(signature);
}

/**
 * Derive an encryption key from a password using a simple PBKDF-like approach.
 * Uses nacl.hash (SHA-512) with salt for key derivation.
 */
function deriveKey(password: string, salt: Uint8Array): Uint8Array {
  const passwordBytes = decodeUTF8(password);
  const combined = new Uint8Array(passwordBytes.length + salt.length);
  combined.set(passwordBytes, 0);
  combined.set(salt, passwordBytes.length);
  const hash = nacl.hash(combined);
  // Use first 32 bytes of SHA-512 hash as the symmetric key
  return hash.slice(0, nacl.secretbox.keyLength);
}

/**
 * Export a key pair to an encrypted JSON key file.
 * The secret key is encrypted with a user-provided password.
 */
export function exportKeyFile(
  keyPair: KeyPair,
  password: string,
): KeyFile {
  const salt = nacl.randomBytes(16);
  const nonce = nacl.randomBytes(nacl.secretbox.nonceLength);
  const key = deriveKey(password, salt);
  const secretKeyBytes = decodeBase64(keyPair.secretKey);
  const encrypted = nacl.secretbox(secretKeyBytes, nonce, key);

  return {
    version: 1,
    publicKey: keyPair.publicKey,
    encryptedSecretKey: encodeBase64(encrypted),
    nonce: encodeBase64(nonce),
    salt: encodeBase64(salt),
    fingerprint: keyPair.fingerprint,
  };
}

/**
 * Import a key pair from an encrypted JSON key file.
 * Returns null if the password is wrong.
 */
export function importKeyFile(
  keyFile: KeyFile,
  password: string,
): KeyPair | null {
  try {
    const salt = decodeBase64(keyFile.salt);
    const nonce = decodeBase64(keyFile.nonce);
    const key = deriveKey(password, salt);
    const encrypted = decodeBase64(keyFile.encryptedSecretKey);
    const secretKeyBytes = nacl.secretbox.open(encrypted, nonce, key);

    if (!secretKeyBytes) return null; // wrong password

    return {
      publicKey: keyFile.publicKey,
      secretKey: encodeBase64(secretKeyBytes),
      fingerprint: keyFile.fingerprint,
    };
  } catch {
    return null;
  }
}

/**
 * Download a key file as a JSON blob.
 */
export function downloadKeyFile(keyFile: KeyFile, filename?: string): void {
  const json = JSON.stringify(keyFile, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `ginie-key-${keyFile.fingerprint.slice(4, 12)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Read a key file from a File input.
 */
export async function readKeyFileFromInput(file: File): Promise<KeyFile> {
  const text = await file.text();
  const parsed = JSON.parse(text) as KeyFile;
  if (parsed.version !== 1 || !parsed.publicKey || !parsed.encryptedSecretKey) {
    throw new Error("Invalid key file format");
  }
  return parsed;
}
