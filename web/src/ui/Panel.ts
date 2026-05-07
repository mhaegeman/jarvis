/** Render the standard panel chrome (title + body) into a host element. */
export function renderPanel(host: HTMLElement, title: string, body: string): void {
  host.classList.add("panel");
  host.setAttribute("role", "region");
  host.setAttribute("aria-label", title);
  host.innerHTML = `<h4>${title}</h4>${body}`;
}
