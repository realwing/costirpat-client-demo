# client_app.py
# ===========================================================================
# CO-STIRPAT PUBLIC CLIENT (Streamlit) — UI ONLY
# ---------------------------------------------------------------------------
# This file contains NO core model logic and NO data file. It only:
#   1. collects parameters from the user (sliders),
#   2. POSTs them to the PRIVATE API server,
#   3. renders the RESULT DATA (charts + table) that the server returns.
#
# Even if someone inspects this app / its iframe, they see only this shell —
# the simulation math (model_engine.py, appendix_d.py) and the .xlsm live on
# the private server and are never shipped here.
#
# Run:
#   pip install -r requirements_client.txt
#   export COSTIRPAT_API_URL="https://<your-private-server>:8000"
#   export COSTIRPAT_API_KEY="<same-secret-as-server>"
#   streamlit run client_app.py
# ===========================================================================

import os
import requests
import streamlit as st
import plotly.graph_objects as go


def _cfg(name, default=""):
    """Read a setting from Streamlit secrets first (Streamlit Cloud), then an
    environment variable (local run), then a default. This lets the same file
    run both on Streamlit Community Cloud (via Secrets) and locally (via env
    vars) with no code changes."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:        # noqa  (st.secrets may be absent locally)
        pass
    return os.environ.get(name, default)


API_URL = _cfg("COSTIRPAT_API_URL", "http://localhost:8000")
API_KEY = _cfg("COSTIRPAT_API_KEY", "")
# Endpoint path: "/simulate" (default) or "/api/v1/simulate" — both work server-side.
API_PATH = _cfg("COSTIRPAT_API_PATH", "/simulate")
TIMEOUT = 60

st.set_page_config(layout="wide", page_title="CO-STIRPAT Dynamic System")
st.title("🌿 CO-STIRPAT Climate-Fiscal Dynamic Simulator")
st.markdown(
    "Korea's Green Investment, Fiscal Sustainability, and NDC Compliance Analysis"
)

with st.expander("📚 References — peer-reviewed research & policy work",
                 expanded=True):
    st.markdown(
        "- Jin, I. (2023). *Probability of Achieving NDC and Implications for "
        "Climate Policy: CO-STIRPAT Approach.* Journal of Economic Analysis, "
        "2(4), 38. "
        "[doi:10.58567/jea02040005]"
        "(https://doi.org/10.58567/jea02040005)\n"
        "- Jin, I. (2024). *Emission Prediction, Global Stocktake, and NDC "
        "Update: CO-STIRPAT Dynamic System.* Green and Low-Carbon Economy, "
        "3(3), 213–219. "
        "[doi:10.47852/bonviewGLCE42022058]"
        "(https://doi.org/10.47852/bonviewGLCE42022058)\n"
        "- Jin, I. (2025). *Aligning green budgeting with nationally "
        "determined contributions.* Climate Policy, 26(2), 1–14. "
        "[doi:10.1080/14693062.2025.2502108]"
        "(https://doi.org/10.1080/14693062.2025.2502108)\n"
        "- Jin, I. (2026). *Fiscal Costs-Benefits of Responding to Extreme "
        "Weather Damage: Extended Climate Budget Tool Based on OECD EDISON.* "
        "4th NABO–OECD Annual Conference of Asian PBOs. "
        "[doi:10.13140/RG.2.2.33492.77443]"
        "(https://doi.org/10.13140/RG.2.2.33492.77443)"
    )


# ---------------------------------------------------------------------------
# API call (the only thing this client does besides drawing)
# ---------------------------------------------------------------------------
def call_simulate(shock_nominal_tr, shock_year_b, shock_year_e,
                  carbon_rate_2050=300000, user_wallet=None):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    payload = {
        "shock_nominal_tr": shock_nominal_tr,
        "shock_year_b": shock_year_b,
        "shock_year_e": shock_year_e,
        "carbon_rate_2050": carbon_rate_2050,
    }
    if user_wallet:                       # only sent when the NFT gate is in use
        payload["user_wallet"] = user_wallet
    resp = requests.post(f"{API_URL}{API_PATH}", json=payload,
                         headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ----------------- Sidebar controls -----------------
st.sidebar.header("🕹️ Scenario Controls")
shock_nominal_tr = st.sidebar.slider(
    "Green investment shock (trillion KRW / yr)", 0, 30, 10, step=5)
shock_window = st.sidebar.select_slider(
    "Shock window (end year)", options=[2028, 2030, 2032, 2035], value=2030)
carbon_rate_2050 = st.sidebar.slider(
    "2050 carbon-price target (KRW / tCO₂)",
    min_value=50000, max_value=400000, value=300000, step=10000,
    help="Scales the ETS missed-target penalty (Comp3). Higher price → "
         "larger fiscal cost of missing NDC targets.")

EXPECTED_BUILD = "2025-06-26-engine-v9d"

# --- Probe server health first: tells us whether the NFT gate is enforced ---
server_health = {}
try:
    server_health = requests.get(f"{API_URL}/health", timeout=10).json()
except Exception:        # noqa
    server_health = {}
nft_gate_on = bool(server_health.get("nft_gate"))
nft_contract = server_health.get("nft_contract")

# --- MetaMask sign-in (only meaningful when the NFT gate is on) -------------
# We verify wallet OWNERSHIP in the browser via MetaMask, then the SERVER
# independently checks that wallet's NFT balance on-chain. A pasted address
# cannot bypass anything: the server is the sole authority on NFT possession.
try:
    from streamlit_js_eval import streamlit_js_eval
    _HAS_JS_EVAL = True
except Exception:        # noqa
    _HAS_JS_EVAL = False

if "wallet" not in st.session_state:
    st.session_state.wallet = _cfg("COSTIRPAT_WALLET", "") or None

# Always-visible copyright (sidebar shows regardless of where the app stops)
st.sidebar.markdown(
    "<div style='color:gray; font-size:0.8em;'>"
    "© 2026 MT1308. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)

with st.sidebar.expander("🔐 NFT license", expanded=nft_gate_on):
    if nft_gate_on:
        st.caption("This server requires a COSTIRPAT NFT license.")
        if nft_contract:
            st.caption(f"Contract: {nft_contract[:6]}…{nft_contract[-4:]}")
        if st.session_state.wallet:
            w = st.session_state.wallet
            st.success(f"Wallet: {w[:6]}…{w[-4:]}")
            if st.button("Disconnect"):
                st.session_state.wallet = None
                st.rerun()
        else:
            if _HAS_JS_EVAL:
                if st.button("🦊 Connect MetaMask", type="primary"):
                    acct = streamlit_js_eval(
                        js_expressions=(
                            "window.ethereum ? "
                            "window.ethereum.request({method:'eth_requestAccounts'})"
                            ".then(a => a[0]) : null"),
                        key="mm_connect", want_output=True)
                    if acct:
                        st.session_state.wallet = acct
                        st.rerun()
                    else:
                        st.warning("MetaMask not detected or request rejected.")
            else:
                st.info("streamlit_js_eval not installed; paste wallet address.")
                manual = st.text_input("Wallet address", value="")
                if manual.strip():
                    st.session_state.wallet = manual.strip()
                    st.rerun()
    else:
        st.caption("NFT gate is OFF on this server — no wallet required.")

user_wallet = st.session_state.wallet if nft_gate_on else None

with st.sidebar.expander("🔌 Server status", expanded=False):
    st.caption(f"API: {API_URL}{API_PATH}")
    if server_health.get("status") == "ok":
        st.success("Server: ok")
        build = server_health.get("build")
        if build == EXPECTED_BUILD:
            st.caption(f"Build: {build} ✓")
        elif build:
            st.warning(f"Build mismatch: server={build}, "
                       f"client expects {EXPECTED_BUILD}. Restart the server.")
        else:
            st.warning("Server reports no build tag — outdated process. Restart it.")
        st.caption(f"NFT gate: {'ON' if nft_gate_on else 'OFF'}")
    else:
        st.error("Server unreachable. Check COSTIRPAT_API_URL and that it is running.")

# --- Gate the app: if NFT enforced but no wallet connected, stop here -------
if nft_gate_on and not user_wallet:
    st.info("🔐 Connect your MetaMask wallet (sidebar) to run the simulation. "
            "A COSTIRPAT NFT license is required.")
    st.stop()


# ----------------- Call server & render -----------------
try:
    with st.spinner("🔄 Running CO-STIRPAT dynamic simulation — solving the "
                    "non-linear system and decomposing fiscal components…"):
        data = call_simulate(int(shock_nominal_tr), 2026, int(shock_window),
                             carbon_rate_2050=int(carbon_rate_2050),
                             user_wallet=user_wallet)
except requests.HTTPError as e:        # noqa
    code = e.response.status_code if e.response is not None else None
    if code == 403:
        st.error("❌ Access denied: this wallet holds no COSTIRPAT NFT license.")
    elif code == 400:
        st.error("❌ Invalid request (check the wallet address).")
    elif code == 401:
        st.error("❌ Unauthorized: missing or wrong API key.")
    else:
        st.error(f"Server error ({code}).")
    st.stop()
except Exception as e:        # noqa
    st.error(f"Could not reach the simulation server: {e}")
    st.info("Check COSTIRPAT_API_URL / COSTIRPAT_API_KEY and that the private "
            "server is running.")
    st.stop()

years = data["years"]

# ---- shared chart styling ------------------------------------------------
GREY = "#7F8C8D"
GREEN = "#2ECC71"
BLUE = "#3498DB"
RED = "#E74C3C"


def style_layout(fig, y_title, height=380):
    """Apply a clean, professional theme shared by all line charts."""
    fig.update_layout(
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=40, r=30, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="rgba(189,195,199,0.3)",
                   tickmode="linear", dtick=5),
        yaxis=dict(showgrid=True, gridcolor="rgba(189,195,199,0.3)",
                   title=y_title, zeroline=False),
    )
    return fig


def gap_line_chart(yb, ya, y_title, base_name="Baseline",
                   alte_name="Green Investment", fill=True, height=380):
    """Two-path line chart; shades the gap between the paths with tonexty."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=yb, mode="lines", name=base_name,
        line=dict(color=GREY, width=2, dash="dash"),
        hovertemplate="%{y:.3f}"))
    fig.add_trace(go.Scatter(
        x=years, y=ya, mode="lines", name=alte_name,
        line=dict(color=GREEN, width=3),
        fill="tonexty" if fill else None,
        fillcolor="rgba(46,204,113,0.15)",
        hovertemplate="%{y:.3f}"))
    return style_layout(fig, y_title, height)


# ============================ TABS ========================================
tab_emis, tab_cost, tab_macro = st.tabs([
    "📈 Emissions & NDC Path",
    "📊 Six Fiscal Cost Components",
    "🏛️ Macro & Debt Sustainability",
])

# ---- Tab 1: Emissions ----------------------------------------------------
with tab_emis:
    st.subheader("Carbon Emissions Path (2025–2050)")
    if data.get("emis_base"):
        fig_emis = gap_line_chart(
            data["emis_base"], data["emis_alte"],
            "Emissions (MtCO₂)", height=420)
        st.plotly_chart(fig_emis, use_container_width=True)
        gap_2050 = data["emis_base"][-1] - data["emis_alte"][-1]
        st.caption(
            f"Shaded area = emissions avoided by green investment. "
            f"By 2050 the green path is {gap_2050:.1f} MtCO₂ below baseline "
            f"({data['emis_base'][-1]:.1f} → {data['emis_alte'][-1]:.1f})."
        )
    else:
        st.info("Emission series not available from the server.")

# ---- Tab 2: Six fiscal cost components -----------------------------------
with tab_cost:
    st.subheader("Six Fiscal Cost Components (OECD EDISON basis)")
    bcr = data["bcr"]
    cost_total = data.get("cost_total", 0.0)
    if cost_total == 0:
        st.metric("Benefit / |Cost| Ratio", "n/a", delta="no shock applied")
    else:
        st.metric("Benefit / |Cost| Ratio", f"{bcr:.3f}",
                  delta=f"{bcr - 1.0:+.3f} (vs break-even)")

    # Waterfall of present values (real server data, not hard-coded)
    comps = data["components"]
    labels = [c["component"] for c in comps]
    pvs = [float(c["pv_tr"]) for c in comps]
    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative"] * len(pvs) + ["total"],
        x=labels + ["Net Benefit"],
        y=pvs + [0],
        text=[(f"+{v:.1f}" if v >= 0 else f"{v:.1f}") for v in pvs] + ["Sum"],
        textposition="outside",
        connector={"line": {"color": GREY}},
        increasing={"marker": {"color": GREEN}},
        decreasing={"marker": {"color": RED}},
        totals={"marker": {"color": BLUE}},
    ))
    fig_wf.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=420, margin=dict(l=20, r=20, t=30, b=80),
        yaxis=dict(title="Present value (trillion KRW)", zeroline=True,
                   zerolinecolor="rgba(127,140,141,0.5)"),
        xaxis=dict(tickangle=-30),
    )
    st.plotly_chart(fig_wf, use_container_width=True)

    # Per-year stacked detail + reference table
    cpaths = data.get("component_paths")
    if cpaths:
        # Notebook-synced component palette (OECD EDISON six-component colours).
        comp_meta = [
            ("comp1", "Comp1 Indirect macro", "#5B7FA6"),
            ("comp2", "Comp2 Weather damage", "#C0533A"),
            ("comp3", "Comp3 Missed target",  "#C62A47"),
            ("comp4", "Comp4 Health",         "#8B4A8B"),
            ("comp5", "Comp5 Lost tax",       "#C89A00"),
            ("comp6", "Comp6 Expenditure",    "#2E7D55"),
        ]
        fig_stack = go.Figure()
        for key, label, color in comp_meta:
            if key in cpaths:
                fig_stack.add_trace(go.Bar(
                    x=years, y=cpaths[key], name=label, marker_color=color))
        fig_stack.update_layout(
            barmode="relative",
            title="Annual contribution by component",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Year", yaxis_title="Annual value (trillion KRW)",
            height=380, margin=dict(l=20, r=20, t=40, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig_stack, use_container_width=True)

    st.table([
        {"Component": c["component"], "Type": c["type"],
         "PV (Tr KRW)": round(c["pv_tr"], 2)}
        for c in comps
    ])

# ---- Tab 3: Macro & debt -------------------------------------------------
with tab_macro:
    st.subheader("Key Fiscal-Sustainability Indicators (2050)")

    # KPI row — all values come from the real server response.
    net_benefit = data["benefit_total"] - data["cost_total"]
    ratio_b = data.get("gdp_ratio_base") or []
    ratio_a = data.get("gdp_ratio_alte") or []
    if ratio_b and ratio_a:
        gdp_2050_alte = ratio_a[-1]
        gdp_diff_pp = (ratio_a[-1] - ratio_b[-1]) * 100.0
    else:
        gdp_2050_alte, gdp_diff_pp = float("nan"), 0.0

    bcr_val = data["bcr"]
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Net Benefit (PV)", f"{net_benefit:,.1f} tr KRW",
                  delta=f"vs {shock_nominal_tr} tr/yr investment")
    with k2:
        status = "🎯 favourable" if bcr_val > 1.0 else "⚠️ below break-even"
        st.metric("Benefit / |Cost| Ratio", f"{bcr_val:.3f}", delta=status)
    with k3:
        st.metric("Real GDP index 2050 (green)", f"{gdp_2050_alte:.4f}",
                  delta=f"{gdp_diff_pp:+.2f} pp vs baseline")

    st.divider()
    st.subheader("Real GDP Path (2025–2050)")
    gdp_mode = st.radio(
        "Real GDP display",
        ["Normalised index (2018=1) — matches notebook",
         "Level (trillion KRW)"],
        horizontal=True, index=0, label_visibility="collapsed")

    gdpr_2018 = data.get("gdpr_2018")
    ratio_base = data.get("gdp_ratio_base")
    ratio_alte = data.get("gdp_ratio_alte")
    if ratio_base is None or ratio_alte is None:
        if gdpr_2018:
            ratio_base = [v / gdpr_2018 for v in data["gdp_base"]]
            ratio_alte = [v / gdpr_2018 for v in data["gdp_alte"]]
        else:
            b0 = data["gdp_base"][0] if data["gdp_base"] else 1.0
            a0 = data["gdp_alte"][0] if data["gdp_alte"] else 1.0
            ratio_base = [v / b0 for v in data["gdp_base"]]
            ratio_alte = [v / a0 for v in data["gdp_alte"]]

    if ratio_base and (ratio_base[0] > 3.0 or ratio_base[0] <= 0):
        st.warning(
            f"Real GDP index starts at {ratio_base[0]:.1f} (expected ≈1.1-1.4). "
            "The simulation server may be running an outdated build. "
            "Restart it and refresh."
        )

    if gdp_mode.startswith("Level"):
        y_base, y_alte = data["gdp_base"], data["gdp_alte"]
        y_title = "Real GDP (trillion KRW, 2018 base)"
    else:
        y_base, y_alte = ratio_base, ratio_alte
        y_title = "Real GDP index (gdpr, 2018 = 1)"

    fig_gdp = gap_line_chart(y_base, y_alte, y_title)
    st.plotly_chart(fig_gdp, use_container_width=True)

    if data["debt_gdp_base"]:
        st.subheader("Public Debt-to-GDP Ratio (2025–2050)")
        # Lower debt is better, so colour the green path blue and shade the gap.
        fig_d2g = go.Figure()
        fig_d2g.add_trace(go.Scatter(
            x=years, y=data["debt_gdp_base"], mode="lines", name="Baseline",
            line=dict(color=GREY, width=2, dash="dash"),
            hovertemplate="%{y:.1f}%"))
        fig_d2g.add_trace(go.Scatter(
            x=years, y=data["debt_gdp_alte"], mode="lines",
            name="Green Investment",
            line=dict(color=BLUE, width=3),
            fill="tonexty", fillcolor="rgba(52,152,219,0.12)",
            hovertemplate="%{y:.1f}%"))
        style_layout(fig_d2g, "Debt / GDP (%)")
        st.plotly_chart(fig_d2g, use_container_width=True)

st.caption(
    f"Scenario: {shock_nominal_tr} tr KRW/yr nominal shock over "
    f"2026-{int(shock_window)} · 2050 carbon-price target "
    f"{int(carbon_rate_2050):,} KRW/tCO₂ · real shock "
    f"{data['shock_real_tr']:.2f} tr (÷ inflation {data['shock_infl']:.3f}) · "
    f"benefit total {data['benefit_total']:.1f}, cost total "
    f"{data['cost_total']:.1f} tr KRW."
)

st.divider()
st.markdown(
    "<div style='text-align:center; color:gray; font-size:0.85em;'>"
    "© 2026 MT1308. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)
