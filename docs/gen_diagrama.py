# -*- coding: utf-8 -*-
import html, sys
OUT = "diagrama_poc_grande"
A = "img/lib/azure2/"
TITLE = "ARQUITECTURA DE LA PoC EN GOOGLE CLOUD — PDI TRÁMITES MIGRATORIOS"
SUBTITLE = "Laboratorio 3 · desplegada con Terraform · ambiente dev"
FOOTNOTE = "SUPUESTOS — CIDR y reglas de NSG son una propuesta del grupo (ambiente dev, VPC 10.30.0.0/16). En GCP los NSG son las reglas de firewall de la VPC. Simulado en la PoC: ClaveÚnica (RUT con módulo 11 dentro del gestor), GEPOL y B3000 (datos sintéticos) y mensajería (solo log). No desplegado: HA VPN, Firewall PDI, Cloud NAT y la PDI real. Secret Manager, Artifact Registry y Logging los usan todos los servicios de Cloud Run (flechas omitidas para no saturar). La IA solo redacta el aviso, nunca decide el trámite."
N = {
 "ciud":   (140, 310, "Ciudadano", "Inicia y consulta", A+"identity/Users.svg", "USR", "act"),
 "func":   (140, 540, "Funcionario PDI", "Revisa y decide", A+"identity/Users.svg", "FUN", "act"),
 "lb":     (1100, 310, "Cloud Armor + LB", "Opcional · HTTP global", A+"networking/Load_Balancers.svg", "LB", "opt"),
 "portal": (700, 310, "Portal web", "Cloud Run · nginx", A+"app_services/App_Services.svg", "APP", "cmp"),
 "adapt":  (520, 695, "Adaptadores PDI", "Simulado · GEPOL y B3000", A+"integration/API_Connections.svg", "API", "cmp"),
 "gestor": (960, 695, "Gestor de trámites", "Cloud Run · API + login", A+"app_services/App_Services.svg", "APP", "cmp"),
 "notif":  (1400, 695, "Notificaciones", "Cloud Run · aviso con IA", A+"app_services/App_Services.svg", "APP", "cmp"),
 "storage":(520, 1080, "Cloud Storage", "Adjuntos · privado", A+"storage/Storage_Accounts.svg", "BLOB", "dat"),
 "tasks":  (960, 1080, "Cloud Tasks", "Cola de avisos · OIDC", A+"integration/Service_Bus.svg", "Q", "sec"),
 "sql":    (1400, 1080, "Cloud SQL", "PostgreSQL 15 · privada", A+"databases/Azure_Database_PostgreSQL_Server.svg", "SQL", "dat"),
 "sec":    (520, 1465, "Secret Manager", "BD, JWT y claves", A+"security/Key_Vaults.svg", "KEY", "ops"),
 "reg":    (960, 1465, "Artifact Registry", "+ Cloud Build", A+"containers/Container_Registries.svg", "REG", "ops"),
 "log":    (1400, 1465, "Cloud Logging", "Logs y métricas", A+"management_governance/Monitor.svg", "MON", "ops"),
 "nat":    (700, 1850, "Cloud NAT", "No desplegado · solo PROD", A+"networking/NAT.svg", "NAT", "opt"),
 "vpn":    (1300, 1850, "HA VPN + Firewall", "No desplegado en la PoC", A+"networking/Virtual_Network_Gateways.svg", "VPN", "opt"),
 "pdi":    (1960, 1850, "PDI on-premise", "GEPOL y B3000 reales", A+"databases/SQL_Server.svg", "PDI", "opt"),
 "msg":    (1960, 425, "Proveedor de mensajes", "Simulado · solo log", A+"integration/Event_Grid_Topics.svg", "MSG", "opt"),
 "gem":    (1960, 695, "Gemini en Vertex AI", "gemini-3.5-flash-lite", A+"ai_machine_learning/Cognitive_Services.svg", "IA", "ext"),
}
Z = {
 "z_act":  (20, 110, 260, 740, "ACTORES", "zone"),
 "z_cloud":(290, 40, 1700, 2110, "GOOGLE CLOUD · southamerica-west1", "cloud"),
 "z_vnet": (310, 100, 1680, 2080, "VPC pdi-tramites-dev · 10.30.0.0/16", "vnet"),
 "s_edge": (330, 170, 1660, 510, "snet-edge · 10.30.1.0/24", "subnet"),
 "s_app":  (330, 555, 1660, 895, "snet-app · 10.30.2.0/24", "subnet"),
 "s_data": (330, 940, 1660, 1280, "snet-data · 10.30.3.0/24", "subnet"),
 "s_ops":  (330, 1325, 1660, 1665, "snet-ops · 10.30.4.0/24", "subnet"),
 "s_hyb":  (330, 1710, 1660, 2050, "snet-hybrid · 10.30.5.0/24", "subnet"),
 "z_ext":  (1760, 295, 2160, 955, "SERVICIOS EXTERNOS", "ext"),
 "z_pdi":  (1760, 1710, 2160, 2050, "PDI (FUTURO)", "onprem"),
}
NSG = {"s_edge": "nsg-edge", "s_app": "nsg-app", "s_data": "nsg-data", "s_ops": "nsg-ops", "s_hyb": "nsg-hybrid"}
SUBNETS = [
 ("snet-edge", "10.30.1.0/24", "nsg-edge", "Portal web, Cloud Armor + LB (opcional)", "Entrada pública HTTPS. El resto del ingreso se deniega"),
 ("snet-app", "10.30.2.0/24", "nsg-app", "Gestor, Notificaciones y Adaptadores (Direct VPC egress)", "Egreso a Cloud SQL por tcp/5432. Se bloquean los demás rangos privados"),
 ("snet-data", "10.30.3.0/24", "nsg-data", "Cloud SQL (peering privado), Cloud Storage y Cloud Tasks", "Solo desde snet-app. Ingreso denegado por defecto"),
 ("snet-ops", "10.30.4.0/24", "nsg-ops", "Secret Manager, Artifact Registry con Cloud Build y Logging", "Solo desde subredes internas"),
 ("snet-hybrid", "10.30.5.0/24", "nsg-hybrid", "Cloud NAT y HA VPN (no desplegados en la PoC)", "Solo hacia el rango on-premise vía VPN"),
]
K, BL, PU, OR, TE, GR = "#333333", "#0078D4", "#7030A0", "#E36C0A", "#00838F", "#7F7F7F"
c1 = 507
c2 = 877
E = [
 ("e01", "ciud", "lb", "HTTP", (GR, 1), ("vhv", 232)),
 ("e02", "ciud", "portal", "HTTPS", (K, 0), None),
 ("e03", "func", "portal", "", (K, 0), ("hvh", 275)),
 ("e04", "lb", "gestor", "/api/*", (GR, 1), ("vhv", c1)),
 ("e05", "portal", "gestor", "REST", (K, 0), ("vhv", c1)),
 ("e06", "gestor", "adapt", "antecedentes", (K, 0), None),
 ("e07", "gestor", "sql", "", (K, 0), ("vhv", c2)),
 ("e08", "gestor", "storage", "adjuntos", (K, 0), ("vhv", c2)),
 ("e09", "gestor", "tasks", "encola", (K, 0), None),
 ("e10", "tasks", "notif", "OIDC", (BL, 0), ("hvh", 1250)),
 ("e11", "notif", "sql", "", (K, 0), None),
 ("e12", "notif", "gem", "redactar aviso", (PU, 0), None),
 ("e13", "notif", "msg", "log", (GR, 1), ("hvh", 1730)),
 ("e14", "vpn", "pdi", "IPsec (futuro)", (GR, 1), None),
]
LBLPOS = {'e10': (1250, 1050), 'e13': (1845, 545), 'e12': (1600, 815)}
TABLE_X, TABLE_Y = 800, 2170
LEGEND_XY = (20, 2170)

TOP = 120
N = {k: (v[0], v[1]+TOP) + tuple(v[2:]) for k, v in N.items()}
Z = {k: (v[0], v[1]+TOP, v[2], v[3]+TOP) + tuple(v[4:]) for k, v in Z.items()}
def _sh(r):
    if r is None: return None
    if isinstance(r, tuple): return ("vhv", r[1]+TOP) if r[0] == "vhv" else r
    return [(x, y+TOP) for x, y in r]
E = [(a, b, c, d, f, _sh(r)) for a, b, c, d, f, r in E]
TABLE_Y += TOP; LEGEND_XY = (LEGEND_XY[0], LEGEND_XY[1]+TOP)

def pts(e):
    r = e[5]
    if r is None: return []
    x1, y1, x2, y2 = N[e[1]][0], N[e[1]][1], N[e[2]][0], N[e[2]][1]
    if isinstance(r, tuple): return [(x1, r[1]), (x2, r[1])] if r[0] == "vhv" else [(r[1], y1), (r[1], y2)]
    return r
def full(e): return [(N[e[1]][0], N[e[1]][1])] + pts(e) + [(N[e[2]][0], N[e[2]][1])]
def label_pos(P):
    best, bi = -1, 0
    for i in range(len(P)-1):
        L = abs(P[i][0]-P[i+1][0]) + abs(P[i][1]-P[i+1][1])
        if L > best: best, bi = L, i
    (xa, ya), (xb, yb) = P[bi], P[bi+1]
    if bi == 0 and xa == xb and yb > ya: ya += 70
    return ((xa+xb)/2, (ya+yb)/2)
esc = lambda s: html.escape(s, quote=True)

W = max(z[2] for z in Z.values()) + 80; H = TABLE_Y + 700
o = ['<mxfile host="app.diagrams.net"><diagram id="arq" name="Arquitectura"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="%d" pageHeight="%d" math="0" shadow="0" background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>' % (W, H)]
o.append('<mxCell id="title" value="%s" style="text;html=1;align=left;verticalAlign=middle;fontSize=32;fontStyle=1;fontColor=#1F3864;" vertex="1" parent="1"><mxGeometry x="20" y="0" width="2100" height="60" as="geometry"/></mxCell>' % esc(TITLE+" · "+SUBTITLE))
zs = {"zone": "fillColor=#FFFBE6;strokeColor=#BF9000;dashed=0", "cloud": "fillColor=#EAF3FC;strokeColor=#4285F4;dashed=1",
      "vnet": "fillColor=#DCEBFA;strokeColor=#0078D4;dashed=1;strokeWidth=2", "subnet": "fillColor=#FFFFFF;strokeColor=#0078D4;dashed=1;dashPattern=6 4",
      "ext": "fillColor=#F5EEFA;strokeColor=#7030A0;dashed=1", "onprem": "fillColor=#F2F2F2;strokeColor=#595959;dashed=1"}
for k, (x1, y1, x2, y2, t, kind) in Z.items():
    o.append('<mxCell id="%s" value="%s" style="rounded=1;arcSize=2;whiteSpace=wrap;html=1;%s;verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontStyle=1;fontSize=28;fontColor=#1F3864;" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>' % (k, esc(t), zs[kind], x1, y1, x2-x1, y2-y1))
for k, nsg in NSG.items():
    x1, y1, x2, y2, _, _ = Z[k]
    o.append('<mxCell id="nsg_%s" value="%s" style="image;aspect=fixed;html=1;image=%snetworking/Network_Security_Groups.svg;verticalLabelPosition=middle;verticalAlign=middle;labelPosition=left;align=right;fontSize=24;fontColor=#0078D4;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="60" height="70" as="geometry"/></mxCell>' % (k, esc("NSG · "+nsg), A, x2-90, y1+10))
for e in E:
    eid, s, d, lab, (col, dash), _ = e
    st = "edgeStyle=none;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=4;strokeColor=%s;fontSize=22;labelBackgroundColor=#FFFFFF;" % col + ("dashed=1;dashPattern=8 6;" if dash else "")
    p = pts(e); arr = '<Array as="points">' + "".join('<mxPoint x="%d" y="%d"/>' % q for q in p) + '</Array>' if p else ""
    o.append('<mxCell id="%s" value="%s" style="%s" edge="1" parent="1" source="%s" target="%s"><mxGeometry relative="1" as="geometry">%s</mxGeometry></mxCell>' % (eid, esc(lab), st, s, d, arr))
for k, (x, y, t, sub, ic, ab, cat) in N.items():
    val = '<b>%s</b><br><font style="font-size:20px" color="#555555">%s</font>' % (t, sub)
    base = (ic + ";html=1;aspect=fixed;fillColor=#2072B8;strokeColor=none") if ic.startswith("shape=") else ("image;aspect=fixed;html=1;image=" + ic)
    o.append('<mxCell id="%s" value="%s" style="%s;verticalLabelPosition=bottom;verticalAlign=top;fontSize=26;labelBackgroundColor=#FFFFFF;%s" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="120" height="120" as="geometry"/></mxCell>' % (k, esc(val), base, "opacity=70;" if cat == "opt" else "", x-60, y-60))
leg = "<b>LÍNEAS DEL DIAGRAMA</b><br>Continua: flujo implementado<br>Discontinua: opcional o simulado<br>Azul: identidad OIDC · Morado: IA<br>Recuadro punteado azul: subred (con su NSG)"
o.append('<mxCell id="legend" value="%s" style="rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#7F7F7F;spacingLeft=12;fontSize=22;" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="520" height="240" as="geometry"/></mxCell>' % (esc(leg), LEGEND_XY[0], LEGEND_XY[1]))
tbl = "<b>SUBREDES Y NSG (propuesta preliminar)</b><br>" + "<br>".join("<b>%s</b> %s · %s: %s. %s." % (a, b, c, d, e_) for a, b, c, d, e_ in SUBNETS) + "<br>Cada subred tiene su propio NSG."
o.append('<mxCell id="subtbl" value="%s" style="rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#0078D4;spacingLeft=12;fontSize=22;" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="1360" height="%d" as="geometry"/></mxCell>' % (esc(tbl), TABLE_X, TABLE_Y, 90+60*len(SUBNETS)))
o.append('<mxCell id="sup" value="%s" style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=20;fontColor=#444444;" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="1500" height="220" as="geometry"/></mxCell>' % (esc(FOOTNOTE), TABLE_X, TABLE_Y+150+60*len(SUBNETS)))
o.append('</root></mxGraphModel></diagram></mxfile>')
open(OUT+".drawio", "w", encoding="utf-8").write("\n".join(o))

S = 0.0185
X = lambda x: x*S
Y = lambda y: -y*S
def tex(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"), ("→", r"$\rightarrow$"), ("·", r"$\cdot$"), ("—", "---"), ("–", "--")]: s = s.replace(a, b)
    return s
colcat = {"act": "FFC000", "cmp": "0078D4", "sec": "E36C0A", "dat": "2E9E4F", "ext": "7030A0", "ops": "7F7F7F", "inf": "00838F", "opt": "A6A6A6"}
T = [r"\documentclass[tikz,border=12pt]{standalone}", r"\usepackage[utf8]{inputenc}", r"\usepackage[T1]{fontenc}", r"\usepackage{helvet}", r"\renewcommand{\familydefault}{\sfdefault}", r"\usetikzlibrary{arrows.meta,positioning,calc,shapes.misc}"]
T += [r"\definecolor{c%s}{HTML}{%s}" % (c, h) for c, h in colcat.items()]
T.append(r"""\definecolor{azure}{HTML}{0078D4}\definecolor{navy}{HTML}{1F3864}
\tikzset{tile/.style={rounded corners=3pt,minimum size=2.4cm,inner sep=0pt,text=white,font=\bfseries\huge,draw=white,line width=.6pt},
 lab/.style={align=center,text width=8cm,font=\LARGE,inner sep=1pt,anchor=north,fill=white,fill opacity=0.9,text opacity=1},
 flow/.style={-{Stealth[length=5mm]},line width=2.4pt,rounded corners=3pt},
 elab/.style={fill=white,inner sep=1.2pt,font=\Large,text=black}}
\begin{document}
\begin{tikzpicture}[x=1cm,y=1cm]""")
T.append(r"\node[anchor=west,font=\Huge\bfseries,text=navy] at (%.2f,%.2f) {%s};" % (X(20), Y(25), tex(TITLE)))
T.append(r"\node[anchor=west,font=\huge,text=gray] at (%.2f,%.2f) {%s};" % (X(20), Y(85), tex(SUBTITLE)))
zst = {"zone": "fill=yellow!10,draw=orange!60!black", "cloud": "fill=blue!5,draw=blue!60,dashed", "vnet": "fill=azure!12,draw=azure,dashed,line width=1.2pt", "subnet": "fill=white,draw=azure,dash pattern=on 4pt off 3pt", "ext": "fill=violet!6,draw=violet!70,dashed", "onprem": "fill=gray!10,draw=gray!70,dashed"}
for k, (x1, y1, x2, y2, t, kind) in Z.items():
    T.append(r"\draw[rounded corners=4pt,%s] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (zst[kind], X(x1), Y(y1), X(x2), Y(y2)))
    T.append(r"\node[anchor=north west,font=\huge\bfseries,text=navy] at (%.2f,%.2f) {%s};" % (X(x1)+0.2, Y(y1)-0.1, tex(t)))
for k, nsg in NSG.items():
    x1, y1, x2, y2, _, _ = Z[k]
    T.append(r"\node[tile,minimum width=2.2cm,minimum height=1.2cm,fill=azure,font=\bfseries\Large,anchor=north east] at (%.2f,%.2f) {NSG};" % (X(x2)-0.2, Y(y1)-0.15))
    T.append(r"\node[anchor=east,fill=white,inner sep=3pt,font=\huge\bfseries,text=azure] at (%.2f,%.2f) {%s};" % (X(x2)-2.8, Y(y1)-0.75, tex("NSG: "+nsg)))
for e in E:
    eid, s, d, lab, (col, dash), _ = e
    P = full(e); path = " -- ".join("(%.2f,%.2f)" % (X(a), Y(b)) for a, b in P); h = col[1:]
    T.append(r"\draw[flow,color={rgb,255:red,%d;green,%d;blue,%d}%s,shorten >=1.35cm,shorten <=1.35cm] %s;" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), ",dashed" if dash else "", path))
    if lab:
        lx, ly = LBLPOS.get(eid) or label_pos(P); T.append(r"\node[elab] at (%.2f,%.2f) {%s};" % (X(lx), Y(ly), tex(lab)))
for k, (x, y, t, sub, ic, ab, cat) in N.items():
    T.append(r"\node[tile,fill=c%s%s] (%s) at (%.2f,%.2f) {%s};" % (cat, ",dashed" if cat == "opt" else "", k, X(x), Y(y), ab))
    T.append(r"\node[lab] at (%.2f,%.2f) {\textbf{%s}\\[-1pt]{\Large\color{gray!70!black}%s}};" % (X(x), Y(y)-1.4, tex(t), tex(sub)))
NS=[t for t in T if "{NSG};" in t or "text=azure]" in t]
T=[t for t in T if t not in NS]+NS
T.append(r"\node[draw=gray,rounded corners=3pt,fill=white,align=left,font=\LARGE,anchor=north west,inner sep=10pt] at (%.2f,%.2f) {\textbf{LÍNEAS DEL DIAGRAMA}\\Continua: flujo implementado\\Discontinua: opcional o simulado\\Azul: identidad OIDC $\cdot$ Morado: IA\\Recuadro punteado azul: subred (con NSG)};" % (X(LEGEND_XY[0]), Y(LEGEND_XY[1])))
rows = " ".join("%s&%s&%s&%s&%s\\\\\\hline" % tuple(tex(c) for c in r) for r in SUBNETS)
T.append(r"\node[anchor=north west,inner sep=0pt] (tbl) at (%.2f,%.2f) {\LARGE\renewcommand{\arraystretch}{1.4}\begin{tabular}{|l|l|l|p{10.5cm}|p{11.5cm}|}\hline \textbf{Subred}&\textbf{CIDR}&\textbf{NSG}&\textbf{Componentes}&\textbf{Regla principal (propuesta)}\\\hline %s \end{tabular}};" % (X(TABLE_X), Y(TABLE_Y), rows))
T.append(r"\node[anchor=north west,font=\LARGE,text=gray!60!black] (n1) at ([yshift=-0.3cm]tbl.south west) {Cada subred tiene su propio NSG. CIDR y reglas son una propuesta preliminar.};")
T.append(r"\node[anchor=north west,font=\LARGE,text=gray!60!black,text width=34cm] at ([yshift=-0.3cm]n1.south west) {%s};" % tex(FOOTNOTE))
T.append(r"\end{tikzpicture}\end{document}")
open(OUT+".tex", "w", encoding="utf-8").write("\n".join(T))
print("ok:", len(N), "nodos,", len(E), "flechas ->", OUT+".drawio /", OUT+".tex")
