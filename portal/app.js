"use strict";
const API = (window.PDI_CONFIG && window.PDI_CONFIG.API_URL) || "";
const $ = (id) => document.getElementById(id);
const sesion = { ciudadano: null, funcionario: null };

// ------------------------------------------------------------ utilidades
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fecha = (iso) => new Date(iso).toLocaleString("es-CL");
const chip = (e) => `<span class="estado ${esc(e)}">${esc(e)}</span>`;

function aviso(texto, tipo = "") {
  const m = $("mensaje");
  m.textContent = texto; m.className = tipo; m.hidden = !texto;
  if (texto) window.scrollTo({ top: 0, behavior: "smooth" });
}

async function api(ruta, { metodo = "GET", cuerpo, archivo, token, blob } = {}) {
  const opciones = { method: metodo, headers: {} };
  if (token) opciones.headers.Authorization = `Bearer ${token}`;
  if (cuerpo) { opciones.headers["Content-Type"] = "application/json"; opciones.body = JSON.stringify(cuerpo); }
  if (archivo) { const f = new FormData(); f.append("archivo", archivo); opciones.body = f; }
  const r = await fetch(API + ruta, opciones);
  if (!r.ok) {
    let detalle = r.statusText;
    try { const j = await r.json(); detalle = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (_) {}
    throw new Error(`${r.status}: ${detalle}`);
  }
  return blob ? r.blob() : r.json();
}

const intentar = (fn) => async (...a) => { try { aviso(""); await fn(...a); } catch (e) { aviso(e.message, "error"); } };

// ------------------------------------------------------------ pestañas
function pestana(cual) {
  $("vista-ciudadano").hidden = cual !== "ciudadano";
  $("vista-funcionario").hidden = cual !== "funcionario";
  $("tab-ciudadano").classList.toggle("activo", cual === "ciudadano");
  $("tab-funcionario").classList.toggle("activo", cual === "funcionario");
  aviso("");
}
$("tab-ciudadano").onclick = () => pestana("ciudadano");
$("tab-funcionario").onclick = () => pestana("funcionario");
$("ambiente").textContent = `ambiente ${(window.PDI_CONFIG && window.PDI_CONFIG.ENV_NAME) || "local"}`;

// ------------------------------------------------------------ ciudadano
$("form-c-login").onsubmit = intentar(async (ev) => {
  ev.preventDefault();
  const r = await api("/auth/ciudadano", { metodo: "POST", cuerpo: { rut: $("c-rut").value } });
  sesion.ciudadano = r.token;
  $("c-quien").textContent = `RUT ${r.rut}`;
  $("c-login").hidden = true; $("c-app").hidden = false;
  await listarCiudadano();
  const folio = new URLSearchParams(location.search).get("folio");
  if (folio) await verCiudadano(folio);
});

$("form-nuevo").onsubmit = intentar(async (ev) => {
  ev.preventDefault();
  const r = await api("/tramites", { metodo: "POST", token: sesion.ciudadano,
    cuerpo: { tipo: $("n-tipo").value, nombre: $("n-nombre").value, email: $("n-email").value } });
  aviso(`Solicitud recibida. Tu folio es ${r.folio}. Ahora adjunta tus antecedentes.`, "exito");
  await listarCiudadano();
  await verCiudadano(r.folio);
});

async function listarCiudadano() {
  const filas = await api("/mis-tramites", { token: sesion.ciudadano });
  $("c-lista").querySelector("tbody").innerHTML = filas.map((t) =>
    `<tr><td>${esc(t.folio)}</td><td>${esc(t.tipo_nombre)}</td><td>${chip(t.estado)}</td>
     <td><button class="sec chico" data-folio="${esc(t.folio)}">Ver</button></td></tr>`).join("")
    || `<tr><td colspan="4">Aún no tienes trámites.</td></tr>`;
  $("c-lista").querySelectorAll("button[data-folio]").forEach((b) => b.onclick = intentar(() => verCiudadano(b.dataset.folio)));
}

async function verCiudadano(folio) {
  const t = await api(`/tramites/${encodeURIComponent(folio)}`, { token: sesion.ciudadano });
  const puedeAdjuntar = ["RECIBIDO", "OBSERVADO"].includes(t.estado);
  $("c-detalle").hidden = false;
  $("c-detalle").innerHTML = `
    <h2>${esc(t.folio)} ${chip(t.estado)}</h2>
    <p>${esc(t.tipo_nombre)} · creado ${fecha(t.creado_en)}</p>
    ${t.observacion ? `<p><b>Observación del funcionario:</b> ${esc(t.observacion)}</p>` : ""}
    ${puedeAdjuntar ? `<div class="fila"><input type="file" id="c-archivo" accept=".pdf,.png,.jpg,.jpeg">
        <button id="c-subir">Adjuntar</button></div>` : ""}
    ${t.estado === "OBSERVADO" ? `<div class="fila" style="margin-top:8px"><input id="c-coment" placeholder="¿Qué corregiste?" size="40">
        <button id="c-subsanar" class="alerta">Enviar subsanación</button></div>` : ""}
    ${t.estado === "APROBADO" ? `<button id="c-cert" class="ok">Descargar certificado</button>` : ""}
    <h3>Adjuntos</h3>${t.adjuntos.map((a) => `<div class="linea">${esc(a.nombre)} (${Math.round(a.tamano / 1024)} KB)</div>`).join("") || "<p>Sin adjuntos.</p>"}
    <h3>Historial</h3>${t.historial.map((h) => `<div class="linea"><b>${esc(h.estado)}</b> · ${fecha(h.fecha)} · ${esc(h.actor)}<br>${esc(h.detalle)}</div>`).join("")}
    <h3>Avisos enviados</h3>${t.avisos.map((a) => `<div class="aviso"><b>${esc(a.estado)}</b> · ${esc(a.canal)} · redactado por ${esc(a.generado_por)}<br>${esc(a.mensaje)}</div>`).join("") || "<p>Aún no hay avisos (llegan en unos segundos).</p>"}
    <button id="c-recargar" class="sec">Actualizar</button>`;
  const on = (id, fn) => { const e = $(id); if (e) e.onclick = intentar(fn); };
  on("c-recargar", () => verCiudadano(folio));
  on("c-subir", async () => {
    const f = $("c-archivo").files[0]; if (!f) throw new Error("Elige un archivo");
    await api(`/tramites/${encodeURIComponent(folio)}/adjuntos`, { metodo: "POST", token: sesion.ciudadano, archivo: f });
    aviso("Adjunto recibido", "exito"); await verCiudadano(folio);
  });
  on("c-subsanar", async () => {
    await api(`/tramites/${encodeURIComponent(folio)}/subsanar`, { metodo: "POST", token: sesion.ciudadano, cuerpo: { comentario: $("c-coment").value } });
    aviso("Subsanación enviada", "exito"); await listarCiudadano(); await verCiudadano(folio);
  });
  on("c-cert", () => descargar(folio, sesion.ciudadano));
}

async function descargar(folio, token) {
  const b = await api(`/tramites/${encodeURIComponent(folio)}/certificado`, { token, blob: true });
  const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `${folio}.pdf`; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

// ------------------------------------------------------------ funcionario
$("form-f-login").onsubmit = intentar(async (ev) => {
  ev.preventDefault();
  const r = await api("/auth/funcionario", { metodo: "POST", cuerpo: { clave: $("f-clave").value } });
  sesion.funcionario = r.token;
  $("f-login").hidden = true; $("f-app").hidden = false;
  await listarFuncionario();
});

async function listarFuncionario() {
  const q = $("f-filtro").value ? `?estado=${encodeURIComponent($("f-filtro").value)}` : "";
  const filas = await api(`/funcionario/tramites${q}`, { token: sesion.funcionario });
  $("f-lista").querySelector("tbody").innerHTML = filas.map((t) =>
    `<tr><td>${esc(t.folio)}</td><td>${esc(t.tipo_nombre)}</td><td>${esc(t.nombre)}<br><small>${esc(t.rut)}</small></td>
     <td>${chip(t.estado)}</td><td><button class="sec chico" data-folio="${esc(t.folio)}">Abrir</button></td></tr>`).join("")
    || `<tr><td colspan="5">No hay solicitudes.</td></tr>`;
  $("f-lista").querySelectorAll("button[data-folio]").forEach((b) => b.onclick = intentar(() => verFuncionario(b.dataset.folio)));
}
$("f-refrescar").onclick = intentar(listarFuncionario);
$("f-filtro").onchange = intentar(listarFuncionario);

async function verFuncionario(folio, extra = "") {
  const t = await api(`/tramites/${encodeURIComponent(folio)}`, { token: sesion.funcionario });
  $("f-detalle").hidden = false;
  $("f-detalle").innerHTML = `
    <h2>${esc(t.folio)} ${chip(t.estado)}</h2>
    <p>${esc(t.tipo_nombre)} · ${esc(t.nombre)} (${esc(t.rut)}) · ${esc(t.email)}</p>
    <div class="fila">
      ${t.estado === "RECIBIDO" ? `<button id="f-tomar">Tomar solicitud</button>` : ""}
      <button id="f-ant" class="sec">Consultar antecedentes (simulado)</button>
      ${t.estado === "APROBADO" ? `<button id="f-cert" class="sec">Ver certificado</button>` : ""}
    </div>
    ${t.estado === "EN_REVISION" ? `<div class="fila" style="margin-top:10px">
      <input id="f-coment" placeholder="Comentario / motivo" size="40">
      <button id="f-aprobar" class="ok">Aprobar</button><button id="f-observar" class="alerta">Observar</button>
      <button id="f-rechazar" class="mal">Rechazar</button></div>` : ""}
    <h3>Adjuntos</h3>${t.adjuntos.map((a) => `<div class="linea">${esc(a.nombre)} (${Math.round(a.tamano / 1024)} KB)</div>`).join("") || "<p>Sin adjuntos.</p>"}
    <h3>Historial</h3>${t.historial.map((h) => `<div class="linea"><b>${esc(h.estado)}</b> · ${fecha(h.fecha)} · ${esc(h.actor)}<br>${esc(h.detalle)}</div>`).join("")}
    <h3>Avisos al ciudadano</h3>${t.avisos.map((a) => `<div class="aviso"><b>${esc(a.estado)}</b> · redactado por ${esc(a.generado_por)}<br>${esc(a.mensaje)}</div>`).join("") || "<p>Sin avisos todavía.</p>"}
    ${extra}`;
  const on = (id, fn) => { const e = $(id); if (e) e.onclick = intentar(fn); };
  const decidir = (d) => async () => {
    await api(`/funcionario/tramites/${encodeURIComponent(folio)}/decision`, { metodo: "POST", token: sesion.funcionario,
      cuerpo: { decision: d, comentario: $("f-coment").value } });
    aviso(`Decisión registrada: ${d}`, "exito"); await listarFuncionario(); await verFuncionario(folio);
  };
  on("f-tomar", async () => { await api(`/funcionario/tramites/${encodeURIComponent(folio)}/tomar`, { metodo: "POST", token: sesion.funcionario }); await listarFuncionario(); await verFuncionario(folio); });
  on("f-ant", async () => {
    const r = await api(`/funcionario/tramites/${encodeURIComponent(folio)}/antecedentes`, { metodo: "POST", token: sesion.funcionario });
    await verFuncionario(folio, `<h3>Antecedentes</h3><pre>${esc(JSON.stringify(r, null, 2))}</pre>`);
  });
  on("f-cert", () => descargar(folio, sesion.funcionario));
  on("f-aprobar", decidir("aprobar")); on("f-observar", decidir("observar")); on("f-rechazar", decidir("rechazar"));
}

$("f-reporte").onclick = intentar(async () => {
  const r = await api("/funcionario/reportes/resumen", { token: sesion.funcionario });
  $("f-detalle").hidden = false;
  $("f-detalle").innerHTML = `<h2>Reporte de gestión</h2><pre>${esc(JSON.stringify(r, null, 2))}</pre>`;
});

if (!API) aviso("Falta configurar API_URL en config.js (lo entrega Terraform).", "error");
