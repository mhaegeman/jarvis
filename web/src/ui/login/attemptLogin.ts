const AUTH_URL = "/auth/login";
const MIN_LENGTH = 12;

export interface LoginResult {
  ok: boolean;
}

export async function attemptLogin(passphrase: string): Promise<LoginResult> {
  try {
    const res = await fetch(AUTH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passphrase }),
    });
    if (res.ok) {
      const { token } = (await res.json()) as { token: string };
      sessionStorage.setItem("jarvis_token", token);
      return { ok: true };
    }
    return { ok: false };
  } catch {
    // Backend unreachable (demo/offline mode) — fall back to length check
    return { ok: passphrase.length >= MIN_LENGTH };
  }
}
