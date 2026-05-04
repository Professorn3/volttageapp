# volttageapp
🔋 Battery ROI Calculator – Streamlit Web App

En interaktiv och användarvänlig webbapplikation byggd i Python med Streamlit för att hjälpa solcellsinstallatörer och privatpersoner att beräkna lönsamheten i batterilager.
🚀 Översikt

Detta verktyg är utformat för att snabbt och visuellt visa hur snabbt ett batterisystem (t.ex. vid lagring av egenproducerad solel eller arbitrage) betalar sig själv. Appen tar hänsyn till investeringskostnad, statliga bidrag (Grönt avdrag) och årliga besparingar.
✨ Funktioner

    Dynamiska beräkningar: Justera systempris och se effekten av det gröna avdraget (50%) i realtid.

    Interaktiva sliders: Ställ in batteriets effekt (kW) och förväntad årlig vinst.

    Visualisering: En tydlig linjegraf visar ackumulerad vinst över 15 år och markerar tydligt "break-even"-punkten.

    KPI-Metrics: Snabba nyckeltal för nettoinvestering och exakt återbetalningstid i år.

    Utbildande innehåll: Inbyggda förklaringar för kunden om hur vinsten genereras (Stödtjänster, Egenanvändning, Arbitrage).

🛠 Teknologi

    Python

    Streamlit (Frontend & Logik)

    Matplotlib / Streamlit Line Charts (Datavisualisering)

📦 Installation & Användning

    Klona repot:
    Bash

    git clone https://github.com/ditt-användarnamn/battery-roi-calculator.git
    cd battery-roi-calculator

    Installera beroenden:
    Bash

    pip install streamlit

    Kör appen:
    Bash

    streamlit run app.py

📈 Roadmap

    [ ] Lägga till stöd för specifika batterimodeller (Dyness, Pylontech, etc.).

    [ ] Möjlighet att exportera resultatet till PDF.

    [ ] Import av historisk elprisdata för mer exakta arbitrage-beräkningar.
