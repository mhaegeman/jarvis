import { LoginOrrery } from "./LoginOrrery";
import type { Surface } from "@/router";

type FieldState = "idle" | "error" | "success";

const MIN_LENGTH = 12;

/**
 * Login screen surface. Validates passphrase locally (min-length + dev demo checks),
 * then calls onSuccess which mounts the Compass.
 *
 * TODO: replace the local check with POST /auth/login (argon2 hash validation on backend).
 * Interface: AuthProvider.login(passphrase: string): Promise<{ ok: boolean }>
 */
export function createLoginPage(onSuccess: () => void): Surface {
  const app = document.getElementById("app")!;
  let orrery: LoginOrrery | null = null;
  let fieldState: FieldState = "idle";
  let revealed = false;
  let clockInterval: ReturnType<typeof setInterval> | null = null;

  // Build DOM
  app.innerHTML = `
    <div class="corner tl">
      <span class="brand">Jarvis</span>
      <span>v0.4</span>
    </div>
    <div class="corner tr" id="login-clock"></div>
    <div class="corner bl">
      <span class="k">Esc</span> clear &nbsp; <span class="k">Enter</span> unlock
    </div>
    <div class="corner br">session · linen &amp; slate</div>

    <div class="login-stage">
      <div class="card">
        <div id="lock-mount"></div>

        <div class="greet">Welcome back, <em>Max.</em></div>
        <div class="sub">Last seen just now · this machine</div>

        <form class="field" id="login-form" novalidate>
          <div class="login-label">Passphrase</div>
          <div class="input-wrap" id="input-wrap">
            <input id="pw" type="password" placeholder="say it quietly" autocomplete="current-password" />
            <button type="button" class="eye" id="eye-btn" aria-label="Toggle visibility">show</button>
          </div>
          <div class="dots" id="dots" aria-hidden="true"></div>
          <div class="hint-row">
            <span id="hint">12 characters min · all local</span>
            <a href="#" id="forgot" tabindex="-1">forgot it? too bad.</a>
          </div>
          <div class="login-status" id="login-status" role="status">Jarvis is listening for you.</div>
          <div class="actions">
            <button class="login-btn" type="submit" id="submit-btn" disabled>
              <span>Unlock</span>
              <span class="arrow">↵</span>
            </button>
          </div>
        </form>
      </div>
    </div>`;

  const clockEl = document.getElementById("login-clock")!;
  const inputWrap = document.getElementById("input-wrap")!;
  const pwEl = document.getElementById("pw") as HTMLInputElement;
  const eyeBtn = document.getElementById("eye-btn")!;
  const dotsEl = document.getElementById("dots")!;
  const hintEl = document.getElementById("hint")!;
  const statusEl = document.getElementById("login-status")!;
  const submitBtn = document.getElementById("submit-btn") as HTMLButtonElement;
  const forgotLink = document.getElementById("forgot")!;
  const form = document.getElementById("login-form") as HTMLFormElement;

  // Mount orrery
  const lockMount = document.getElementById("lock-mount")!;
  orrery = new LoginOrrery(lockMount);

  // Build 12 strength dots
  for (let i = 0; i < MIN_LENGTH; i++) {
    const span = document.createElement("span");
    dotsEl.appendChild(span);
  }

  function tick(): void {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    clockEl.textContent = `${h}:${m}:${s}`;
  }
  tick();
  clockInterval = setInterval(tick, 1000);

  function setFieldState(state: FieldState): void {
    fieldState = state;
    inputWrap.classList.toggle("error", state === "error");
    inputWrap.classList.toggle("success", state === "success");
    orrery?.setState(state === "error" ? "error" : state === "success" ? "unlocking" : "idle");
    statusEl.className = `login-status${state !== "idle" ? ` ${state}` : ""}`;

    if (state === "error") {
      statusEl.textContent = "that's not it. try again.";
    } else if (state === "success") {
      statusEl.textContent = "unlocked · opening compass…";
    } else {
      statusEl.textContent = "Jarvis is listening for you.";
    }
  }

  function updateDots(value: string): void {
    const len = value.length;
    const full = len >= MIN_LENGTH;
    const dots = dotsEl.querySelectorAll("span");
    dots.forEach((dot, i) => {
      dot.className = i < len ? (full ? "warm" : "on") : "";
    });

    hintEl.textContent = full ? "looks good · Enter to unlock" : `12 characters min · all local`;
    submitBtn.disabled = !full;
  }

  function handleSubmit(e: Event): void {
    e.preventDefault();
    if (fieldState === "success") return;
    const val = pwEl.value;

    // TODO: replace with POST /auth/login — see plan for interface stub
    // Dev-mode demo checks (tested before the length guard so short test strings are reachable):
    if (val === "wrong" || val === "wrongwrong") {
      setFieldState("error");
      setTimeout(() => {
        if (fieldState === "error") {
          setFieldState("idle");
          pwEl.focus();
          pwEl.select();
        }
      }, 600);
      return;
    }

    if (val.length < MIN_LENGTH) return;

    setFieldState("success");
    setTimeout(() => onSuccess(), 900);
  }

  pwEl.addEventListener("input", () => {
    if (fieldState === "error") setFieldState("idle");
    updateDots(pwEl.value);
  });

  eyeBtn.addEventListener("click", () => {
    revealed = !revealed;
    pwEl.type = revealed ? "text" : "password";
    eyeBtn.textContent = revealed ? "hide" : "show";
  });

  forgotLink.addEventListener("click", (e) => {
    e.preventDefault();
    // nothing to do — it's an easter egg
  });

  form.addEventListener("submit", handleSubmit);

  // Keyboard shortcuts
  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      pwEl.value = "";
      revealed = false;
      pwEl.type = "password";
      eyeBtn.textContent = "show";
      updateDots("");
      setFieldState("idle");
    }
  }
  window.addEventListener("keydown", handleKeydown);

  // Focus input
  pwEl.focus();

  return {
    destroy(): void {
      if (clockInterval !== null) clearInterval(clockInterval);
      window.removeEventListener("keydown", handleKeydown);
      orrery?.destroy();
      app.innerHTML = "";
    },
  };
}
