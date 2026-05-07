import "./style.css";

const app = document.getElementById("app");
if (app) {
  app.textContent = "Jarvis booting…";
  document.body.dataset.ready = "true";
}
