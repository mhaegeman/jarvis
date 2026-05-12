const AUTH_URL = "/auth/login";

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
    // Network/runtime failure — fail closed. We never grant access without a
    // successful backend verification. (Offline demo mode, if reintroduced,
    // must be gated by an explicit build-time flag, not a fetch fallback.)
    return { ok: false };
  }
}
