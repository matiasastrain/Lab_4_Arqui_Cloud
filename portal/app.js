// Portal ciudadano / funcionario. Habla solo con la API del gestor.
const API = (window.APP_CONFIG && window.APP_CONFIG.API_URL || "").replace(/\/$/, "");
const estado = { c: null, f: null }; // tokens de sesión
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
const fecha = (iso) => new Date(iso).toLocaleString("es-CL");

function aviso(texto, error = false) {
  const m = $("#mensaje");
  m.textContent = texto;
  m.className = "mensaje" + (error ? " error" : "");
  clearTimeout(aviso._t);
  aviso._t = setTimeout(() => m.classList.add("oculto"), 6000);
}

async function api(ruta, { token, metodo = "GET", json, form, crudo } = {}) {
  const headers = {};
  if (token) headers.Authorization = "Bearer " + token;
  if (json) headers["Content-Type"] = "application/json";
  const r = await fetch(API + ruta, { method: metodo, headers, body: json ? JSON.stringify(json) : form });
  if (!r.ok) {
    let det = r.statusText;
    try { det = (await r.json()).detail || det; } catch (_) {}
    throw new Error(typeof det === "string" ? det : JSON.stringify(det));
  }
  return crudo ? r.blob() : r.json();
}

function guardarSesion() { try { sessionStorage.setItem("pdi", JSON.stringify(estado)); } catch (_) {} }
function cargarSesion() { try { Object.assign(estado, JSON.parse(sessionStorage.getItem("pdi") || "{}")); } catch (_) {} }

// ---------------- Pestañas ----------------
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("activo", x === b));
  $("#vista-ciudadano").classList.toggle("oculto", b.dataset.vista !== "ciudadano");
  $("#vista-funcionario").classList.toggle("oculto", b.dataset.vista !== "funcionario");
}));

function historialHTML(t) {
  return `<ul class="hist">${t.historial.map((h) => `
    <li><b>${esc(h.estado_nuevo)}</b> · ${fecha(h.fecha)} · <small>${esc(h.actor)}</small>
      ${h.comentario ? `<div>${esc(h.comentario)}</div>` : ""}
      ${h.aviso
        ? `<div class="aviso">📨 ${esc(h.aviso.texto)} <span class="origen ${esc(h.aviso.origen)}">${esc(h.aviso.origen)}</span></div>`
        : `<div class="aviso"><i>Aviso en proceso…</i></div>`}
    </li>`).join("")}</ul>`;
}

function adjuntosHTML(t, token) {
  if (!t.adjuntos.length) return "<p class='ayuda'>Sin adjuntos.</p>";
  return "<ul>" + t.adjuntos.map((a) =>
    `<li><a href="#" data-adj="${a.id}" data-folio="${esc(t.folio)}" data-quien="${token}">${esc(a.nombre)}</a> (${Math.round(a.tamano / 1024)} KB)</li>`).join("") + "</ul>";
}

async function descargar(ruta, token, nombre) {
  try {
    const blob = await api(ruta, { token: estado[token], crudo: true });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = nombre || ""; a.target = "_blank";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (e) { aviso(e.message, true); }
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-adj]");
  if (!a) return;
  e.preventDefault();
  descargar(`/api/tramites/${a.dataset.folio}/adjuntos/${a.dataset.adj}`, a.dataset.quien, "");
});

// ---------------- Ciudadano ----------------
$("#f-c-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  if (!d.email) delete d.email;
  if (!d.telefono) delete d.telefono;
  try {
    const r = await api("/api/auth/ciudadano", { metodo: "POST", json: d });
    estado.c = r.token; estado.cNombre = `${r.nombre} (${r.rut})`; guardarSesion();
    mostrarCiudadano();
  } catch (err) { aviso(err.message, true); }
});
$("#c-salir").addEventListener("click", () => { estado.c = null; guardarSesion(); mostrarCiudadano(); });
$("#c-refrescar").addEventListener("click", () => listarCiudadano());

$("#f-nuevo").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  if (!d.detalle) delete d.detalle;
  try {
    const t = await api("/api/tramites", { token: estado.c, metodo: "POST", json: d });
    aviso(`Trámite creado con folio ${t.folio}. Adjunte al menos un documento.`);
    e.target.reset();
    await listarCiudadano();
    verCiudadano(t.folio);
  } catch (err) { aviso(err.message, true); }
});

async function mostrarCiudadano() {
  const dentro = !!estado.c;
  $("#c-login").classList.toggle("oculto", dentro);
  $("#c-panel").classList.toggle("oculto", !dentro);
  if (!dentro) return;
  $("#c-quien").textContent = "Sesión: " + (estado.cNombre || "");
  if (!$("#sel-tipo").options.length) {
    const tipos = await api("/api/tipos");
    $("#sel-tipo").innerHTML = tipos.map((t) => `<option value="${t.codigo}">${esc(t.nombre)}</option>`).join("");
  }
  listarCiudadano();
}

async function listarCiudadano() {
  try {
    const lista = await api("/api/tramites", { token: estado.c });
    $("#c-lista").innerHTML = lista.map((t) => `<tr data-folio="${esc(t.folio)}"><td>${esc(t.folio)}</td><td>${esc(t.tipo_nombre)}</td>
      <td><span class="estado ${t.estado}">${t.estado}</span></td><td>${fecha(t.actualizado)}</td></tr>`).join("")
      || "<tr><td colspan='4'>Sin trámites.</td></tr>";
    $("#c-lista").querySelectorAll("tr[data-folio]").forEach((tr) => tr.addEventListener("click", () => verCiudadano(tr.dataset.folio)));
  } catch (err) { manejarSesion(err, "c"); }
}

async function verCiudadano(folio) {
  try {
    const t = await api(`/api/tramites/${folio}`, { token: estado.c });
    const abierto = !["APROBADO", "RECHAZADO"].includes(t.estado);
    $("#c-detalle").classList.remove("oculto");
    $("#c-detalle").innerHTML = `
      <h2>${esc(t.folio)} <span class="estado ${t.estado}">${t.estado}</span></h2>
      <p>${esc(t.tipo_nombre)}</p>
      <h3>Adjuntos</h3>${adjuntosHTML(t, "c")}
      ${abierto ? `<form id="f-adj" class="grid"><label>Archivo (PDF, PNG o JPEG, máx. 5 MB)
        <input type="file" name="archivo" accept=".pdf,.png,.jpg,.jpeg" required></label><button>Subir</button></form>` : ""}
      ${t.estado === "OBSERVADO" ? `<h3>Subsanar observación</h3><form id="f-sub" class="grid">
        <label class="ancho">Comentario <input name="comentario" required minlength="3"></label><button class="warn">Enviar subsanación</button></form>` : ""}
      ${t.estado === "APROBADO" ? `<div class="acciones"><button class="ok" id="b-cert">Descargar certificado PDF</button></div>` : ""}
      <h3>Historial y avisos</h3>${historialHTML(t)}
      <div class="acciones"><button class="sec chico" id="b-recargar">Actualizar</button></div>`;
    $("#b-recargar").onclick = () => verCiudadano(folio);
    const fa = $("#f-adj");
    if (fa) fa.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/api/tramites/${folio}/adjuntos`, { token: estado.c, metodo: "POST", form: new FormData(fa) });
        aviso("Adjunto subido."); verCiudadano(folio);
      } catch (err) { aviso(err.message, true); }
    };
    const fs = $("#f-sub");
    if (fs) fs.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/api/tramites/${folio}/subsanar`, { token: estado.c, metodo: "POST", json: Object.fromEntries(new FormData(fs)) });
        aviso("Subsanación enviada."); listarCiudadano(); verCiudadano(folio);
      } catch (err) { aviso(err.message, true); }
    };
    const bc = $("#b-cert");
    if (bc) bc.onclick = () => descargar(`/api/tramites/${folio}/certificado`, "c", `certificado-${folio}.pdf`);
  } catch (err) { manejarSesion(err, "c"); }
}

// ---------------- Funcionario ----------------
$("#f-f-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  try {
    const r = await api("/api/auth/funcionario", { metodo: "POST", json: d });
    estado.f = r.token; estado.fNombre = d.usuario; guardarSesion();
    mostrarFuncionario();
  } catch (err) { aviso(err.message, true); }
});
$("#f-salir").addEventListener("click", () => { estado.f = null; guardarSesion(); mostrarFuncionario(); });
$("#f-refrescar").addEventListener("click", () => { reporte(); listarFuncionario(); });
$("#f-filtro").addEventListener("change", () => listarFuncionario());

function mostrarFuncionario() {
  const dentro = !!estado.f;
  $("#f-login").classList.toggle("oculto", dentro);
  $("#f-panel").classList.toggle("oculto", !dentro);
  if (!dentro) return;
  $("#f-quien").textContent = "Funcionario: " + (estado.fNombre || "");
  reporte(); listarFuncionario();
}

async function reporte() {
  try {
    const r = await api("/api/reportes/resumen", { token: estado.f });
    const kpi = (n, t) => `<div class="kpi"><b>${n}</b><span>${esc(t)}</span></div>`;
    $("#f-reporte").innerHTML = kpi(r.total_tramites, "Trámites")
      + ["RECIBIDO", "EN_REVISION", "OBSERVADO", "APROBADO", "RECHAZADO"].map((e) => kpi(r.por_estado[e] || 0, e)).join("")
      + kpi(r.tasa_aprobacion == null ? "—" : Math.round(r.tasa_aprobacion * 100) + "%", "Tasa de aprobación")
      + kpi(r.avisos_por_origen.gemini || 0, "Avisos Gemini")
      + kpi(r.avisos_por_origen.plantilla || 0, "Avisos plantilla");
  } catch (err) { manejarSesion(err, "f"); }
}

async function listarFuncionario() {
  try {
    const f = $("#f-filtro").value;
    const lista = await api("/api/tramites" + (f ? `?estado=${f}` : ""), { token: estado.f });
    $("#f-lista").innerHTML = lista.map((t) => `<tr data-folio="${esc(t.folio)}"><td>${esc(t.folio)}</td><td>${esc(t.tipo_nombre)}</td>
      <td>${esc(t.rut)}</td><td>${esc(t.nombre)}</td><td><span class="estado ${t.estado}">${t.estado}</span></td></tr>`).join("")
      || "<tr><td colspan='5'>Sin trámites.</td></tr>";
    $("#f-lista").querySelectorAll("tr[data-folio]").forEach((tr) => tr.addEventListener("click", () => verFuncionario(tr.dataset.folio)));
  } catch (err) { manejarSesion(err, "f"); }
}

async function verFuncionario(folio) {
  try {
    const t = await api(`/api/tramites/${folio}`, { token: estado.f });
    $("#f-detalle").classList.remove("oculto");
    $("#f-detalle").innerHTML = `
      <h2>${esc(t.folio)} <span class="estado ${t.estado}">${t.estado}</span></h2>
      <p>${esc(t.tipo_nombre)} · ${esc(t.nombre)} (${esc(t.rut)}) ${t.detalle ? "· " + esc(t.detalle) : ""}</p>
      <h3>Adjuntos</h3>${adjuntosHTML(t, "f")}
      <div class="acciones">
        ${t.estado === "RECIBIDO" ? `<button id="b-tomar">Tomar trámite</button>` : ""}
        <button class="sec" id="b-ant">Consultar antecedentes (GEPOL / B3000)</button>
      </div>
      <div id="antecedentes"></div>
      ${t.estado === "EN_REVISION" ? `<h3>Decisión</h3>
        <label>Observación o motivo (obligatorio para observar o rechazar)<textarea id="obs" rows="2"></textarea></label>
        <div class="acciones">
          <button class="ok" data-dec="APROBADO">Aprobar</button>
          <button class="warn" data-dec="OBSERVADO">Observar</button>
          <button class="bad" data-dec="RECHAZADO">Rechazar</button>
        </div>` : ""}
      <h3>Historial y avisos</h3>${historialHTML(t)}
      <div class="acciones"><button class="sec chico" id="b-frecargar">Actualizar</button></div>`;
    $("#b-frecargar").onclick = () => verFuncionario(folio);
    const bt = $("#b-tomar");
    if (bt) bt.onclick = async () => {
      try { await api(`/api/tramites/${folio}/tomar`, { token: estado.f, metodo: "POST" }); aviso("Trámite tomado."); refrescarF(folio); }
      catch (err) { aviso(err.message, true); }
    };
    $("#b-ant").onclick = async () => {
      try {
        const a = await api(`/api/tramites/${folio}/antecedentes`, { token: estado.f });
        $("#antecedentes").innerHTML = `<h3>Antecedentes (datos sintéticos)</h3><pre>${esc(JSON.stringify({ gepol: a.gepol, b3000: a.b3000 }, null, 2))}</pre>`;
      } catch (err) { aviso(err.message, true); }
    };
    document.querySelectorAll("[data-dec]").forEach((b) => b.onclick = async () => {
      const observacion = $("#obs").value.trim();
      try {
        await api(`/api/tramites/${folio}/decision`, { token: estado.f, metodo: "POST", json: { resultado: b.dataset.dec, observacion: observacion || null } });
        aviso(`Decisión registrada: ${b.dataset.dec}.`); refrescarF(folio);
      } catch (err) { aviso(err.message, true); }
    });
  } catch (err) { manejarSesion(err, "f"); }
}

function refrescarF(folio) { reporte(); listarFuncionario(); verFuncionario(folio); }

function manejarSesion(err, quien) {
  if (/token|sesión|Falta/i.test(err.message)) {
    estado[quien] = null; guardarSesion();
    quien === "c" ? mostrarCiudadano() : mostrarFuncionario();
  }
  aviso(err.message, true);
}

cargarSesion();
mostrarCiudadano();
mostrarFuncionario();
