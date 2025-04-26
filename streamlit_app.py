# Optimized Streamlit Retirement Simulator with Grid Heatmap and IRR Visualization
import streamlit as st
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy_financial as npf
import random
import matplotlib
from joblib import Parallel, delayed


matplotlib.rcParams['font.family'] = ['Arial Unicode MS', 'Heiti TC', 'sans-serif']
st.set_page_config(layout="wide")


SCENARIOS_FIXED = [
    (3, -0.02, 0.25, 0.01, 0.08, "2008–2010 Financial Crisis"),
    (3, 0.10, 0.18, 0.03, 0.05, "2011–2013 Bull Market Recovery"),
    (2, 0.01, 0.20, 0.02, 0.06, "2014–2015 European Debt Crisis"),
    (5, 0.09, 0.16, 0.04, 0.05, "2016–2020 Continued Bull Market"),
    (2, -0.05, 0.30, 0.00, 0.10, "2021–2022 COVID-19"),
    (3, 0.06, 0.18, 0.01, 0.08, "2023–2025 Post-Pandemic Recovery"),
    (30, 0.07, 0.14, 0.03, 0.05, "2026+ Stable Growth")
]

@st.cache_data(show_spinner=False)
def generate_random_scenarios(seed=42):
    rng = random.Random(seed)
    blocks = rng.sample(SCENARIOS_FIXED[:-1], k=len(SCENARIOS_FIXED)-1)
    final = SCENARIOS_FIXED[-1]
    total_years = sum([b[0] for b in blocks])
    if total_years >= 30:
        new_blocks, count = [], 0
        for b in blocks:
            if count + b[0] <= 30:
                new_blocks.append(b)
                count += b[0]
        return new_blocks
    else:
        final_duration = 30 - total_years
        final_block = (final_duration, *final[1:])
        return blocks + [final_block]

def get_market_params(year, scenarios):
    counter = 0
    for duration, stock_mean, stock_std, bond_mean, bond_std, _ in scenarios:
        if year < counter + duration:
            return stock_mean, stock_std, bond_mean, bond_std
        counter += duration
    return scenarios[-1][1:5]

def compute_irr(annual_changes, withdrawal, initial_asset):
    if not annual_changes:
        return None
    cash_flows = [-initial_asset] + [withdrawal] * len(annual_changes)
    try:
        return npf.irr(cash_flows)
    except:
        return None

def simulate_once(sim_id, initial_asset, withdraw_rate, years, stock_ratio, seed, scenarios):
    rng = np.random.default_rng(seed + sim_id)
    annual_withdrawal = initial_asset * withdraw_rate
    stock_asset = initial_asset * stock_ratio
    bond_asset = initial_asset * (1 - stock_ratio)
    asset_history = []
    annual_changes = []

    for year in range(years):
        stock_mean, stock_std, bond_mean, bond_std = get_market_params(year, scenarios)
        stock_return = rng.normal(stock_mean, stock_std)
        bond_return = rng.normal(bond_mean, bond_std)
        stock_asset *= (1 + stock_return)
        bond_asset *= (1 + bond_return)
        total_asset = stock_asset + bond_asset - annual_withdrawal
        if total_asset <= 0:
            irr_value = compute_irr(annual_changes, annual_withdrawal, initial_asset)
            return {"ending_asset": 0, "bankruptcy_year": year + 1, "return_rate": None, "irr": irr_value}
        if asset_history:
            change = (total_asset - asset_history[-1]) / asset_history[-1]
            annual_changes.append(change)
        asset_history.append(total_asset)
        stock_asset = total_asset * stock_ratio
        bond_asset = total_asset * (1 - stock_ratio)
    final_asset = stock_asset + bond_asset
    return_rate = (final_asset / initial_asset) ** (1 / years) - 1
    return {"ending_asset": final_asset, "bankruptcy_year": None, "return_rate": return_rate, "irr": None}

st.sidebar.title("Simulation Parameters")
withdraw_rate = st.sidebar.slider("Withdrawal Rate (%)", 2.0, 6.0, 4.0, step=0.5) / 100
stock_ratio_percent = st.sidebar.slider("Stock Allocation (%)", 0, 100, 70, step=10)
stock_ratio = stock_ratio_percent / 100  # 實際計算使用小數
n_simulations = st.sidebar.number_input("Number of Simulations", min_value=1000, max_value=5000, value=1000, step=500)
use_random_scenario = st.sidebar.checkbox("Random Market Scenarios", value=False)
run_grid_analysis = st.sidebar.checkbox("Run Grid Heatmap Analysis")

scenarios = generate_random_scenarios(seed=42) if use_random_scenario else SCENARIOS_FIXED


results = [simulate_once(i, 1000, withdraw_rate, 30, stock_ratio, 42, scenarios) for i in range(n_simulations)]
successes = [r for r in results if r["bankruptcy_year"] is None]
failures = [r for r in results if r["bankruptcy_year"] is not None]

st.header("Results of Monte Carol Simulation")
col1, col2 = st.columns(2)
col1.metric("Success Rate", f"{len(successes) / n_simulations:.1%}")
avg_bk = np.mean([r['bankruptcy_year'] for r in failures]) if failures else None
col2.metric("Average Bankruptcy Year", f"{avg_bk:.1f}" if avg_bk else "None")

final_assets = [r["ending_asset"] for r in successes if r["ending_asset"] is not None]
if final_assets:
    st.write("Statistics of Ending Assets for Successful Cases")
    st.dataframe(
        pd.DataFrame({
            "Duration": ["30 years"],
            "Initial Asset": [1000],
            "Median Asset": [int(np.median(final_assets))],
            "Top 25% Median": [int(np.percentile(final_assets, 75))],
            "Bottom 25% Median": [int(np.percentile(final_assets, 25))]
        }).style.hide(axis="index"),  # 關鍵：這裡關閉索引欄
        use_container_width=True
    )


# 顯示 Market Scenarios 表格
st.subheader("Market Scenarios Overview")
scenario_table = pd.DataFrame([
    {
        "Label": label,
        "Duration (yrs)": duration,
        "Stock Mean": f"{stock_mean:.2%}",
        "Stock Std": f"{stock_std:.2%}",
        "Bond Mean": f"{bond_mean:.2%}",
        "Bond Std": f"{bond_std:.2%}"
    }
    for duration, stock_mean, stock_std, bond_mean, bond_std, label in scenarios
])
st.dataframe(scenario_table.style.hide(axis="index"), use_container_width=True)

# 繪製直方圖
success_returns = [r["return_rate"] for r in successes if r["return_rate"] is not None]
failure_irrs = [r["irr"] for r in failures if r["irr"] is not None]
fig, ax = plt.subplots(figsize=(10, 4))
sns.histplot(success_returns, bins=50, kde=True, color="green", label="Success Return Rate", ax=ax)
sns.histplot(failure_irrs, bins=50, kde=True, color="red", label="Bankruptcy IRR", ax=ax)
ax.legend()
ax.set_title("Distribution of Annual Returns")
ax.set_xlabel("Return Rate")
ax.set_ylabel("Frequency")
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
st.pyplot(fig)

if run_grid_analysis:
    st.header("Grid Heatmap Analysis for Market Scenarios")

    def simulate_grid(wr, sr, n_simulations, scenarios):
        res = [simulate_once(i, 1000, wr, 30, sr, 100 + i, scenarios) for i in range(n_simulations)]
        success = [r for r in res if r['bankruptcy_year'] is None]
        fail = [r for r in res if r['bankruptcy_year'] is not None]
        return {
            "Withdrawal Rate": wr,
            "Stock Allocation": sr,
            "Success Rate": len(success) / n_simulations,
            "Top 25% Median": np.percentile([r["ending_asset"] for r in success], 75) if success else None,
            "Bottom 25% Median": np.percentile([r["ending_asset"] for r in success], 25) if success else None,
            "Median Bankruptcy Year": np.median([r["bankruptcy_year"] for r in fail]) if fail else None
        }

    withdraw_rates = np.arange(0.02, 0.06, 0.005)
    stock_ratios = np.arange(0.0, 1.0, 0.1)
    param_grid = [(wr, sr) for wr in withdraw_rates for sr in stock_ratios]
    st.info("\U0001F680 Running Parallel Simulations. Please wait...")
    grid_results = Parallel(n_jobs=-1)(delayed(simulate_grid)(wr, sr, n_simulations, scenarios) for wr, sr in param_grid)

    def plot_heatmap(data, value_col, title, cmap):
        df = pd.DataFrame(data)
        pivot = df.pivot(index="Withdrawal Rate", columns="Stock Allocation", values=value_col)
        fmt = ".1%" if value_col == "Success Rate" else ".1f" if "Year" in title else ".0f"
        if value_col == "Success Rate":
            fmt = ".1%"
        pivot.index = [f"{x:.1%}" for x in pivot.index]
        pivot.columns = [f"{x:.0%}" for x in pivot.columns]
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.heatmap(pivot, annot=True, fmt=fmt, cmap=cmap, ax=ax)
        ax.set_title(title)
        ax.set_xlabel("Stock Allocation")
        ax.set_ylabel("Withdrawal Rate")
        st.pyplot(fig)

    plot_heatmap(grid_results, "Success Rate", "30-Year Success Rate Heatmap", "YlGnBu")
    plot_heatmap(grid_results, "Top 25% Median", "Top 25% Median Ending Asset", "PuBuGn")
    plot_heatmap(grid_results, "Bottom 25% Median", "Bottom 25% Median Ending Asset", "OrRd")
    plot_heatmap(grid_results, "Median Bankruptcy Year", "Median Bankruptcy Year Heatmap", "YlOrBr")

import datetime

# 初始化 Session 計數器
if 'visit_count' not in st.session_state:
    st.session_state.visit_count = 0

st.session_state.visit_count += 1

# 取得當前日期
today = datetime.date.today()
current_year = today.year
current_month = today.month
current_day = today.day

# 假設這是網頁端「統計」的變數（這裡簡單模擬，真正要跨 session 要連接外部資料庫）
total_visits = 12345  # 假設目前總訪問次數
today_visits = st.session_state.visit_count
month_visits = st.session_state.visit_count
year_visits = st.session_state.visit_count

# 顯示在側邊欄底部
with st.sidebar:
    st.markdown("---")
    st.caption(f"**🔎 頁面統計**")
    st.caption(f"總訪問次數：{total_visits:,}")
    st.caption(f"今日訪問：{today_visits:,} 次")
    st.caption(f"本月訪問：{month_visits:,} 次")
    st.caption(f"今年訪問：{year_visits:,} 次")
