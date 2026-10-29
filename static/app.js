"use strict";
const byId = (id) => document.getElementById(id);
const form = byId("form");
const results = byId("results");
const status = byId("status");
const error = byId("error");
const demo = document.body.dataset.demo === "true";
const node = (tag, text, style) => {
  const element = document.createElement(tag);
  element.textContent = text;
  if (style) element.className = style;
  return element;
};

byId("ejemplo").addEventListener("click", () => {
  byId("cv-text").value =
    "Analista de datos. Conocimientos de Python, SQL y Excel. Preparación de reportes, limpieza de datos con pandas y consultas en SQLite.";
  byId("cv-file").value = "";
  byId("cv-text").focus();
});

function showMatches(matches) {
  results.replaceChildren();
  for (const match of matches) {
    const article = document.createElement("article");
    article.className = "oferta";
    article.append(node("h3", match.position || "Aviso sin título"));
    article.append(
      node(
        "p",
        [match.company, match.location].filter(Boolean).join(" · "),
        "empresa",
      ),
    );
    const skills = match.why?.shared_skills || [];
    article.append(
      node(
        "p",
        skills.length
          ? "Coincide en: " + skills.join(", ")
          : "Coincide en algunas palabras del CV.",
        "coincidencias",
      ),
    );
    article.append(
      node(
        "span",
        demo
          ? "Datos ficticios"
          : "Enlace " + (match.link_status || "sin verificar"),
        "estado",
      ),
    );
    if (!demo) {
      try {
        const url = new URL(match.apply_url);
        if (url.protocol === "https:" && !url.username && !url.password) {
          const link = node("a", "Ver aviso");
          link.href = url.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          article.append(link);
        }
      } catch {
        /* Un aviso con enlace inválido no se muestra como enlace. */
      }
    }
    results.append(article);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.hidden = true;
  error.textContent = "";
  const upload = byId("cv-file").files[0];
  if (upload && upload.size > 1048576) {
    error.textContent = "El archivo no puede superar 1 MB.";
    error.hidden = false;
    return;
  }
  const button = byId("buscar");
  button.disabled = true;
  button.textContent = "Buscando…";
  results.setAttribute("aria-busy", "true");
  status.textContent = "Consultando los avisos. Puede tardar unos segundos.";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 22000);
  try {
    const response = await fetch("/api/match", {
      method: "POST",
      body: new FormData(form),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data)
      throw new Error(data?.error || "No se pudo completar la consulta.");
    showMatches(data.matches || []);
    status.textContent = data.matches?.length
      ? data.message
      : "No se encontraron avisos con coincidencias para este CV.";
  } catch (failure) {
    results.replaceChildren();
    status.textContent = "";
    error.textContent =
      failure.name === "AbortError"
        ? "La consulta tardó demasiado. Probá de nuevo más tarde."
        : failure.message;
    error.hidden = false;
  } finally {
    clearTimeout(timer);
    button.disabled = false;
    button.textContent = "Buscar avisos";
    results.setAttribute("aria-busy", "false");
  }
});
