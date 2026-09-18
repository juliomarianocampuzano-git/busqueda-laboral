
const form = document.getElementById("form");
const statusEl = document.getElementById("status");
const results = document.getElementById("results");
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  statusEl.textContent = "Consultando RemoteOK y verificando apply_url...";
  results.innerHTML = "";
  const res = await fetch("/api/match", { method: "POST", body: new FormData(form) });
  const data = await res.json();
  statusEl.textContent = data.message || "";
  if (!data.matches || !data.matches.length) {
    results.innerHTML = "<p>0 matches encontrados</p>";
    return;
  }
  results.innerHTML = data.matches.map((m) => `
    <article class="offer">
      <h2>${m.position || "(sin título)"}</h2>
      <p><strong>${m.company || ""}</strong> · ${m.location || ""} · afinidad ${m.affinity}</p>
      <p>Por qué: skills ${(m.why?.shared_skills || []).join(", ") || "pocas explícitas"};
         seniority ${m.why?.seniority_signal}; modalidad ${m.why?.modality};
         similitud ${m.why?.tfidf_similarity}</p>
      <p>Tags: ${(m.tags || []).join(", ")}</p>
      <p><a href="${m.apply_url}" target="_blank" rel="noopener">Postularme (apply_url original)</a></p>
    </article>`).join("");
});
