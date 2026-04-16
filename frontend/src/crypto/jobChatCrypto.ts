/**
 * Client-side E2EE for job-order chat: X25519 wrap of room key + AES-GCM for messages.
 * Must stay in sync with unwrap/decrypt logic (single implementation).
 */
import { x25519 } from "@noble/curves/ed25519";

const STORAGE_PRIV = "mci_job_chat_x25519_private";

const HKDF_WRAP_INFO = "mci-job-chat-wrap-v1";
const MSG_AAD_PREFIX = "mci-job-chat-msg-v1|job=";

function u8ToB64(u: Uint8Array): string {
  let bin = "";
  u.forEach((b) => {
    bin += String.fromCharCode(b);
  });
  return btoa(bin);
}

function b64ToU8(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function randomBytes(n: number): Uint8Array {
  const u = new Uint8Array(n);
  crypto.getRandomValues(u);
  return u;
}

export function getOrCreateX25519Identity(): { privateKey: Uint8Array; publicKey: Uint8Array } {
  const raw = localStorage.getItem(STORAGE_PRIV);
  if (raw) {
    try {
      const privateKey = b64ToU8(raw);
      if (privateKey.length === 32) {
        return { privateKey, publicKey: x25519.getPublicKey(privateKey) };
      }
    } catch {
      /* fall through */
    }
  }
  const privateKey = x25519.utils.randomPrivateKey();
  localStorage.setItem(STORAGE_PRIV, u8ToB64(privateKey));
  return { privateKey, publicKey: x25519.getPublicKey(privateKey) };
}

export function publicKeyB64(): string {
  const { publicKey } = getOrCreateX25519Identity();
  return u8ToB64(publicKey);
}

async function hkdfAes256GcmKey(ikm: Uint8Array, info: string): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", ikm, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: new Uint8Array(0),
      info: new TextEncoder().encode(info),
    },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

/** Ephemeral X25519 + AES-GCM(room_key); blob = e_pub(32) | iv(12) | ct+tag */
export async function wrapRoomKey(roomKey32: Uint8Array, recipientPublicKeyB64: string, jobId: number): Promise<string> {
  if (roomKey32.length !== 32) throw new Error("room key must be 32 bytes");
  const recipientPub = b64ToU8(recipientPublicKeyB64);
  if (recipientPub.length !== 32) throw new Error("invalid recipient public key");
  const ephPriv = x25519.utils.randomPrivateKey();
  const ephPub = x25519.getPublicKey(ephPriv);
  const shared = x25519.getSharedSecret(ephPriv, recipientPub);
  const aes = await hkdfAes256GcmKey(shared, `${HKDF_WRAP_INFO}|job=${jobId}`);
  const iv = randomBytes(12);
  const ct = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, aes, roomKey32.buffer as ArrayBuffer),
  );
  const out = new Uint8Array(32 + 12 + ct.length);
  out.set(ephPub, 0);
  out.set(iv, 32);
  out.set(ct, 44);
  return u8ToB64(out);
}

export async function unwrapRoomKey(wrappedKeyB64: string, jobId: number): Promise<Uint8Array> {
  const { privateKey } = getOrCreateX25519Identity();
  const blob = b64ToU8(wrappedKeyB64);
  if (blob.length < 44 + 16) throw new Error("wrapped key too short");
  const ephPub = blob.slice(0, 32);
  const iv = blob.slice(32, 44);
  const ct = blob.slice(44);
  const shared = x25519.getSharedSecret(privateKey, ephPub);
  const aes = await hkdfAes256GcmKey(shared, `${HKDF_WRAP_INFO}|job=${jobId}`);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, aes, ct.buffer as ArrayBuffer);
  return new Uint8Array(pt);
}

export async function encryptChatMessage(roomKey32: Uint8Array, plaintextUtf8: string, jobId: number) {
  if (roomKey32.length !== 32) throw new Error("room key must be 32 bytes");
  const aes = await crypto.subtle.importKey("raw", roomKey32, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  const iv = randomBytes(12);
  const aad = new TextEncoder().encode(`${MSG_AAD_PREFIX}${jobId}`);
  const data = new TextEncoder().encode(plaintextUtf8);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad }, aes, data));
  return { ciphertextB64: u8ToB64(ct), ivB64: u8ToB64(iv) };
}

export async function decryptChatMessage(roomKey32: Uint8Array, ciphertextB64: string, ivB64: string, jobId: number) {
  if (roomKey32.length !== 32) throw new Error("room key must be 32 bytes");
  const aes = await crypto.subtle.importKey("raw", roomKey32, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  const iv = b64ToU8(ivB64);
  const ct = b64ToU8(ciphertextB64);
  const aad = new TextEncoder().encode(`${MSG_AAD_PREFIX}${jobId}`);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: aad }, aes, ct.buffer as ArrayBuffer);
  return new TextDecoder().decode(pt);
}

export function generateRoomKey(): Uint8Array {
  return randomBytes(32);
}
