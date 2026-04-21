"""
Voltageapp – Batterisystem ROI-Kalkylator
==========================================
Kör med:  python -m streamlit run app.py

Beroenden:
    pip install streamlit plotly reportlab pandas
"""

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ──────────────────────────────────────────────────────────────
# SYSTEMDATABAS  –  verkliga specs från tillverkarnas datablad
# ──────────────────────────────────────────────────────────────
SYSTEMS = {
    "Dyness Stack 100": {
        "tillverkare": "Dyness",
        "kategori": "Budget",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 5.12,
        "moduler": [3, 4, 5, 6, 7, 8, 9, 10],   # 3–10 moduler per torn
        "cykler": 6000,
        "garanti_ar": 10,
        "livslangd_ar": 15,
        "verkningsgrad": 0.95,
        "dod_pct": 100,
        "info": "Stapelbar HV-modul med inbyggt brandsläckningssystem. Plug-and-play, 30 min installationstid. 0 kabeldragning mellan moduler.",
        "saljargument": "Lägst nettoinvestering per kWh → betalar sig snabbast.",
    },
    "Pylontech US5000": {
        "tillverkare": "Pylontech",
        "kategori": "Budget",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 4.8,
        "moduler": [2, 3, 4, 5, 6, 7, 8],        # upp till 8 utan LV-Hub
        "cykler": 6000,
        "garanti_ar": 10,
        "livslangd_ar": 15,
        "verkningsgrad": 0.95,
        "dod_pct": 95,
        "info": "Marknadsledande rackmonterad LFP-modul. Stöds av Victron, GoodWe, Solis m.fl. 10 års garanti vid registrering.",
        "saljargument": "Beprövad teknik, störst installationsbas globalt.",
    },
    "SAJ HS3": {
        "tillverkare": "SAJ",
        "kategori": "Mellanklass",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 5.0,
        "moduler": [2, 3, 4, 5, 6],
        "cykler": 6000,
        "garanti_ar": 10,
        "livslangd_ar": 15,
        "verkningsgrad": 0.94,
        "dod_pct": 95,
        "info": "Integrerat HV-hybridsystem från SAJ. God kompatibilitet och stabil prestanda för mellansegmentet.",
        "saljargument": "Bra balans mellan pris och funktioner.",
    },
    "Huawei LUNA2000": {
        "tillverkare": "Huawei",
        "kategori": "Mellanklass",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 5.0,
        "moduler": [2, 3, 4, 5, 6],
        "cykler": 6000,
        "garanti_ar": 10,
        "livslangd_ar": 15,
        "verkningsgrad": 0.95,
        "dod_pct": 100,
        "info": "Premium hybridlösning med AI-styrning och utmärkt app. Kräver Huawei-växelriktare.",
        "saljargument": "Stark app-integration, välkänt varumärke.",
    },
    "1Komma5 / FoxESS (ECS-serie)": {
        "tillverkare": "FoxESS",
        "kategori": "Mellanklass",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 5.12,
        "moduler": [2, 3, 4, 5, 6, 7, 8],
        "cykler": 6000,
        "garanti_ar": 10,
        "livslangd_ar": 15,
        "verkningsgrad": 0.95,
        "dod_pct": 100,
        "info": "FoxESS ECS-moduler säljs i Sverige under varumärket 1Komma5. Stöd för trefas och smart styrning.",
        "saljargument": "Kompetent system med bra support via 1Komma5-nätverket.",
    },
    "Sigenergy SigenStor": {
        "tillverkare": "Sigenergy",
        "kategori": "Premium",
        "kemi": "LFP (LiFePO₄)",
        "modul_kwh": 9.04,   # BAT-9.0 modulen, den vanligaste i Sverige
        "moduler": [1, 2, 3, 4, 5, 6],  # 1–6 moduler (max ~54 kWh per stack)
        "cykler": 6000,      # tillverkarens uppgift; marknadsförs ibland som "upp till 10 000"
        "garanti_ar": 10,
        "livslangd_ar": 20,
        "verkningsgrad": 0.96,
        "dod_pct": 97,
        "info": "5-i-1 system: PV-växelriktare + batteri + EV DC-laddare + EMS + gateway. AI-styrd energioptimering. Modul: BAT-9.0 (9,04 kWh / 8,76 kWh nyttbar).",
        "saljargument": "Mest funktioner i ett paket, men högt pris ger lång återbetalningstid.",
    },
}

KATEGORI_FARG = {"Budget": "#22C55E", "Mellanklass": "#3B82F6", "Premium": "#F59E0B"}

# ──────────────────────────────────────────────────────────────
# BERÄKNINGAR
# ──────────────────────────────────────────────────────────────
def berakna(
    kwh_kapacitet: float,
    pris_kr: float,
    gront_avdrag: bool,
    produktion_ar_kwh: float,
    forbrukning_ar_kwh: float,
    elpris_kr: float,
    extra_tjänst_kr: float,
    livslangd_ar: int,
    verkningsgrad: float,
) -> dict:
    # Nettoinvestering
    netto = pris_kr * 0.5 if gront_avdrag else pris_kr

    # --- Energimodell ---
    # Andel sol som kan användas direkt (dagtid när sol + förbrukning sammanfaller)
    direkt_anvandning = min(produktion_ar_kwh, forbrukning_ar_kwh) * 0.55

    # Överskott som kan lagras
    overskott = max(produktion_ar_kwh - direkt_anvandning, 0)

    # Vad batteriet faktiskt kan lagra per år (begränsas av kapacitet × cykler per dag)
    max_laddning_ar = kwh_kapacitet * 365 * 0.85  # ~310 laddningscykler/år
    lagrat = min(overskott * verkningsgrad, max_laddning_ar)

    # Vad kunden annars köper från nätet som batteriet täcker
    behov_kvar = max(forbrukning_ar_kwh - direkt_anvandning, 0)
    batteri_anvandning = min(lagrat, behov_kvar)

    # Total egenanvändning
    egenanvandning = direkt_anvandning + batteri_anvandning
    sjalvforsorjning = min(egenanvandning / forbrukning_ar_kwh * 100 if forbrukning_ar_kwh > 0 else 0, 100)

    # Besparing = undviken nätköp tack vare batteriet
    besparing = batteri_anvandning * elpris_kr + extra_tjänst_kr
    arsvinst = besparing

    payback = netto / arsvinst if arsvinst > 0 else float("inf")
    total_vinst = arsvinst * livslangd_ar - netto

    balans = []
    for ar in range(livslangd_ar + 1):
        balans.append({"ar": ar, "kr": round(-netto + arsvinst * ar)})

    return {
        "netto": netto,
        "arsvinst": arsvinst,
        "besparing_el": batteri_anvandning * elpris_kr,
        "payback": payback,
        "total_vinst": total_vinst,
        "sjalvforsorjning": sjalvforsorjning,
        "direkt_kwh": direkt_anvandning,
        "batteri_kwh": batteri_anvandning,
        "kvar_fran_nat": max(forbrukning_ar_kwh - egenanvandning, 0),
        "balans": balans,
    }


# ──────────────────────────────────────────────────────────────
# PDF-RAPPORT
# ──────────────────────────────────────────────────────────────
def generera_pdf(configs, resultat, params, foretag, kund):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18,
                        textColor=colors.HexColor("#0F172A"))
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12,
                        textColor=colors.HexColor("#1D4ED8"))
    BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9, leading=13)
    SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=7.5,
                           textColor=colors.HexColor("#64748B"))

    els = []
    els.append(Paragraph("🔋 Batterisystem ROI-Rapport", H1))
    els.append(Spacer(1, 0.2*cm))
    els.append(Paragraph(
        f"Säljare: <b>{foretag}</b> &nbsp;|&nbsp; Kund: <b>{kund}</b> &nbsp;|&nbsp; {date.today().strftime('%Y-%m-%d')}",
        BODY))
    els.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1")))
    els.append(Spacer(1, 0.3*cm))

    # Förutsättningar
    els.append(Paragraph("Förutsättningar", H2))
    rows = [
        ["Parameter", "Värde"],
        ["Årsproduktion sol", f"{params['prod']:,.0f} kWh"],
        ["Årsförbrukning", f"{params['forb']:,.0f} kWh"],
        ["Elpris (köp)", f"{params['elpris']:.2f} kr/kWh"],
        ["Grönt Avdrag 50%", "Ja" if params['gront'] else "Nej"],
        ["Extra tjänsteintäkt/år", f"{params['extra']:,.0f} kr"],
    ]
    t = Table(rows, colWidths=[9*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    els.append(t)
    els.append(Spacer(1, 0.5*cm))

    # Jämförelsetabell
    els.append(Paragraph("Systemjämförelse – sorterad på återbetalningstid", H2))
    sorterade = sorted(configs.keys(), key=lambda n: resultat[n]["payback"])
    hdrs = ["System", "Kap. (kWh)", "Netto invest.", "Årsvinst", "Återbet.", "Vinst livsl.", "Cykler"]
    trows = [hdrs]
    for namn in sorterade:
        r = resultat[namn]
        c = configs[namn]
        sys = SYSTEMS[namn]
        pb = r["payback"]
        trows.append([
            namn,
            f"{c['kwh']:.1f}",
            f"{r['netto']:,.0f} kr",
            f"{r['arsvinst']:,.0f} kr",
            f"{pb:.1f} år" if pb < 50 else "–",
            f"{r['total_vinst']:,.0f} kr",
            f"{sys['cykler']:,}",
        ])
    cw = [5.5*cm, 1.6*cm, 2.4*cm, 2.0*cm, 1.8*cm, 2.4*cm, 1.5*cm]
    t2 = Table(trows, colWidths=cw)
    rb = [("BACKGROUND", (0, i), (-1, i),
           colors.HexColor("#F0FDF4") if i % 2 == 1 else colors.white)
          for i in range(1, len(trows))]
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        *rb,
    ]))
    els.append(t2)
    els.append(Spacer(1, 0.4*cm))

    # Förklaring
    els.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#CBD5E1")))
    els.append(Spacer(1, 0.2*cm))
    els.append(Paragraph(
        "OBS: Beräkningarna är uppskattningar baserade på angivna parametrar och en förenklad energimodell. "
        "Faktisk avkastning beror på elpriser, solproduktion, förbrukningsprofil och installationsförhållanden. "
        "Rapporten är inte ett juridiskt bindande erbjudande.",
        SMALL))

    doc.build(els)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────
# STREAMLIT APP
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Voltageapp – Batteri ROI",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #F1F5F9; }
.block-container { padding-top: 1.5rem; }
.kpi { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px;
       padding:14px 16px; margin-bottom:8px; }
.kpi h5 { margin:0; font-size:11px; color:#64748B; text-transform:uppercase;
           letter-spacing:.06em; }
.kpi .val { font-size:22px; font-weight:700; color:#0F172A; margin:3px 0 0; }
.kpi .sub { font-size:11px; color:#94A3B8; margin:1px 0 0; }
.good { color:#16A34A !important; }
.warn { color:#D97706 !important; }
.bad  { color:#DC2626 !important; }
.tag  { display:inline-block; padding:2px 9px; border-radius:20px;
        font-size:11px; font-weight:600; }
.tag-Budget     { background:#DCFCE7; color:#15803D; }
.tag-Mellanklass{ background:#DBEAFE; color:#1D4ED8; }
.tag-Premium    { background:#FEF3C7; color:#B45309; }
.cycle-bar { background:#E2E8F0; border-radius:6px; height:8px; overflow:hidden; }
.cycle-fill{ height:8px; border-radius:6px; background:#3B82F6; }
.insight { background:#ECFDF5; border-left:4px solid #22C55E;
           padding:10px 14px; border-radius:6px; font-size:13px; color:#15803D; margin-bottom:1rem; }
.warning-box { background:#FFF7ED; border-left:4px solid #F59E0B;
               padding:10px 14px; border-radius:6px; font-size:12px; color:#92400E; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔋 Voltageapp")
    st.caption("Försäljningsverktyg för batterisystem")
    st.divider()

    st.markdown("#### ⚡ Kundens energi (12 månader)")
    produktion = st.number_input(
        "Solproduktion senaste 12 mån (kWh)",
        min_value=0, max_value=50_000, value=6_000, step=100,
        help="Avläses från kundens solcellsinverter eller elräkning")
    forbrukning = st.number_input(
        "Elförbrukning senaste 12 mån (kWh)",
        min_value=0, max_value=50_000, value=10_000, step=100,
        help="Avläses från Tibber, elnätsbolagets app eller elräkning")

    st.divider()
    st.markdown("#### 💡 Elpris")
    elpris = st.number_input(
        "Elpris inkl. nätavgift & skatt (kr/kWh)",
        min_value=0.50, max_value=8.0, value=1.80, step=0.05, format="%.2f",
        help="Totalt pris kunden betalar per kWh – hittas på elräkningen")

    st.divider()
    st.markdown("#### 🏷️ Grönt Avdrag")
    gront_avdrag = st.toggle("50% Grönt Avdrag", value=True,
                              help="Privatpersoner kan få 50% skattereduktion på arbete & material")
    extra_intakt = st.number_input(
        "Extra årsintäkt (Checkwatt/FCR m.m.) kr/år",
        min_value=0, max_value=30_000, value=0, step=500,
        help="Lämna 0 om kunden inte deltar i stödtjänster")

    st.divider()
    st.markdown("#### 📄 PDF-rapport")
    foretag_namn = st.text_input("Ert företagsnamn", value="Voltageapp AB")
    kund_namn = st.text_input("Kundens namn", value="")


# ── SYSTEMKONFIGURATOR ──────────────────────────────────────
st.title("🔋 Batteri ROI – Försäljningsverktyg")
st.caption(
    f"Produktion **{produktion:,} kWh/år** · Förbrukning **{forbrukning:,} kWh/år** · "
    f"Elpris **{elpris:.2f} kr/kWh** · {'Grönt Avdrag 50%' if gront_avdrag else 'Inget grönt avdrag'}"
)

st.markdown("### Konfigurera system")
st.markdown("Ange pris och välj antal moduler för de system du vill jämföra.")

configs = {}   # namn → {kwh, pris, aktiv}

system_cols = st.columns(3)
for idx, (namn, sys) in enumerate(SYSTEMS.items()):
    with system_cols[idx % 3]:
        with st.expander(
            f"**{namn}**  ·  {sys['kategori']}",
            expanded=(sys["kategori"] == "Budget")
        ):
            aktiv = st.checkbox("Inkludera i jämförelse", value=(sys["kategori"] in ("Budget", "Premium")),
                                key=f"aktiv_{namn}")
            if aktiv:
                # Modulval
                modul_options = [f"{n} modul{'er' if n > 1 else ''} = {n * sys['modul_kwh']:.1f} kWh"
                                 for n in sys["moduler"]]
                modul_vald = st.selectbox("Antal moduler", modul_options,
                                          index=min(2, len(modul_options)-1),
                                          key=f"mod_{namn}")
                n_moduler = sys["moduler"][modul_options.index(modul_vald)]
                kwh = n_moduler * sys["modul_kwh"]

                pris = st.number_input(
                    "Systempris inkl. moms (kr)",
                    min_value=10_000, max_value=500_000,
                    value=int(kwh * 9_000),   # schablonvärde att utgå från
                    step=1_000, key=f"pris_{namn}",
                    help="Ange ert faktiska försäljningspris i kronor"
                )

                kat = sys["kategori"]
                st.markdown(
                    f"<span class='tag tag-{kat}'>{kat}</span> "
                    f"**{kwh:.1f} kWh** · {sys['cykler']:,} cykler · {sys['garanti_ar']} år garanti",
                    unsafe_allow_html=True
                )
                configs[namn] = {"kwh": kwh, "pris": pris}

if not configs:
    st.warning("Aktivera minst ett system ovan.")
    st.stop()

# ── BERÄKNINGAR ─────────────────────────────────────────────
resultat = {}
for namn, cfg in configs.items():
    sys = SYSTEMS[namn]
    resultat[namn] = berakna(
        kwh_kapacitet=cfg["kwh"],
        pris_kr=cfg["pris"],
        gront_avdrag=gront_avdrag,
        produktion_ar_kwh=float(produktion),
        forbrukning_ar_kwh=float(forbrukning),
        elpris_kr=elpris,
        extra_tjänst_kr=extra_intakt,
        livslangd_ar=SYSTEMS[namn]["livslangd_ar"],
        verkningsgrad=SYSTEMS[namn]["verkningsgrad"],
    )

sorterade = sorted(configs.keys(), key=lambda n: resultat[n]["payback"])
bast = sorterade[0]
samst = sorterade[-1]

# ── INSIKTRUTA ───────────────────────────────────────────────
if len(sorterade) >= 2:
    pb_b = resultat[bast]["payback"]
    pb_s = resultat[samst]["payback"]
    netto_b = resultat[bast]["netto"]
    netto_s = resultat[samst]["netto"]
    kwh_b = configs[bast]["kwh"]
    kwh_s = configs[samst]["kwh"]

    if pb_b < 50 and pb_s < 50:
        diff_ar = pb_s - pb_b
        diff_kr = netto_s - netto_b
        st.markdown(
            f"<div class='insight'>💡 <b>{bast}</b> betalar sig <b>{diff_ar:.1f} år snabbare</b> "
            f"än {samst} och kräver <b>{diff_kr:,.0f} kr mindre</b> i nettoinvestering. "
            f"Kunden sparar in mellanskillnaden redan år {pb_b:.1f} – oavsett att {samst} "
            f"marknadsförs med fler cykler/funktioner.</div>",
            unsafe_allow_html=True
        )

st.divider()

# ── TABS ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Jämförelse & ROI", "⚡ Energiflöde", "📄 PDF-rapport"])

# ════════════════════════════════════════════════════════
# TAB 1 – Jämförelse
# ════════════════════════════════════════════════════════
with tab1:
    # KPI-kort
    cols = st.columns(min(len(sorterade), 3))
    for i, namn in enumerate(sorterade):
        r = resultat[namn]
        sys = SYSTEMS[namn]
        cfg = configs[namn]
        pb = r["payback"]
        rang = "🥇 " if i == 0 else ("🥈 " if i == 1 else ("🥉 " if i == 2 else ""))
        pb_class = "good" if pb < 10 else ("warn" if pb < 15 else "bad")
        pb_str = f"{pb:.1f} år" if pb < 50 else "–"
        tv_class = "good" if r["total_vinst"] > 0 else "bad"

        with cols[i % 3]:
            kat2 = sys["kategori"]
            st.markdown(
                f"""<div class='kpi'>
                  <span class='tag tag-{kat2}'>{kat2}</span>
                  <h5 style='margin-top:8px'>{rang}{namn}</h5>
                  <div class='val'>{cfg['pris']:,} kr</div>
                  <div class='sub'>Listpris inkl. moms</div>
                </div>""", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            c1.metric("Nettoinvest.", f"{r['netto']:,.0f} kr")
            c2.metric("Kapacitet", f"{cfg['kwh']:.1f} kWh")
            c1.metric("Årsvinst", f"{r['arsvinst']:,.0f} kr")
            c2.metric("Återbet. tid", pb_str)
            st.metric(f"Total vinst ({sys['livslangd_ar']} år)", f"{r['total_vinst']:,.0f} kr")

            # Cykel-visualisering
            max_cykler = max(SYSTEMS[n]["cykler"] for n in configs)
            pct = sys["cykler"] / max_cykler * 100
            st.markdown(
                f"**Lovar {sys['cykler']:,} cykler** &nbsp;({sys['kemi']})<br>"
                f"<div class='cycle-bar'><div class='cycle-fill' style='width:{pct:.0f}%'></div></div>"
                f"<span style='font-size:11px;color:#64748B'>{sys['garanti_ar']} år garanti · "
                f"{sys['dod_pct']}% DoD</span>",
                unsafe_allow_html=True
            )

            with st.expander("ℹ️ Systembeskrivning"):
                st.write(sys["info"])
                st.markdown(f"**Säljarens argument:** {sys['saljargument']}")

    st.divider()

    # ── ROI-GRAF ─────────────────────────────────────────────
    st.subheader("Ackumulerad vinst över tid")
    FARGER = ["#22C55E", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"]
    fig = go.Figure()
    fig.add_hline(y=0, line_dash="dash", line_color="#94A3B8", line_width=1.5,
                  annotation_text="Break-even", annotation_position="right")

    for i, namn in enumerate(sorterade):
        r = resultat[namn]
        ar_vals = [d["ar"] for d in r["balans"]]
        kr_vals = [d["kr"] for d in r["balans"]]
        c = FARGER[i % len(FARGER)]
        fig.add_trace(go.Scatter(
            x=ar_vals, y=kr_vals, name=namn,
            line=dict(color=c, width=2.5),
            hovertemplate=f"<b>{namn}</b><br>År %{{x}}: %{{y:,.0f}} kr<extra></extra>",
        ))

    fig.update_layout(
        xaxis_title="År", yaxis_title="Ackumulerad vinst (kr)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        height=400, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_yaxes(tickformat=",.0f", gridcolor="#F1F5F9")
    fig.update_xaxes(gridcolor="#F1F5F9")
    st.plotly_chart(fig, use_container_width=True)

    # ── PAYBACK-STAPLAR ──────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Återbetalningstid")
        pb_names, pb_vals, pb_colors = [], [], []
        for namn in sorterade:
            pb = resultat[namn]["payback"]
            if pb < 50:
                pb_names.append(namn)
                pb_vals.append(round(pb, 1))
                pb_colors.append("#22C55E" if pb < 10 else ("#F59E0B" if pb < 15 else "#EF4444"))
        fig2 = go.Figure(go.Bar(
            x=pb_vals, y=pb_names, orientation="h",
            marker_color=pb_colors,
            text=[f"{v} år" for v in pb_vals], textposition="outside",
        ))
        fig2.update_layout(height=280, margin=dict(l=10, r=60, t=10, b=10),
                           plot_bgcolor="white", paper_bgcolor="white")
        fig2.update_xaxes(gridcolor="#F1F5F9", title="År")
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        st.subheader("Nettoinvestering vs årsvinst")
        fig3 = go.Figure()
        for i, namn in enumerate(sorterade):
            r = resultat[namn]
            c = FARGER[i % len(FARGER)]
            fig3.add_trace(go.Bar(name=namn, x=[namn],
                                  y=[r["netto"]], marker_color=c, opacity=0.6))
            fig3.add_trace(go.Bar(name=f"Årsvinst×10", x=[namn],
                                  y=[r["arsvinst"] * 10], marker_color=c,
                                  showlegend=False,
                                  hovertemplate=f"Årsvinst×10: %{{y:,.0f}} kr"))
        fig3.update_layout(barmode="group", height=280,
                           margin=dict(l=10, r=10, t=10, b=10),
                           showlegend=False, plot_bgcolor="white", paper_bgcolor="white")
        fig3.update_yaxes(tickformat=",.0f", gridcolor="#F1F5F9")
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Mörk stapel = nettoinvestering · ljus = 10× årsvinst")

    # ── FULL TABELL ───────────────────────────────────────────
    st.subheader("Fullständig jämförelsetabell")
    tabell = []
    for namn in sorterade:
        r = resultat[namn]
        sys = SYSTEMS[namn]
        cfg = configs[namn]
        pb = r["payback"]
        tabell.append({
            "System": namn,
            "Kat.": sys["kategori"],
            "Pris (kr)": f"{cfg['pris']:,}",
            "Kapacitet (kWh)": f"{cfg['kwh']:.1f}",
            "Netto invest. (kr)": f"{r['netto']:,.0f}",
            "Årsvinst (kr)": f"{r['arsvinst']:,.0f}",
            "Återbet. (år)": f"{pb:.1f}" if pb < 50 else "–",
            "Total vinst (kr)": f"{r['total_vinst']:,.0f}",
            "Cykler": f"{sys['cykler']:,}",
            "Garanti": f"{sys['garanti_ar']} år",
        })
    st.dataframe(pd.DataFrame(tabell), hide_index=True, use_container_width=True)

    # Varning om "fler cykler"-argumentet
    st.markdown("""
    <div class='warning-box'>
    ⚠️ <b>Kunden hänvisar till cykler/funktioner?</b> – Alla system i listan använder LFP-kemi med 
    6 000 cykler. "Upp till 10 000 cykler" är ett max-värde under ideala labförhållanden; 
    i praktiken sker 1 cykel/dag → ~16 år. Det avgörande är hur snabbt systemet betalar sig, 
    inte antalet cykler på ett papper.
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
# TAB 2 – Energiflöde
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("Energiflöde per system")
    st.info(
        f"☀️ Årsproduktion: **{produktion:,} kWh** · "
        f"🏠 Årsförbrukning: **{forbrukning:,} kWh**"
    )
    for namn in sorterade:
        r = resultat[namn]
        sys = SYSTEMS[namn]
        with st.expander(f"**{namn}** — Självförsörjning {r['sjalvforsorjning']:.0f}%",
                         expanded=(namn == bast)):
            c1, c2, c3 = st.columns(3)
            c1.metric("Direkt solanvändning", f"{r['direkt_kwh']:,.0f} kWh/år",
                      help="Sol som används direkt under dagen")
            c2.metric("Via batteri", f"{r['batteri_kwh']:,.0f} kWh/år",
                      help="Lagrad sol som används på kvällen/natten")
            c3.metric("Köps från nätet", f"{r['kvar_fran_nat']:,.0f} kWh/år")

            tot = float(forbrukning) if forbrukning > 0 else 1
            pd_pct = r["direkt_kwh"] / tot * 100
            pb_pct = r["batteri_kwh"] / tot * 100
            pn_pct = r["kvar_fran_nat"] / tot * 100
            st.markdown(
                f"""<div style='display:flex;height:24px;border-radius:6px;overflow:hidden;margin:10px 0 4px'>
                  <div style='width:{pd_pct:.1f}%;background:#F59E0B' title='Direkt sol'></div>
                  <div style='width:{pb_pct:.1f}%;background:#3B82F6' title='Batteri'></div>
                  <div style='width:{pn_pct:.1f}%;background:#E2E8F0' title='Nät'></div>
                </div>
                <div style='font-size:11px;color:#64748B;display:flex;gap:14px'>
                  <span>🟡 Direkt sol {pd_pct:.0f}%</span>
                  <span>🔵 Batteri {pb_pct:.0f}%</span>
                  <span>⬜ Nät {pn_pct:.0f}%</span>
                </div>""",
                unsafe_allow_html=True
            )
            st.metric("Besparing via batteriet", f"{r['besparing_el']:,.0f} kr/år",
                      help=f"= {r['batteri_kwh']:,.0f} kWh × {elpris:.2f} kr/kWh")


# ════════════════════════════════════════════════════════
# TAB 3 – PDF
# ════════════════════════════════════════════════════════
with tab3:
    st.subheader("📄 Generera kundrapport")
    st.write("Proffsig PDF med förutsättningar och fullständig systemjämförelse.")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        f_namn = st.text_input("Ert företagsnamn", value=foretag_namn, key="pdf_f")
    with col_p2:
        k_namn = st.text_input("Kundens namn", value=kund_namn or "Kund AB", key="pdf_k")

    if st.button("📥 Skapa PDF-rapport", type="primary"):
        with st.spinner("Skapar rapport..."):
            params = {
                "prod": float(produktion),
                "forb": float(forbrukning),
                "elpris": elpris,
                "gront": gront_avdrag,
                "extra": extra_intakt,
            }
            pdf_bytes = generera_pdf(configs, resultat, params, f_namn, k_namn)
        st.download_button(
            "⬇️ Ladda ner PDF",
            data=pdf_bytes,
            file_name=f"roi_{k_namn.replace(' ','_')}_{date.today()}.pdf",
            mime="application/pdf",
        )
        st.success("Klar!")

    st.divider()
    st.subheader("📊 Exportera som CSV")
    csv_rows = []
    for namn in sorterade:
        r = resultat[namn]
        sys = SYSTEMS[namn]
        cfg = configs[namn]
        csv_rows.append({
            "System": namn,
            "Kapacitet_kWh": cfg["kwh"],
            "Pris_kr": cfg["pris"],
            "Netto_invest_kr": round(r["netto"]),
            "Arsvinst_kr": round(r["arsvinst"]),
            "Payback_ar": round(r["payback"], 2) if r["payback"] < 50 else None,
            "Total_vinst_kr": round(r["total_vinst"]),
            "Sjalvforsorjning_pct": round(r["sjalvforsorjning"]),
            "Cykler": sys["cykler"],
            "Garanti_ar": sys["garanti_ar"],
        })
    csv_df = pd.DataFrame(csv_rows)
    st.download_button(
        "⬇️ Ladda ner CSV",
        data=csv_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"roi_{date.today()}.csv",
        mime="text/csv",
    )