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
      const link = safeLink(match.apply_url, "Ver aviso");
      if (link) article.append(link);
    }
    const save = node("button", "Guardar en mis postulaciones", "secundario guardar");
    save.type = "button";
    save.addEventListener("click", () => saveApplication(match, save));
    article.append(save);
    results.append(article);
  }
}

/* ---------- postulaciones ---------- */
const LABELS = {
  guardada: "Guardada",
  postulada: "Postulada",
  entrevista: "Entrevista",
  oferta: "Oferta",
  descartada: "Descartada",
};
const postList = byId("lista-post");

function safeLink(value, text) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return null;
    const link = node("a", text);
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  } catch {
    /* Un aviso con enlace inválido no se muestra como enlace. */
    return null;
  }
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);
  if (!response.ok || !data)
    throw new Error(data?.error || "No se pudo guardar el cambio.");
  return data;
}

const sendJson = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

async function saveApplication(match, button) {
  button.disabled = true;
  try {
    const data = await api(
      "/api/postulaciones",
      sendJson("POST", {
        position: match.position || "Aviso sin título",
        company: match.company || "",
        apply_url: match.apply_url || "",
      }),
    );
    button.textContent = data.created ? "Guardada ✓" : "Ya estaba guardada";
    button.classList.add("hecho");
    status.textContent = "Aviso guardado en tus postulaciones.";
    loadApplications();
  } catch (failure) {
    button.disabled = false;
    error.textContent = failure.message;
    error.hidden = false;
  }
}

function renderApplications(data) {
  const counters = byId("contadores");
  counters.replaceChildren();
  for (const key of data.statuses) {
    const item = document.createElement("li");
    item.append(node("strong", String(data.counts[key])), LABELS[key]);
    counters.append(item);
  }
  postList.replaceChildren();
  if (!data.items.length) {
    postList.append(
      node(
        "li",
        "Todavía no guardaste avisos. Buscá avisos y tocá “Guardar en mis postulaciones”.",
        "vacio",
      ),
    );
    return;
  }
  for (const item of data.items) {
    const row = node("li", "", "post");
    const info = document.createElement("div");
    info.append(node("h3", item.position));
    const company = node("p", item.company || "Empresa sin indicar", "empresa");
    const link = demo ? null : safeLink(item.apply_url, "Ver aviso");
    if (link) company.append(" · ", link);
    info.append(company);

    const select = document.createElement("select");
    select.setAttribute("aria-label", "Estado de " + item.position);
    for (const key of data.statuses) {
      const option = new Option(LABELS[key], key, false, key === item.status);
      select.append(option);
    }
    select.addEventListener("change", () =>
      patch(item.id, { status: select.value }, "Estado actualizado."),
    );

    const notes = document.createElement("textarea");
    notes.maxLength = 1000;
    notes.placeholder = "Notas: contacto, fecha de entrevista, próximos pasos…";
    notes.value = item.notes;
    notes.setAttribute("aria-label", "Notas de " + item.position);
    notes.addEventListener("change", () =>
      patch(item.id, { notes: notes.value }, "Notas guardadas."),
    );

    const actions = node("div", "", "acciones");
    actions.append(node("small", "Actualizada: " + item.updated_at + " (UTC)"));
    const remove = node("button", "Quitar", "borrar");
    remove.type = "button";
    remove.setAttribute("aria-label", "Quitar " + item.position);
    remove.addEventListener("click", async () => {
      if (!confirm("¿Quitar “" + item.position + "” de tus postulaciones?")) return;
      try {
        await api("/api/postulaciones/" + item.id, { method: "DELETE" });
        status.textContent = "Postulación quitada.";
        loadApplications();
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
      }
    });
    actions.append(remove);
    row.append(info, select, notes, actions);
    postList.append(row);
  }
}

async function patch(id, body, message) {
  try {
    await api("/api/postulaciones/" + id, sendJson("PATCH", body));
    status.textContent = message;
    loadApplications();
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
  }
}

async function loadApplications() {
  try {
    renderApplications(await api("/api/postulaciones"));
  } catch {
    postList.replaceChildren(
      node("li", "No se pudieron cargar las postulaciones.", "vacio"),
    );
  }
}
loadApplications();

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
