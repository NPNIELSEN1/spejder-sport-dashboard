"""
Spejder Sport — Salgs-Dashboard med Prophet Forecasting
Kør: streamlit run spejder_sport_dashboard.py
Kræver: pip install streamlit plotly pandas requests openpyxl prophet
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="Spejder Sport Dashboard", page_icon="🏔️",
                   layout="wide", initial_sidebar_state="expanded")

P = {
    "mørkegrøn": "#1B4332", "grøn": "#52B788", "lysgrøn": "#B7E4C7",
    "orange": "#E76F51", "guld": "#F4A261", "blå": "#2171B5",
    "lilla": "#6A3D9A", "bg": "#F4F7F4", "card": "#FFFFFF", "grid": "#DDE8DD",
}

st.markdown(f"""
<style>
  .main, .stApp {{ background-color: {P['bg']}; }}
  .metric-card {{
    background:white; border-left:4px solid {P['grøn']};
    border-radius:8px; padding:16px 20px;
    box-shadow:0 2px 8px rgba(0,0,0,0.06); margin-bottom:8px;
  }}
  .metric-label {{ font-size:11px; color:#666; text-transform:uppercase; letter-spacing:1px; }}
  .metric-value {{ font-size:26px; font-weight:700; color:{P['mørkegrøn']}; }}
  .metric-delta {{ font-size:12px; color:{P['grøn']}; }}
  .section-header {{
    font-size:15px; font-weight:600; color:{P['mørkegrøn']};
    border-bottom:2px solid {P['lysgrøn']}; padding-bottom:6px; margin-bottom:16px;
  }}
  .source-badge {{
    display:inline-block; background:{P['lysgrøn']}; color:{P['mørkegrøn']};
    border-radius:12px; padding:2px 10px; font-size:11px; font-weight:600;
  }}
  .forecast-badge {{
    display:inline-block; background:#EDE7F6; color:{P['lilla']};
    border-radius:12px; padding:2px 10px; font-size:11px; font-weight:600;
  }}
</style>
""", unsafe_allow_html=True)

MAANED = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Maj",6:"Jun",
          7:"Jul",8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec"}

FALLBACK_CPI = {
    "2023-01":7.9,"2023-02":7.1,"2023-03":6.7,"2023-04":6.2,
    "2023-05":5.5,"2023-06":3.7,"2023-07":3.1,"2023-08":2.7,
    "2023-09":2.3,"2023-10":2.3,"2023-11":2.2,"2023-12":2.1,
    "2024-01":1.8,"2024-02":2.0,"2024-03":2.2,"2024-04":2.2,
    "2024-05":1.8,"2024-06":1.5,"2024-07":1.7,"2024-08":1.8,
    "2024-09":1.8,"2024-10":2.0,"2024-11":2.2,"2024-12":2.3,
}

@st.cache_data
def load_sales(file):
    df = pd.read_excel(file)
    df["Måned_navn"] = df["Måned"].map(MAANED)
    df["År_Måned"] = df["År"].astype(str) + "-" + df["Måned"].astype(str).str.zfill(2)
    df["Dato"] = pd.to_datetime(
        df["År"].astype(str) + "-" + df["Måned"].astype(str).str.zfill(2) + "-01")
    return df

@st.cache_data(ttl=3600)
def fetch_cpi():
    url = "https://api.statbank.dk/v1/data"
    payload = {
        "table": "PRIS9", "format": "JSONSTAT", "lang": "da",
        "variables": [
            {"code": "FORMDATO", "values": ["*"]},
            {"code": "ENHED", "values": ["100"]},
            {"code": "Tid", "values": [
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
        data = r.json()["dataset"]
        tids = list(data["dimension"]["Tid"]["category"]["index"].keys())
        vals = data["value"]
        cpi = {t[:4]+"-"+t[5:]: round(float(v),1)
               for t, v in zip(tids, vals) if v is not None}
        return cpi, True
    except Exception:
        return FALLBACK_CPI, False

def cpi_to_df(d):
    rows = []
    for k, v in d.items():
        yr, mo = k.split("-")
        rows.append({"År":int(yr),"Måned":int(mo),"CPI_%":v,
                     "Dato":pd.Timestamp(f"{yr}-{mo}-01")})
    return pd.DataFrame(rows).sort_values("Dato").reset_index(drop=True)

def metric_card(col, label, value, delta=""):
    col.markdown(f"""<div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="metric-delta">{delta}</div>
    </div>""", unsafe_allow_html=True)

def clean_fig(fig, height=380):
    fig.update_layout(
        plot_bgcolor=P["card"], paper_bgcolor=P["card"],
        margin=dict(l=10,r=10,t=30,b=10), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=P["grid"])
    return fig

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏔️ Spejder Sport")
    st.caption("Salgs-Dashboard · AI-øvelse")
    st.divider()
    uploaded = st.file_uploader("Upload Excel-datasæt", type=["xlsx"])
    if uploaded:
        df_raw = load_sales(uploaded)
        st.divider()
        st.markdown("**Filtrering**")
        år_valg     = st.multiselect("📅 År", sorted(df_raw["År"].unique()),
                          default=sorted(df_raw["År"].unique()))
        kat_valg    = st.multiselect("🎒 Produktkategori",
                          sorted(df_raw["Produktkategori_navn"].unique()),
                          default=sorted(df_raw["Produktkategori_navn"].unique()))
        region_valg = st.multiselect("🗺️ Region", sorted(df_raw["Region"].unique()),
                          default=sorted(df_raw["Region"].unique()))
        kanal_valg  = st.multiselect("🛒 Kanal", sorted(df_raw["Kanal"].unique()),
                          default=sorted(df_raw["Kanal"].unique()))
        st.divider()
        vis_cpi = st.toggle("📈 Vis CPI-overlay", value=True)
    else:
        df_raw = år_valg = kat_valg = region_valg = kanal_valg = None
        vis_cpi = True

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<h1 style='color:{P["mørkegrøn"]};margin-bottom:0'>
  🏔️ Spejder Sport — Salgsanalyse & Forecast
</h1>
<p style='color:#666;margin-top:4px'>
  AI-assisteret forretningsanalyse · Excel + Danmarks Statistik API + Prophet AI
</p>""", unsafe_allow_html=True)
st.divider()

if not uploaded:
    st.info("👈 **Upload dit Excel-datasæt i sidebaren for at starte.**")
    st.stop()

df = df_raw[
    df_raw["År"].isin(år_valg) &
    df_raw["Produktkategori_navn"].isin(kat_valg) &
    df_raw["Region"].isin(region_valg) &
    df_raw["Kanal"].isin(kanal_valg)
].copy()

if df.empty:
    st.warning("⚠️ Ingen data matcher filtrene.")
    st.stop()

cpi_raw, api_ok = fetch_cpi()
cpi_data = cpi_to_df(cpi_raw)

_, sc = st.columns([8,2])
with sc:
    if api_ok:
        st.markdown(f"<p style='color:{P['grøn']};font-weight:600'>🟢 DST API live</p>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<p style='color:{P['orange']};font-weight:600'>🟡 DST API offline – fallback</p>",
                    unsafe_allow_html=True)

# ── KPI-KORT ─────────────────────────────────────────────────────────────────
total_salg = df["Salg (DKK)"].sum()
avg_bav    = df["Bruttoavance_%"].mean()
cpi_snit   = cpi_data[cpi_data["År"].isin(år_valg)]["CPI_%"].mean()

if len(år_valg) >= 2:
    sy    = sorted(år_valg)
    s_ny  = df[df["År"]==sy[-1]]["Salg (DKK)"].sum()
    s_gl  = df[df["År"]==sy[-2]]["Salg (DKK)"].sum()
    vækst = (s_ny - s_gl) / s_gl * 100
    real  = vækst - cpi_snit
    vækst_txt = f"+{vækst:.1f}% vs. {sy[-2]}"
else:
    vækst_txt = "—"
    real      = None

k1,k2,k3,k4,k5 = st.columns(5)
metric_card(k1, "Total Salg",     f"{total_salg/1e6:.2f} mio. DKK", vækst_txt)
metric_card(k2, "Bruttoavance",   f"{avg_bav:.1f}%", "Gns. alle kategorier")
metric_card(k3, "Måneder i data", str(df["År_Måned"].nunique()), f"{len(år_valg)} år valgt")
metric_card(k4, "Gns. CPI",       f"{cpi_snit:.1f}%", "Danmarks Statistik")
metric_card(k5, "Real vækst",
            f"{real:+.1f}%" if real is not None else "—", "Salgsvækst minus CPI")
st.markdown("<br>", unsafe_allow_html=True)

# ── FANEBLADE ─────────────────────────────────────────────────────────────────
tab_linje, tab_bar, tab_heat, tab_fc = st.tabs([
    "📈 Linjegraf", "📊 Søjlediagram", "🟦 Heatmap", "🔮 Forecast (Prophet AI)"
])

# ── TAB 1: LINJEGRAF ─────────────────────────────────────────────────────────
with tab_linje:
    st.markdown('<div class="section-header">📈 Månedlig salgsudvikling vs. CPI</div>',
                unsafe_allow_html=True)
    monthly = (df.groupby(["År","Måned","Måned_navn"])["Salg (DKK)"]
                 .sum().reset_index().sort_values(["År","Måned"]))
    fig_l = make_subplots(specs=[[{"secondary_y": True}]])
    colors_år = [P["mørkegrøn"], P["grøn"], P["blå"]]
    for i, år in enumerate(sorted(monthly["År"].unique())):
        s = monthly[monthly["År"]==år]
        fig_l.add_trace(go.Scatter(
            x=s["Måned_navn"], y=s["Salg (DKK)"]/1000, name=str(år),
            mode="lines+markers",
            line=dict(color=colors_år[i%3], width=3),
            marker=dict(size=8, line=dict(width=2, color="white")),
            hovertemplate=f"<b>{år}</b><br>%{{x}}: %{{y:.0f}}k DKK<extra></extra>",
        ), secondary_y=False)
    if vis_cpi:
        cpi_f = cpi_data[cpi_data["År"].isin(år_valg)].copy()
        cpi_f["Måned_navn"] = cpi_f["Måned"].map(MAANED)
        for år in sorted(cpi_f["År"].unique()):
            sc2 = cpi_f[cpi_f["År"]==år]
            fig_l.add_trace(go.Scatter(
                x=sc2["Måned_navn"], y=sc2["CPI_%"], name=f"CPI {år}",
                mode="lines", line=dict(color=P["orange"], width=2, dash="dot"),
                marker=dict(symbol="diamond", size=6),
                hovertemplate=f"CPI {år} — %{{x}}: %{{y:.1f}}%<extra></extra>",
            ), secondary_y=True)
        fig_l.update_yaxes(title_text="CPI (%)", secondary_y=True,
                           tickfont=dict(color=P["orange"]))
    fig_l.update_yaxes(title_text="Salg (1.000 DKK)", secondary_y=False)
    fig_l.update_layout(hovermode="x unified")
    clean_fig(fig_l)
    st.plotly_chart(fig_l, use_container_width=True)
    st.markdown('<span class="source-badge">Excel-data + Danmarks Statistik API (PRIS9)</span>',
                unsafe_allow_html=True)

# ── TAB 2: SØJLEDIAGRAM ──────────────────────────────────────────────────────
with tab_bar:
    st.markdown('<div class="section-header">📊 Salg fordelt på kategori, region og kanal</div>',
                unsafe_allow_html=True)

    def søjle(group_col, farver):
        agg = df.groupby(["År",group_col])["Salg (DKK)"].sum().reset_index()
        agg["Salg_mio"] = agg["Salg (DKK)"]/1e6
        fig = px.bar(agg, x=group_col, y="Salg_mio", color="År",
                     barmode="group", color_discrete_sequence=farver,
                     labels={"Salg_mio":"Salg (mio. DKK)", group_col:""},
                     text=agg["Salg_mio"].apply(lambda v: f"{v:.2f}m"))
        yr_list = sorted(agg["År"].unique())
        if len(yr_list) >= 2:
            for cat in agg[group_col].unique():
                s = agg[agg[group_col]==cat]
                v_gl = s[s["År"]==yr_list[-2]]["Salg (DKK)"].sum()
                v_ny = s[s["År"]==yr_list[-1]]["Salg (DKK)"].sum()
                if v_gl > 0:
                    fig.add_annotation(x=cat, y=v_ny/1e6+0.05,
                                       text=f"+{(v_ny-v_gl)/v_gl*100:.1f}%",
                                       showarrow=False,
                                       font=dict(size=11, color=P["mørkegrøn"]))
        fig.update_traces(textposition="outside", textfont_size=10)
        return clean_fig(fig)

    bt1, bt2, bt3 = st.tabs(["🎒 Produktkategori","🗺️ Region","🛒 Kanal"])
    with bt1:
        st.plotly_chart(søjle("Produktkategori_navn",
            [P["mørkegrøn"],P["grøn"],P["lysgrøn"]]), use_container_width=True)
    with bt2:
        st.plotly_chart(søjle("Region",
            [P["mørkegrøn"],P["grøn"]]), use_container_width=True)
    with bt3:
        st.plotly_chart(søjle("Kanal",
            [P["mørkegrøn"],P["grøn"]]), use_container_width=True)
    st.markdown('<span class="source-badge">Excel-data (interne salgstal)</span>',
                unsafe_allow_html=True)

# ── TAB 3: HEATMAP ───────────────────────────────────────────────────────────
with tab_heat:
    st.markdown('<div class="section-header">🟦 Heatmap — Sæsonmønster & intensitet</div>',
                unsafe_allow_html=True)
    ht1, ht2 = st.tabs(["Absolut salg","YoY vækst (%)"])

    with ht1:
        hm  = df.groupby(["Produktkategori_navn","Måned"])["Salg (DKK)"].sum().reset_index()
        hmp = hm.pivot_table(index="Produktkategori_navn", columns="Måned",
                             values="Salg (DKK)", aggfunc="sum")
        hmp.columns = list(MAANED.values())[:len(hmp.columns)]
        fig_h = go.Figure(go.Heatmap(
            z=hmp.values/1000, x=hmp.columns.tolist(), y=hmp.index.tolist(),
            colorscale=[[0,P["lysgrøn"]],[0.5,P["grøn"]],[1,P["mørkegrøn"]]],
            text=[[f"{v:.0f}k" for v in r] for r in hmp.values/1000],
            texttemplate="%{text}", textfont={"size":11,"color":"white"},
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f}k DKK<extra></extra>",
            colorbar=dict(title="DKK (t.)", ticksuffix="k"),
        ))
        clean_fig(fig_h, height=260)
        fig_h.update_layout(plot_bgcolor=P["card"], paper_bgcolor=P["card"])
        st.plotly_chart(fig_h, use_container_width=True)
        st.caption("Mørkere = højere salg. Q4 er stærkest på tværs af alle kategorier.")

    with ht2:
        if len(år_valg) < 2:
            st.info("Vælg mindst 2 år i sidebaren for at se YoY-vækst.")
        else:
            sy2 = sorted(år_valg)
            h_gl = (df[df["År"]==sy2[-2]].groupby(["Produktkategori_navn","Måned"])
                    ["Salg (DKK)"].sum())
            h_ny = (df[df["År"]==sy2[-1]].groupby(["Produktkategori_navn","Måned"])
                    ["Salg (DKK)"].sum())
            hv = ((h_ny-h_gl)/h_gl*100).reset_index()
            hv.columns = ["Produktkategori_navn","Måned","Vækst_%"]
            hvp = hv.pivot_table(index="Produktkategori_navn", columns="Måned",
                                 values="Vækst_%")
            hvp.columns = list(MAANED.values())[:len(hvp.columns)]
            fig_h2 = go.Figure(go.Heatmap(
                z=hvp.values, x=hvp.columns.tolist(), y=hvp.index.tolist(),
                colorscale="RdYlGn", zmid=0,
                text=[[f"{v:+.1f}%" for v in r] for r in hvp.values],
                texttemplate="%{text}", textfont={"size":11},
                hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.1f}%<extra></extra>",
                colorbar=dict(title=f"Vækst %\n({sy2[-2]}→{sy2[-1]})"),
            ))
            clean_fig(fig_h2, height=260)
            fig_h2.update_layout(plot_bgcolor=P["card"], paper_bgcolor=P["card"])
            st.plotly_chart(fig_h2, use_container_width=True)
            st.caption(f"Grøn = vækst · Rød = fald ({sy2[-2]} → {sy2[-1]})")
    st.markdown('<span class="source-badge">Excel-data (interne salgstal)</span>',
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4: PROPHET FORECAST
# ════════════════════════════════════════════════════════════════════════════
with tab_fc:
    st.markdown('<div class="section-header">🔮 AI-Forecast med Meta Prophet</div>',
                unsafe_allow_html=True)

    try:
        from prophet import Prophet
        prophet_ok = True
    except ImportError:
        prophet_ok = False

    if not prophet_ok:
        st.error("""
**Prophet er ikke installeret.**

Kør denne kommando i terminalen og genstart appen:
```
pip install prophet
```
""")
        st.stop()

    # Indstillinger
    st.markdown("#### ⚙️ Indstillinger")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        fc_kat = st.selectbox("🎒 Produktkategori til forecast",
            ["Alle kategorier"] + sorted(df_raw["Produktkategori_navn"].unique()))
    with fc2:
        fc_mdr = st.slider("📅 Forecastperiode (måneder)", 3, 24, 12, 3)
    with fc3:
        fc_int = st.slider("📊 Usikkerhedsinterval (%)", 70, 95, 80, 5)

    fc4, fc5 = st.columns(2)
    with fc4:
        brug_cpi = st.toggle("📈 Inkluder CPI som variabel", value=True,
            help="Bruger inflationsdata fra DST som ekstra variabel i modellen")
    with fc5:
        vis_komp = st.toggle("🔍 Vis trend-komponenter", value=False,
            help="Viser trend og sæson separat")
    st.divider()

    # Byg datasæt
    if fc_kat == "Alle kategorier":
        df_fc = df_raw.groupby("Dato")["Salg (DKK)"].sum().reset_index()
    else:
        df_fc = (df_raw[df_raw["Produktkategori_navn"]==fc_kat]
                 .groupby("Dato")["Salg (DKK)"].sum().reset_index())

    df_prophet = df_fc.rename(columns={"Dato":"ds","Salg (DKK)":"y"})
    df_prophet["ds"] = pd.to_datetime(df_prophet["ds"])
    df_prophet = df_prophet.sort_values("ds").reset_index(drop=True)

    if brug_cpi:
        cpi_m = cpi_data[["Dato","CPI_%"]].rename(columns={"Dato":"ds","CPI_%":"cpi"})
        cpi_m["ds"] = pd.to_datetime(cpi_m["ds"])
        df_prophet = df_prophet.merge(cpi_m, on="ds", how="left")
        df_prophet["cpi"] = df_prophet["cpi"].fillna(df_prophet["cpi"].mean())

    with st.spinner("🤖 Prophet AI beregner forecast..."):
        try:
            model = Prophet(
                interval_width=fc_int/100,
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                seasonality_mode="multiplicative",
                changepoint_prior_scale=0.05,
            )
            if brug_cpi:
                model.add_regressor("cpi")

            model.fit(df_prophet)

            future = model.make_future_dataframe(periods=fc_mdr, freq="MS")
            if brug_cpi:
                future = future.merge(cpi_m[["ds","cpi"]], on="ds", how="left")
                future["cpi"] = future["cpi"].fillna(df_prophet["cpi"].iloc[-1])

            forecast = model.predict(future)
            last_hist = df_prophet["ds"].max()
            hist_fc   = forecast[forecast["ds"] <= last_hist]
            pred_fc   = forecast[forecast["ds"] >  last_hist]

            # Forecast-graf
            fig_fc = go.Figure()

            # Usikkerhedsbånd
            fig_fc.add_trace(go.Scatter(
                x=pd.concat([pred_fc["ds"], pred_fc["ds"].iloc[::-1]]),
                y=pd.concat([pred_fc["yhat_upper"]/1000,
                              pred_fc["yhat_lower"].iloc[::-1]/1000]),
                fill="toself", fillcolor="rgba(106,61,154,0.15)",
                line=dict(color="rgba(255,255,255,0)"),
                name=f"Usikkerhed ({fc_int}%)", hoverinfo="skip",
            ))
            # Historisk model-fit
            fig_fc.add_trace(go.Scatter(
                x=hist_fc["ds"], y=hist_fc["yhat"]/1000,
                mode="lines", name="Model (historik)",
                line=dict(color=P["grøn"], width=2, dash="dot"), opacity=0.7,
            ))
            # Faktisk salg
            fig_fc.add_trace(go.Scatter(
                x=df_prophet["ds"], y=df_prophet["y"]/1000,
                mode="lines+markers", name="Faktisk salg",
                line=dict(color=P["mørkegrøn"], width=3),
                marker=dict(size=7, line=dict(width=2, color="white")),
                hovertemplate="%{x|%b %Y}: %{y:.0f}k DKK<extra>Faktisk</extra>",
            ))
            # Forecast
            fig_fc.add_trace(go.Scatter(
                x=pred_fc["ds"], y=pred_fc["yhat"]/1000,
                mode="lines+markers", name="Forecast",
                line=dict(color=P["lilla"], width=3),
                marker=dict(size=7, symbol="diamond",
                            line=dict(width=2, color="white")),
                hovertemplate="%{x|%b %Y}: %{y:.0f}k DKK<extra>Forecast</extra>",
            ))
            # Skillelinje
            fig_fc.add_vline(
                x=last_hist.timestamp()*1000,
                line_dash="dash", line_color=P["orange"],
                annotation_text="← Historik | Forecast →",
                annotation_position="top",
                annotation_font_color=P["orange"],
            )
            fig_fc.update_layout(
                yaxis_title="Salg (1.000 DKK)", hovermode="x unified",
                plot_bgcolor=P["card"], paper_bgcolor=P["card"],
                legend=dict(orientation="h", yanchor="bottom",
                            y=1.02, xanchor="right", x=1),
                margin=dict(l=10,r=10,t=40,b=10), height=460,
            )
            fig_fc.update_xaxes(showgrid=False)
            fig_fc.update_yaxes(gridcolor=P["grid"])

            st.markdown(f"#### Salgsforecast — {fc_kat} (+{fc_mdr} mdr. · {fc_int}% interval)")
            st.plotly_chart(fig_fc, use_container_width=True)

            # Forecast KPI-kort
            fc_total  = pred_fc["yhat"].sum()
            fc_max_md = pred_fc.loc[pred_fc["yhat"].idxmax(),"ds"].strftime("%b %Y")
            fc_max_v  = pred_fc["yhat"].max()
            hist_snit = df_prophet["y"].mean()
            fc_snit   = pred_fc["yhat"].mean()
            fc_vækst  = (fc_snit - hist_snit) / hist_snit * 100

            fk1,fk2,fk3,fk4 = st.columns(4)
            metric_card(fk1, f"Forecast total ({fc_mdr} mdr.)",
                        f"{fc_total/1e6:.2f} mio. DKK", "")
            metric_card(fk2, "Stærkeste forecast-måned",
                        fc_max_md, f"{fc_max_v/1000:.0f}k DKK")
            metric_card(fk3, "Gns. vækst vs. historik",
                        f"{fc_vækst:+.1f}%", "Forecast vs. historisk snit")
            metric_card(fk4, "AI-model",
                        "Prophet",
                        "Meta · Sæson + CPI" if brug_cpi else "Meta · Sæson")
            st.markdown("<br>", unsafe_allow_html=True)

            # Trendkomponenter
            if vis_komp:
                st.markdown("#### 🔍 Trend- og sæsonkomponenter")
                comp = make_subplots(rows=2, cols=1,
                    subplot_titles=["Overordnet trend","Sæsonmønster (månedligt)"],
                    vertical_spacing=0.18)
                comp.add_trace(go.Scatter(
                    x=forecast["ds"], y=forecast["trend"]/1000,
                    mode="lines", name="Trend",
                    line=dict(color=P["mørkegrøn"], width=2.5)), row=1, col=1)
                if "yearly" in forecast.columns:
                    comp.add_trace(go.Scatter(
                        x=forecast["ds"], y=forecast["yearly"]/1000,
                        mode="lines", name="Sæsonalitet",
                        line=dict(color=P["grøn"], width=2.5)), row=2, col=1)
                comp.update_layout(
                    plot_bgcolor=P["card"], paper_bgcolor=P["card"],
                    height=420, showlegend=False,
                    margin=dict(l=10,r=10,t=40,b=10))
                comp.update_xaxes(showgrid=False)
                comp.update_yaxes(gridcolor=P["grid"])
                st.plotly_chart(comp, use_container_width=True)

            # Forecast-tabel
            with st.expander("📋 Vis og download forecast-tabel"):
                fc_tbl = pred_fc[["ds","yhat","yhat_lower","yhat_upper"]].copy()
                fc_tbl.columns = ["Dato","Forecast (DKK)",
                                   f"Nedre grænse ({fc_int}%)",
                                   f"Øvre grænse ({fc_int}%)"]
                fc_tbl["Dato"] = fc_tbl["Dato"].dt.strftime("%b %Y")
                for col in fc_tbl.columns[1:]:
                    fc_tbl[col] = fc_tbl[col].apply(lambda v: f"{v:,.0f} DKK")
                st.dataframe(fc_tbl, use_container_width=True, hide_index=True)
                csv_fc = pred_fc[["ds","yhat","yhat_lower","yhat_upper"]]\
                             .to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Download forecast som CSV", data=csv_fc,
                    file_name=f"spejder_forecast_{fc_mdr}mdr.csv", mime="text/csv")

            # Forklaring
            st.markdown("---")
            st.markdown(f"""
            <div style='background:white; border-left:4px solid {P["lilla"]};
                 border-radius:8px; padding:16px 20px;
                 box-shadow:0 2px 8px rgba(0,0,0,0.05)'>
            <b style='color:{P["mørkegrøn"]}'>🤖 Hvad gør Prophet?</b><br><br>
            Prophet er Metas open source-tidsseriemodel der opdeler salget i tre lag:
            <b>trend</b> (langsigtet retning), <b>sæsonalitet</b> (Q4-peak, forårsopgang)
            og <b>eksterne variable</b> — her CPI fra Danmarks Statistik.
            Usikkerhedsbåndet viser det interval hvori {fc_int}% af alle sandsynlige
            fremtidsscenarier forventes at ligge. Jo bredere bånd, jo mere usikker modellen er.
            </div>""", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"⚠️ Forecast fejlede: {e}")
            st.info("Tjek at datasættet har mindst 12 måneder med data.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f'<span class="forecast-badge">Model: Meta Prophet · Data: Excel + Danmarks Statistik API</span>',
                unsafe_allow_html=True)

# ── RAW DATA ─────────────────────────────────────────────────────────────────
with st.expander("🗃️ Se rådata og eksportér"):
    st.dataframe(df.drop(columns=["Produktkategori"], errors="ignore"),
                 use_container_width=True, height=280)
    st.download_button("⬇️ Download filtreret data som CSV",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="spejder_filtreret.csv", mime="text/csv")

st.markdown(f"""
<div style='text-align:center;color:#aaa;font-size:11px;margin-top:32px'>
  Spejder Sport Dashboard · Streamlit + Claude (Anthropic) + Meta Prophet ·
  Danmarks Statistik API (PRIS9) · {datetime.now().strftime('%d.%m.%Y')}
</div>""", unsafe_allow_html=True)
