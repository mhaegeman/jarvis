export interface KeyboardActions {
  onMicDown(): void;
  onMicUp(): void;
  onInterrupt(): void;
}

function isInputTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  return t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable;
}

export function attachKeyboard(target: Window, a: KeyboardActions): () => void {
  let micDown = false;

  const onKeyDown = (e: KeyboardEvent): void => {
    if (e.repeat) return;
    if (e.code === "Space" && !micDown && !isInputTarget(e.target)) {
      e.preventDefault();
      micDown = true;
      a.onMicDown();
    } else if (e.key === "Escape") {
      e.preventDefault();
      a.onInterrupt();
    }
  };

  const onKeyUp = (e: KeyboardEvent): void => {
    if (e.code === "Space" && micDown) {
      e.preventDefault();
      micDown = false;
      a.onMicUp();
    }
  };

  target.addEventListener("keydown", onKeyDown);
  target.addEventListener("keyup", onKeyUp);
  return (): void => {
    target.removeEventListener("keydown", onKeyDown);
    target.removeEventListener("keyup", onKeyUp);
  };
}
