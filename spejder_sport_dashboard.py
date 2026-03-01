"""
╔══════════════════════════════════════════════════════════════╗
║   Spejder Sport — Salgs-Dashboard                           ║
║   Streamlit app med live CPI fra Danmarks Statistik API     ║
╚══════════════════════════════════════════════════════════════╝

Kør med:  streamlit run spejder_sport_dashboard.py
Kræver:   pip install streamlit plotly pandas requests openpyxl
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime

# ── Sidekonfiguration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Spejder Sport Dashboard",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Farver (Spejder Sport forest-palette) ────────────────────────────────────
PALETTE = {
    "mørkegrøn":  "#1B4332",
    "grøn":       "#52B788",
    "lysgrøn":    "#B7E4C7",
    "orange":     "#E76F51",
    "guld":       "#F4A261",
    "blå":        "#2171B5",
    "lilla":      "#6A3D9A",
    "bg":         "#F4F7F4",
}

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .main {{ background-color: {PALETTE['bg']}; }}
    .stApp {{ background-color: {PALETTE['bg']}; }}
    .metric-card {{
        background: white;
        border-left: 4px solid {PALETTE['grøn']};
        border-radius: 8px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
    .metric-value {{ font-size: 28px; font-weight: 700; color: {PALETTE['mørkegrøn']}; }}
    .metric-delta {{ font-size: 13px; color: {PALETTE['grøn']}; }}
    .section-header {{
        font-size: 15px; font-weight: 600;
        color: {PALETTE['mørkegrøn']};
        border-bottom: 2px solid {PALETTE['lysgrøn']};
        padding-bottom: 6px; margin-bottom: 16px;
    }}
    .source-badge {{
        display: inline-block; background: {PALETTE['lysgrøn']};
        color: {PALETTE['mørkegrøn']}; border-radius: 12px;
        padding: 2px 10px; font-size: 11px; font-weight: 600;
    }}
    .api-status-ok  {{ color: {PALETTE['grøn']};  font-weight: 600; }}
    .api-status-err {{ color: {PALETTE['orange']}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# 1) DATA — Excel upload
# ════════════════════════════════════════════════════════════════════════════
@st.cache_data
def load_sales(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df["Måned_navn"] = df["Måned"].map({
        1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Maj",6:"Jun",
        7:"Jul",8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec"
    })
    df["År_Måned"] = df["År"].astype(str) + "-" + df["Måned"].astype(str).str.zfill(2)
    return df


# ════════════════════════════════════════════════════════════════════════════
# 2) CPI — Danmarks Statistik API (live hentning)
# ════════════════════════════════════════════════════════════════════════════
FALLBACK_CPI = {
    "2023-01": 7.9,"2023-02": 7.1,"2023-03": 6.7,"2023-04": 6.2,
    "2023-05": 5.5,"2023-06": 3.7,"2023-07": 3.1,"2023-08": 2.7,
    "2023-09": 2.3,"2023-10": 2.3,"2023-11": 2.2,"2023-12": 2.1,
    "2024-01": 1.8,"2024-02": 2.0,"2024-03": 2.2,"2024-04": 2.2,
    "2024-05": 1.8,"2024-06": 1.5,"2024-07": 1.7,"2024-08": 1.8,
    "2024-09": 1.8,"2024-10": 2.0,"2024-11": 2.2,"2024-12": 2.3,
}

@st.cache_data(ttl=3600)
def fetch_cpi() -> tuple[dict, bool]:
    """
    Henter CPI fra Danmarks Statistik API (PRIS9 — Forbrugerprisindeks).
    API-kald:  POST https://api.statbank.dk/v1/data
    Returnerer (cpi_dict, api_ok)
    """
    url = "https://api.statbank.dk/v1/data"
    payload = {
        "table": "PRIS9",
        "format": "JSONSTAT",
        "lang": "da",
        "variables": [
            {"code": "FORMDATO", "values": ["*"]},
            {"code": "ENHED",    "values": ["100"]},   # 100 = %-ændring ift. samme md. året før
            {"code": "Tid",      "values": [
                "2023M01","2023M02","2023M03","2023M04","2023M05","2023M06",
                "2023M07","2023M08","2023M09","2023M10","2023M11","2023M12",
                "2024M01","2024M02","2024M03","2024M04","2024M05","2024M06",
                "2024M07","2024M08","2024M09","2024M10","2024M11","2024M12",
            ]}
        ]
    }
    try:
        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        data = r.json()

        # Parse JSONSTAT → dict {YYYY-MM: værdi}
        dataset   = data["dataset"]
        time_ids  = list(dataset["dimension"]["Tid"]["category"]["index"].keys())
        values    = dataset["value"]
        cpi = {}
        for tid, val in zip(time_ids, values):
            # "2023M01" → "2023-01"
            key = tid[:4] + "-" + tid[5:]
            if val is not None:
                cpi[key] = round(float(val), 1)
        return cpi, True

    except Exception:
        return FALLBACK_CPI, False


def cpi_df(cpi_dict: dict) -> pd.DataFrame:
    rows = []
    for key, val in cpi_dict.items():
        year, month = key.split("-")
        rows.append({"År": int(year), "Måned": int(month),
                     "CPI_%": val, "År_Måned": key})
    return pd.DataFrame(rows).sort_values("År_Måned")


# ════════════════════════════════════════════════════════════════════════════
# 3) SIDEBAR — Filtrering & upload
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Placeholder_view_vector.svg/200px-Placeholder_view_vector.svg.png",
             width=40)  # erstat med Spejder Sport logo-URL
    st.title("🏔️ Spejder Sport")
    st.caption("Salgs-Dashboard · AI-øvelse")
    st.divider()

    uploaded = st.file_uploader(
        "Upload Excel-datasæt", type=["xlsx"],
        help="Upload filen Datasæt_til_Claude_øvelsen.xlsx"
    )
    st.divider()

    # Filtre vises når data er indlæst
    if uploaded:
        df_raw = load_sales(uploaded)

        år_valg = st.multiselect(
            "📅 Vælg år",
            options=sorted(df_raw["År"].unique()),
            default=sorted(df_raw["År"].unique()),
        )
        kat_valg = st.multiselect(
            "🎒 Produktkategori",
            options=sorted(df_raw["Produktkategori_navn"].unique()),
            default=sorted(df_raw["Produktkategori_navn"].unique()),
        )
        region_valg = st.multiselect(
            "🗺️ Region",
            options=sorted(df_raw["Region"].unique()),
            default=sorted(df_raw["Region"].unique()),
        )
        kanal_valg = st.multiselect(
            "🛒 Kanal",
            options=sorted(df_raw["Kanal"].unique()),
            default=sorted(df_raw["Kanal"].unique()),
        )
        st.divider()
        vis_cpi = st.toggle("📈 Vis CPI-overlay", value=True)
        st.caption("CPI hentes live fra Danmarks Statistik")
    else:
        df_raw = år_valg = kat_valg = region_valg = kanal_valg = None
        vis_cpi = True


# ════════════════════════════════════════════════════════════════════════════
# 4) HOVED-INDHOLD
# ════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<h1 style='color:{PALETTE["mørkegrøn"]};margin-bottom:0'>
  🏔️ Spejder Sport — Salgsanalyse Dashboard
</h1>
<p style='color:#666;margin-top:4px'>
  AI-assisteret forretningsanalyse · Data fra Excel + Danmarks Statistik API
</p>
""", unsafe_allow_html=True)
st.divider()

# ── Ingen fil uploadet ───────────────────────────────────────────────────────
if not uploaded:
    st.info("👈 **Upload dit Excel-datasæt i sidebaren for at starte.**")
    with st.expander("ℹ️ Hvad gør denne app?"):
        st.markdown("""
        Denne Streamlit-app demonstrerer **AI-assisteret forretningsoptimering** ved at:
        1. **Indlæse** Spejder Sports salgsdata fra Excel
        2. **Hente CPI live** fra Danmarks Statistik API (api.statbank.dk)
        3. **Visualisere** data i tre grafer med dynamisk filtrering:
           - 📈 **Linjegraf** — månedlig salgsudvikling vs. CPI
           - 📊 **Søjlediagram** — sammenligning på kategori/region/kanal
           - 🟦 **Heatmap** — sæsonmønster på tværs af måneder og kategorier
        4. **Beregne** KPI'er og sammenligne med markedsdata
        """)
    st.stop()

# ── Filtrer data ─────────────────────────────────────────────────────────────
df = df_raw[
    df_raw["År"].isin(år_valg) &
    df_raw["Produktkategori_navn"].isin(kat_valg) &
    df_raw["Region"].isin(region_valg) &
    df_raw["Kanal"].isin(kanal_valg)
].copy()

if df.empty:
    st.warning("⚠️ Ingen data matcher de valgte filtre. Juster filtrene i sidebaren.")
    st.stop()

# ── Hent CPI ─────────────────────────────────────────────────────────────────
cpi_raw, api_ok = fetch_cpi()
cpi_data = cpi_df(cpi_raw)

# ── API-status badge ─────────────────────────────────────────────────────────
api_col1, api_col2 = st.columns([6,1])
with api_col2:
    if api_ok:
        st.markdown('<p class="api-status-ok">🟢 DST API live</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="api-status-err">🟡 DST API offline – fallback-data bruges</p>',
                    unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# 5) KPI-METRIK-KORT (øverste række)
# ════════════════════════════════════════════════════════════════════════════
total_salg   = df["Salg (DKK)"].sum()
avg_bruttoav = df["Bruttoavance_%"].mean()
antal_mdr    = df["År_Måned"].nunique()

# Vækst ift. foregående år (hvis begge år er valgt)
if len(år_valg) >= 2:
    sorted_år = sorted(år_valg)
    salg_sid  = df[df["År"] == sorted_år[-1]]["Salg (DKK)"].sum()
    salg_for  = df[df["År"] == sorted_år[-2]]["Salg (DKK)"].sum()
    vækst_pct = (salg_sid - salg_for) / salg_for * 100
    vækst_txt = f"+{vækst_pct:.1f}% vs. {sorted_år[-2]}"
else:
    vækst_txt = "—"

# Gennemsnitlig CPI for valgte år
cpi_filter = cpi_data[cpi_data["År"].isin(år_valg)]["CPI_%"].mean()
real_vækst = vækst_pct - cpi_filter if len(år_valg) >= 2 else None

k1, k2, k3, k4, k5 = st.columns(5)

def metric_card(col, label, value, delta=""):
    col.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="metric-delta">{delta}</div>
    </div>""", unsafe_allow_html=True)

metric_card(k1, "Total Salg (DKK)",   f"{total_salg/1e6:.2f} mio.", vækst_txt)
metric_card(k2, "Bruttoavance",        f"{avg_bruttoav:.1f}%",       "Gns. på tværs af kat.")
metric_card(k3, "Måneder i datasæt",   str(antal_mdr),               f"{len(år_valg)} år valgt")
metric_card(k4, "Gns. CPI (periode)",  f"{cpi_filter:.1f}%",         "Danmarks Statistik")
metric_card(k5, "Real vækst (ekskl. inflation)",
            f"{real_vækst:+.1f}%" if real_vækst is not None else "—",
            "Salgsvækst minus CPI")

st.markdown("<br>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# 6) GRAF 1 — LINJEGRAF: Månedlig salg + CPI overlay
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📈 Månedlig salgsudvikling vs. CPI</div>',
            unsafe_allow_html=True)
st.caption(
    "Linjegrafen viser det samlede salg per måned fordelt på år. "
    "CPI-linjen (Danmarks Statistik) viser inflationspresset i samme periode."
)

monthly = (df.groupby(["År","Måned","Måned_navn"])["Salg (DKK)"]
             .sum().reset_index().sort_values(["År","Måned"]))

fig_linje = make_subplots(specs=[[{"secondary_y": True}]])

colors_år = [PALETTE["mørkegrøn"], PALETTE["grøn"], PALETTE["blå"]]
for i, år in enumerate(sorted(monthly["År"].unique())):
    sub = monthly[monthly["År"] == år]
    fig_linje.add_trace(
        go.Scatter(
            x=sub["Måned_navn"], y=sub["Salg (DKK)"] / 1000,
            name=str(år), mode="lines+markers",
            line=dict(color=colors_år[i % len(colors_år)], width=3),
            marker=dict(size=8, symbol="circle", line=dict(width=2, color="white")),
            hovertemplate=f"<b>{år}</b><br>%{{x}}: %{{y:.0f}}k DKK<extra></extra>",
        ),
        secondary_y=False,
    )

if vis_cpi:
    cpi_filter_df = cpi_data[cpi_data["År"].isin(år_valg)].copy()
    cpi_filter_df["Måned_navn"] = cpi_filter_df["Måned"].map({
        1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Maj",6:"Jun",
        7:"Jul",8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec"
    })
    for i, år in enumerate(sorted(cpi_filter_df["År"].unique())):
        sub_cpi = cpi_filter_df[cpi_filter_df["År"] == år]
        fig_linje.add_trace(
            go.Scatter(
                x=sub_cpi["Måned_navn"], y=sub_cpi["CPI_%"],
                name=f"CPI {år}", mode="lines",
                line=dict(color=PALETTE["orange"], width=2, dash="dot"),
                marker=dict(symbol="diamond", size=6),
                hovertemplate=f"<b>CPI {år}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
            ),
            secondary_y=True,
        )
    fig_linje.update_yaxes(title_text="Inflation / CPI (%)",
                           secondary_y=True,
                           tickfont=dict(color=PALETTE["orange"]))

fig_linje.update_layout(
    yaxis_title="Salg (1.000 DKK)",
    hovermode="x unified",
    plot_bgcolor="white", paper_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=30, b=10),
    height=380,
)
fig_linje.update_xaxes(showgrid=False)
fig_linje.update_yaxes(gridcolor="#EEF3EE", secondary_y=False)

st.plotly_chart(fig_linje, use_container_width=True)

st.markdown(
    f'<span class="source-badge">Kilde: Excel-datasæt (salg) + Danmarks Statistik API – PRIS9 (CPI)</span>',
    unsafe_allow_html=True
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 7) GRAF 2 — SØJLEDIAGRAM: Kategori / Region / Kanal sammenligning
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📊 Salg fordelt på kategori, region og kanal</div>',
            unsafe_allow_html=True)

bar_tab1, bar_tab2, bar_tab3 = st.tabs(
    ["🎒 Produktkategori", "🗺️ Region", "🛒 Kanal"]
)

def søjle_fig(group_col, farver):
    agg = (df.groupby(["År", group_col])["Salg (DKK)"]
              .sum().reset_index())
    agg["Salg_mio"] = agg["Salg (DKK)"] / 1e6
    fig = px.bar(
        agg, x=group_col, y="Salg_mio", color="År",
        barmode="group",
        color_discrete_sequence=farver,
        labels={"Salg_mio": "Salg (mio. DKK)", group_col: ""},
        text=agg["Salg_mio"].apply(lambda v: f"{v:.2f}m"),
    )
    # Tilføj vækst-annotation
    if len(sorted(agg["År"].unique())) >= 2:
        sorted_yr = sorted(agg["År"].unique())
        for cat in agg[group_col].unique():
            sub = agg[agg[group_col] == cat]
            v_old = sub[sub["År"] == sorted_yr[-2]]["Salg (DKK)"].sum()
            v_new = sub[sub["År"] == sorted_yr[-1]]["Salg (DKK)"].sum()
            if v_old > 0:
                pct = (v_new - v_old) / v_old * 100
                fig.add_annotation(
                    x=cat, y=v_new / 1e6 + 0.05,
                    text=f"+{pct:.1f}%",
                    showarrow=False, font=dict(size=11, color=PALETTE["mørkegrøn"]),
                )
    fig.update_traces(textposition="outside", textfont_size=10)
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        legend_title_text="År",
        margin=dict(l=10, r=10, t=30, b=10),
        height=380,
        yaxis=dict(gridcolor="#EEF3EE"),
        xaxis=dict(showgrid=False),
    )
    return fig

with bar_tab1:
    st.plotly_chart(
        søjle_fig("Produktkategori_navn",
                  [PALETTE["mørkegrøn"], PALETTE["grøn"], PALETTE["lysgrøn"]]),
        use_container_width=True
    )
with bar_tab2:
    st.plotly_chart(
        søjle_fig("Region",
                  [PALETTE["mørkegrøn"], PALETTE["grøn"]]),
        use_container_width=True
    )
with bar_tab3:
    st.plotly_chart(
        søjle_fig("Kanal",
                  [PALETTE["mørkegrøn"], PALETTE["grøn"]]),
        use_container_width=True
    )

st.markdown(
    f'<span class="source-badge">Kilde: Excel-datasæt (interne salgsdata)</span>',
    unsafe_allow_html=True
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 8) GRAF 3 — HEATMAP: Sæsonmønster
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">🟦 Heatmap — Sæsonmønster & intensitet</div>',
            unsafe_allow_html=True)

hm_tab1, hm_tab2 = st.tabs(["📅 Kategori × Måned", "📅 Kategori × Måned (vækst % YoY)"])

# Tab 1: Absolut salg
with hm_tab1:
    hm_data = (df.groupby(["Produktkategori_navn","Måned","Måned_navn"])["Salg (DKK)"]
                 .sum().reset_index())
    hm_pivot = hm_data.pivot_table(
        index="Produktkategori_navn", columns="Måned", values="Salg (DKK)", aggfunc="sum"
    )
    hm_pivot.columns = ["Jan","Feb","Mar","Apr","Maj","Jun",
                         "Jul","Aug","Sep","Okt","Nov","Dec"][:len(hm_pivot.columns)]

    fig_hm = go.Figure(go.Heatmap(
        z=hm_pivot.values / 1000,
        x=hm_pivot.columns.tolist(),
        y=hm_pivot.index.tolist(),
        colorscale=[[0, PALETTE["lysgrøn"]], [0.5, PALETTE["grøn"]], [1, PALETTE["mørkegrøn"]]],
        text=[[f"{v:.0f}k" for v in row] for row in hm_pivot.values / 1000],
        texttemplate="%{text}",
        textfont={"size": 11, "color": "white"},
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f}k DKK<extra></extra>",
        colorbar=dict(title="DKK (1.000)", ticksuffix="k"),
    ))
    fig_hm.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=20, b=10), height=280,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("Mørkere = højere salg. Klatregrej dominerer; Q4 er klart stærkest på tværs af alle kategorier.")

# Tab 2: YoY vækst (kun hvis begge år er valgt)
with hm_tab2:
    if len(år_valg) < 2:
        st.info("Vælg mindst 2 år i sidebaren for at se YoY-vækst.")
    else:
        sorted_yr = sorted(år_valg)
        yr_old, yr_new = sorted_yr[-2], sorted_yr[-1]
        hm_old = (df[df["År"] == yr_old]
                  .groupby(["Produktkategori_navn","Måned"])["Salg (DKK)"].sum())
        hm_new = (df[df["År"] == yr_new]
                  .groupby(["Produktkategori_navn","Måned"])["Salg (DKK)"].sum())
        hm_vækst = ((hm_new - hm_old) / hm_old * 100).reset_index()
        hm_vækst.columns = ["Produktkategori_navn","Måned","Vækst_%"]
        hm_vp = hm_vækst.pivot_table(
            index="Produktkategori_navn", columns="Måned", values="Vækst_%"
        )
        hm_vp.columns = ["Jan","Feb","Mar","Apr","Maj","Jun",
                          "Jul","Aug","Sep","Okt","Nov","Dec"][:len(hm_vp.columns)]

        fig_hm2 = go.Figure(go.Heatmap(
            z=hm_vp.values,
            x=hm_vp.columns.tolist(),
            y=hm_vp.index.tolist(),
            colorscale="RdYlGn",
            zmid=0,
            text=[[f"{v:+.1f}%" for v in row] for row in hm_vp.values],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.1f}%<extra></extra>",
            colorbar=dict(title=f"Vækst %\n({yr_old}→{yr_new})"),
        ))
        fig_hm2.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=10, r=10, t=20, b=10), height=280,
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_hm2, use_container_width=True)
        st.caption(f"Grøn = vækst, Rød = tilbagegang ({yr_old} → {yr_new}).")

st.markdown(
    f'<span class="source-badge">Kilde: Excel-datasæt (interne salgsdata)</span>',
    unsafe_allow_html=True
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# 9) RAW DATA & EKSPORT
# ════════════════════════════════════════════════════════════════════════════
with st.expander("🗃️ Se rådata og eksportér"):
    st.dataframe(df.drop(columns=["Produktkategori"]), use_container_width=True, height=300)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Download filtreret data som CSV",
        data=csv, file_name="spejder_sport_filtreret.csv", mime="text/csv"
    )
    st.markdown("---")
    st.markdown("**CPI-data fra Danmarks Statistik:**")
    st.dataframe(cpi_data[cpi_data["År"].isin(år_valg)], use_container_width=True, height=200)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='text-align:center; color:#aaa; font-size:11px; margin-top:32px'>
  Spejder Sport Dashboard · Bygget med Streamlit + Claude (Anthropic) ·
  Data: Excel-upload + Danmarks Statistik API (api.statbank.dk/v1/data · tabel PRIS9) ·
  {datetime.now().strftime('%d.%m.%Y')}
</div>
""", unsafe_allow_html=True)
