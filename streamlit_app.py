# 精簡熱力圖 + 平行運算 + 初始金額與統計修正
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
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

font_path = "/usr/share/fonts/truetype/arphic/ukai.ttc"  # Linux 常見中文字型路徑
fm.fontManager.addfont(font_path)
plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()

st.set_page_config(layout="wide")

SCENARIOS_FIXED = [
    (3, -0.02, 0.25, 0.01, 0.08, "2008–2010 金融危機"),
    (3, 0.10, 0.18, 0.03, 0.05, "2011–2013 復續牛市"),
    (2, 0.01, 0.20, 0.02, 0.06, "2014–2015 歐債危機"),
    (5, 0.09, 0.16, 0.04, 0.05, "2016–2020 牛市繼行"),
    (2, -0.05, 0.30, 0.00, 0.10, "2021–2022 COVID-19"),
    (3, 0.06, 0.18, 0.01, 0.08, "2023–2025 疫後通股"),
    (30, 0.07, 0.14, 0.03, 0.05, "2026+ 平穩成長")
]

@st.cache_data
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

# 側邊欄參數
st.sidebar.title("模擬參數設定")
withdraw_rate = st.sidebar.slider("提領率 (%)", 2.0, 6.0, 4.0, step=0.5) / 100
stock_ratio = st.sidebar.slider("股票比例", 0.0, 1.0, 0.7, step=0.1)
n_simulations = st.sidebar.number_input("模擬次數", min_value=1000, max_value=5000, value=1000, step=500)
use_random_scenario = st.sidebar.checkbox("使用隨機情境順序", value=False)
run_grid_analysis = st.sidebar.checkbox("執行網格熱力圖分析")

# 簡化市場情境顯示
scenarios = generate_random_scenarios(seed=42) if use_random_scenario else SCENARIOS_FIXED
with st.sidebar.expander("📘 使用的市場情境（簡化顯示）"):
    for dur, stock_mean, stock_std, _, _, label in scenarios:
        st.markdown(f"• {label}（{dur}年）：報酬率 {stock_mean:.0%}，波動 {stock_std:.0%}")

# 單一模擬執行
results = [simulate_once(i, 1000, withdraw_rate, 30, stock_ratio, 42, scenarios) for i in range(n_simulations)]
successes = [r for r in results if r["bankruptcy_year"] is None]
failures = [r for r in results if r["bankruptcy_year"] is not None]

st.header("模擬結果（單一組合）")
col1, col2 = st.columns(2)
col1.metric("成功率", f"{len(successes) / n_simulations:.1%}")
avg_bk = np.mean([r['bankruptcy_year'] for r in failures]) if failures else None
col2.metric("平均破產年", f"{avg_bk:.1f}" if avg_bk else "無")

final_assets = [r["ending_asset"] for r in successes if r["ending_asset"] is not None]
if final_assets:
    st.write("成功組資產統計")
    st.write(pd.DataFrame({
        "期間": ["30年"],
        "初始金額": [1000],
        "資產中位數": [int(np.median(final_assets))],
        "前25%資產": [int(np.median(final_assets[int(len(final_assets)*0.75):]))],
        "後25%資產": [int(np.median(final_assets[:int(len(final_assets)*0.25)]))]
    }))

# 年報酬率與IRR直方圖
success_returns = [r["return_rate"] for r in successes if r["return_rate"] is not None]
failure_irrs = [r["irr"] for r in failures if r["irr"] is not None]
fig, ax = plt.subplots(figsize=(10, 4))
sns.histplot(success_returns, bins=50, kde=True, color="green", label="成功報酬率", ax=ax)
sns.histplot(failure_irrs, bins=50, kde=True, color="red", label="破產 IRR", ax=ax)
ax.legend()
ax.set_title("年報酬率分佈")
ax.set_xlabel("報酬率")
ax.set_ylabel("次數")
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
st.pyplot(fig)

# 熱力圖分析（平行運算）
if run_grid_analysis:
    st.header("多組提領率與股票比例組合的熱力圖分析")

    def simulate_grid(wr, sr, n_simulations, scenarios):
        res = [simulate_once(i, 1000, wr, 30, sr, 100 + i, scenarios) for i in range(n_simulations)]
        success = [r for r in res if r['bankruptcy_year'] is None]
        fail = [r for r in res if r['bankruptcy_year'] is not None]
        return {
            "提領率": wr,
            "股票比例": sr,
            "成功率": len(success) / n_simulations,
            "前25%中位數": np.median(sorted([r["ending_asset"] for r in success])[int(len(success)*0.75):]) if success else None,
            "後25%中位數": np.median(sorted([r["ending_asset"] for r in success])[:int(len(success)*0.25)]) if success else None,
            "破產年中位數": np.median([r["bankruptcy_year"] for r in fail]) if fail else None
        }

    withdraw_rates = np.arange(0.03, 0.071, 0.01)
    stock_ratios = np.arange(0.0, 1.01, 0.2)
    param_grid = [(wr, sr) for wr in withdraw_rates for sr in stock_ratios]
    st.info("🚀 使用平行運算中，請耐心等候結果...")
    grid_results = Parallel(n_jobs=-1)(delayed(simulate_grid)(wr, sr, n_simulations, scenarios) for wr, sr in param_grid)

    def plot_heatmap(data, value_col, title, cmap):
        df = pd.DataFrame(data)
        pivot = df.pivot(index="提領率", columns="股票比例", values=value_col)
        pivot.index = [f"{x:.1%}" for x in pivot.index]
        pivot.columns = [f"{x:.0%}" for x in pivot.columns]
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.heatmap(pivot, annot=True, fmt=".1f" if '年' in title else ".0f", cmap=cmap, ax=ax)
        ax.set_title(title)
        ax.set_xlabel("股票比例")
        ax.set_ylabel("提領率")
        st.pyplot(fig)

    plot_heatmap(grid_results, "成功率", "30年成功率熱力圖", "YlGnBu")
    plot_heatmap(grid_results, "前25%中位數", "前25%成功組資產中位數", "PuBuGn")
    plot_heatmap(grid_results, "後25%中位數", "後25%成功組資產中位數", "OrRd")
    plot_heatmap(grid_results, "破產年中位數", "破產年中位數熱力圖", "YlOrBr")
