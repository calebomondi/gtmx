import { startAuthentication, startRegistration, type PublicKeyCredentialRequestOptionsJSON } from "@simplewebauthn/browser"

import type { PasskeyOwner, SignatureRequestDto } from "@/lib/api"

/** ES256: the only key type the Store's wallet accepts. */
const ES256 = -7

function randomBase64Url(bytes: number): string {
  const raw = crypto.getRandomValues(new Uint8Array(bytes))
  return btoa(String.fromCharCode(...raw)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

/** Make a passkey on this device for the Store's owner. Nothing is verified
 * here: the passkey proves itself later, when NEAR Intents checks each
 * signature against the public key returned now. */
export async function createStorePasskey(storeName: string, who: { email: string; name: string }): Promise<PasskeyOwner> {
  const created = await startRegistration({
    optionsJSON: {
      challenge: randomBase64Url(32),
      rp: { id: window.location.hostname, name: "Thalace" },
      user: { id: randomBase64Url(16), name: `${who.email} · ${storeName}`, displayName: `${who.name}, for ${storeName}` },
      pubKeyCredParams: [{ type: "public-key", alg: ES256 }],
      authenticatorSelection: { residentKey: "preferred", userVerification: "required" },
      attestation: "none",
    },
  })
  const publicKey = created.response.publicKey
  if (!publicKey || created.response.publicKeyAlgorithm !== ES256) {
    throw new Error("This browser can't make the kind of passkey the Store needs. Try a recent Chrome, Safari or Edge.")
  }
  return { credential_id: created.id, public_key: publicKey, rp_id: window.location.hostname, origin: window.location.origin }
}

/** Sign one of the Store's requests with the owner's passkey. The request is
 * passed to the device exactly as NEAR Intents made it. */
export async function signWithPasskey(request: SignatureRequestDto): Promise<Record<string, unknown>> {
  if (request.intent.standard !== "webauthn") {
    throw new Error(`This Store signs with a passkey, but was asked for a ${request.intent.standard} signature.`)
  }
  const credential = await startAuthentication({ optionsJSON: request.intent.payload as PublicKeyCredentialRequestOptionsJSON })
  return { ...request.intent, credential }
}

/** What went wrong with a passkey prompt, in words for the owner. */
export function passkeyError(err: unknown): string {
  if (err instanceof Error && err.name === "NotAllowedError") return "The passkey prompt was closed or timed out. Try again."
  return err instanceof Error ? err.message : String(err)
}
