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


# ---------------------------------------------------------------------------
# API call (the only thing this client does besides drawing)
# ---------------------------------------------------------------------------
def call_simulate(shock_nominal_tr, shock_year_b, shock_year_e, user_wallet=None):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    payload = {
        "shock_nominal_tr": shock_nominal_tr,
        "shock_year_b": shock_year_b,
        "shock_year_e": shock_year_e,
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

EXPECTED_BUILD = "2025-06-26-engine-v9c"

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
    data = call_simulate(int(shock_nominal_tr), 2026, int(shock_window),
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

# Single-column layout: table on top, then the four charts stacked vertically.
st.subheader("📊 Six Fiscal Cost Components")
bcr = data["bcr"]
cost_total = data.get("cost_total", 0.0)
if cost_total == 0:
    st.metric("Benefit / |Cost| Ratio", "n/a",
              delta="no shock applied")
else:
    st.metric("Benefit / |Cost| Ratio", f"{bcr:.3f}",
              delta=f"{bcr - 1.0:+.3f} (vs break-even)")
st.table([
    {"Component": c["component"], "Type": c["type"],
     "PV (Tr KRW)": round(c["pv_tr"], 2)}
    for c in data["components"]
])

st.subheader("📈 Macro-Fiscal Paths")

# The notebook (plot_scenario_comparison) plots the normalised gdpr_f ratio
# (2018 = 1). Default to that so the chart matches the notebook analysis;
# offer a toggle to view the trillion-KRW level.
gdp_mode = st.radio(
    "Real GDP display",
    ["Normalised index (2018=1) — matches notebook",
     "Level (trillion KRW)"],
    horizontal=True, index=0, label_visibility="collapsed")

# Resilient to older server responses that may not include the ratio
# series: derive the index from the level if needed.
gdpr_2018 = data.get("gdpr_2018")
ratio_base = data.get("gdp_ratio_base")
ratio_alte = data.get("gdp_ratio_alte")
if ratio_base is None or ratio_alte is None:
    if gdpr_2018:
        ratio_base = [v / gdpr_2018 for v in data["gdp_base"]]
        ratio_alte = [v / gdpr_2018 for v in data["gdp_alte"]]
    else:
        # last-resort: normalise each series to its own first value
        b0 = data["gdp_base"][0] if data["gdp_base"] else 1.0
        a0 = data["gdp_alte"][0] if data["gdp_alte"] else 1.0
        ratio_base = [v / b0 for v in data["gdp_base"]]
        ratio_alte = [v / a0 for v in data["gdp_alte"]]

# Sanity guard: the 2025 real-GDP index should sit near ~1.1-1.4 (2018=1).
# A first point far outside that band (e.g. a spike to ~20 that then
# collapses) means the simulation server returned stale/garbage output —
# almost always an old server process from before the engine fixes.
if ratio_base and (ratio_base[0] > 3.0 or ratio_base[0] <= 0):
    st.warning(
        f"Real GDP index starts at {ratio_base[0]:.1f} (expected ≈1.1-1.4). "
        "This indicates the simulation server is running an outdated build. "
        "Restart the server (Ctrl+C, then `uvicorn server:app --host 0.0.0.0 "
        "--port 8000`) and refresh."
    )

if gdp_mode.startswith("Level"):
    y_base, y_alte = data["gdp_base"], data["gdp_alte"]
    y_title = "Real GDP (trillion KRW, 2018 base)"
else:
    y_base, y_alte = ratio_base, ratio_alte
    y_title = "Real GDP index (gdpr, 2018 = 1)"

# Chart 1: Real GDP path
fig_gdp = go.Figure()
fig_gdp.add_trace(go.Scatter(x=years, y=y_base, name="Baseline",
                             line=dict(color="gray", dash="dash")))
fig_gdp.add_trace(go.Scatter(x=years, y=y_alte,
                             name="Green Investment",
                             line=dict(color="green", width=3)))
fig_gdp.update_layout(
    title="Real GDP Path (2025-2050)", xaxis_title="Year",
    yaxis_title=y_title,
    height=360, margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig_gdp, use_container_width=True)

# Chart 2: Public Debt-to-GDP ratio
if data["debt_gdp_base"]:
    fig_d2g = go.Figure()
    fig_d2g.add_trace(go.Scatter(x=years, y=data["debt_gdp_base"],
                                 name="Baseline",
                                 line=dict(color="gray", dash="dash")))
    fig_d2g.add_trace(go.Scatter(x=years, y=data["debt_gdp_alte"],
                                 name="Green Investment",
                                 line=dict(color="blue", width=3)))
    fig_d2g.update_layout(
        title="Public Debt-to-GDP Ratio (2025-2050)", xaxis_title="Year",
        yaxis_title="Debt / GDP (%)",
        height=360, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_d2g, use_container_width=True)

# Chart 3: Six fiscal cost components, stacked by year
cpaths = data.get("component_paths")
if cpaths:
    comp_meta = [
        ("comp1", "Comp1 Indirect macro", "#2e7d32"),
        ("comp2", "Comp2 Weather damage", "#66bb6a"),
        ("comp3", "Comp3 Missed target",  "#a5d6a7"),
        ("comp4", "Comp4 Health",         "#1565c0"),
        ("comp5", "Comp5 Lost tax",       "#ef6c00"),
        ("comp6", "Comp6 Expenditure",    "#c62828"),
    ]
    fig_stack = go.Figure()
    for key, label, color in comp_meta:
        if key in cpaths:
            fig_stack.add_trace(go.Bar(
                x=years, y=cpaths[key], name=label, marker_color=color))
    fig_stack.update_layout(
        barmode="relative",   # stacks positives up, negatives down
        title="Six Fiscal Cost Components, Stacked by Year",
        xaxis_title="Year", yaxis_title="Annual value (trillion KRW)",
        height=400, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    st.plotly_chart(fig_stack, use_container_width=True)

# Chart 4: Emission path (MtCO2)
if data.get("emis_base"):
    fig_emis = go.Figure()
    fig_emis.add_trace(go.Scatter(x=years, y=data["emis_base"],
                                  name="Baseline",
                                  line=dict(color="gray", dash="dash")))
    fig_emis.add_trace(go.Scatter(x=years, y=data["emis_alte"],
                                  name="Green Investment",
                                  line=dict(color="green", width=3)))
    fig_emis.update_layout(
        title="Carbon Emissions Path (2025-2050)", xaxis_title="Year",
        yaxis_title="Emissions (MtCO₂)",
        height=360, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_emis, use_container_width=True)

st.caption(
    f"Scenario: {shock_nominal_tr} tr KRW/yr nominal shock over "
    f"2026-{int(shock_window)} · real shock {data['shock_real_tr']:.2f} tr "
    f"(÷ inflation {data['shock_infl']:.3f}) · benefit total "
    f"{data['benefit_total']:.1f}, cost total {data['cost_total']:.1f} tr KRW."
)
