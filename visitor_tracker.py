# visitor_tracker.py
import sqlite3
import datetime
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

DB_FILE = "visitors.db"  # 資料庫檔案名稱

def init_db():
    """建立資料表"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

def record_visit(user_id):
    """記錄使用者訪問"""
    today = datetime.date.today()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 檢查是否已經有相同user_id
    c.execute('SELECT * FROM visitors WHERE date = ? AND user_id = ?', (today.isoformat(), user_id))
    if not c.fetchone():
        c.execute('INSERT INTO visitors (date, user_id) VALUES (?, ?)', (today.isoformat(), user_id))
        conn.commit()
    conn.close()

def get_statistics():
    """取得統計資料"""
    today = datetime.date.today()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('SELECT COUNT(DISTINCT user_id) FROM visitors WHERE date = ?', (today.isoformat(),))
    today_count = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT user_id) FROM visitors WHERE strftime("%Y-%m", date) = ?', (today.strftime("%Y-%m"),))
    month_count = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT user_id) FROM visitors WHERE strftime("%Y", date) = ?', (today.strftime("%Y"),))
    year_count = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT user_id) FROM visitors')
    total_count = c.fetchone()[0]

    conn.close()
    return today_count, month_count, year_count, total_count

def plot_recent_visits():
    """繪製最近7日訪問圖"""
    today = datetime.date.today()
    seven_days_ago = today - datetime.timedelta(days=6)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT date, COUNT(DISTINCT user_id) as users
        FROM visitors
        WHERE date >= ?
        GROUP BY date
        ORDER BY date
    ''', (seven_days_ago.isoformat(),))
    rows = c.fetchall()
    conn.close()

    if rows:
        df = pd.DataFrame(rows, columns=["date", "users"])
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(df["date"], df["users"], marker="o")
        ax.set_xlabel("日期")
        ax.set_ylabel("不同使用者數")
        ax.set_title("最近7日不同使用者訪問量")
        ax.grid(True)
        st.pyplot(fig)
    else:
        st.info("最近7天尚無訪問紀錄。")

def track():
    """主控制函數：追蹤並顯示結果"""
    # 初始化資料庫
    init_db()

    # 取得 user_id（用 query string 模擬）
    query_params = st.query_params
    user_id = query_params.get("user", ["unknown"])[0]
    # 記錄訪問
    record_visit(user_id)

    # 顯示統計在側邊欄
    today_count, month_count, year_count, total_count = get_statistics()
    with st.sidebar:
        st.markdown("---")
        st.caption(f"**🔎 不同使用者統計**")
        st.caption(f"今日訪問：{today_count:,} 人")
        st.caption(f"本月訪問：{month_count:,} 人")
        st.caption(f"今年訪問：{year_count:,} 人")
        st.caption(f"總訪問：{total_count:,} 人")

    # 畫最近7日流量圖
    st.subheader("最近7日不同使用者訪問量")
    plot_recent_visits()
