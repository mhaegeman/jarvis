import "./style.css";
import { Header } from "@/ui/Header";

const start = Date.now();
const header = new Header('[data-cell="top"]');

function tick(): void {
  header.render({ uptimeMs: Date.now() - start });
  requestAnimationFrame(tick);
}
tick();
document.body.dataset.ready = "true";
