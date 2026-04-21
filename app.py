import streamlit as st

# --- Sidinställningar ---
st.set_page_config(page_title="Batteri ROI Kalkylator", layout="centered")

st.title("🔋 Batterisystem: ROI-Kalkylator")
st.markdown("Beräkna hur snabbt ditt batterisystem betalar sig självt.")

# --- Sidebar: Inmatning ---
st.sidebar.header("Systeminställningar")
pris_system = st.sidebar.number_input("Investeringskostnad (kr inkl. moms)", value=100000, step=5000)
gront_avdrag = st.sidebar.checkbox("Använd Grönt Avdrag (50%)", value=True)

st.sidebar.header("Prestanda & Intäkter")
batteri_kw = st.sidebar.slider("Batteriets effekt (kW)", 1, 20, 10)
vinst_per_ar = st.sidebar.number_input("Uppskattad årlig vinst/besparing (kr)", value=12000, step=500)

# --- Beräkningar ---
netto_investering = pris_system * 0.5 if gront_avdrag else pris_system
payback_tid = netto_investering / vinst_per_ar if vinst_per_ar > 0 else 0

# --- Presentation ---
st.divider()

col1, col2 = st.columns(2)
with col1:
    st.metric("Nettoinvestering", f"{int(netto_investering):,} kr".replace(",", " "))
with col2:
    color = "normal" if payback_tid < 10 else "inverse"
    st.metric("Återbetalningstid", f"{payback_tid:.1f} år", delta_color=color)

# --- Grafisk vy ---
st.subheader("Ekonomisk översikt")
ar = list(range(0, 16))
balans = [-netto_investering + (vinst_per_ar * t) for t in ar]

st.line_chart(dict(zip(ar, balans)))
st.caption("Grafen visar ackumulerad vinst över 15 år (break-even vid 0-strecket).")

# --- Förklaring ---
with st.expander("Hur räknas vinsten ut?"):
    st.write("""
    Den årliga vinsten baseras oftast på tre faktorer:
    1. **Stödtjänster (t.ex. Checkwatt):** Ersättning för att hjälpa till att balansera elnätet.
    2. **Egenanvändning:** Att du använder din egen solel på kvällen istället för att sälja den billigt.
    3. **Arbitrage:** Att ladda när elen är billig (natt) och använda när den är dyr (dag).
    """)