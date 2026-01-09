import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ページ設定
st.set_page_config(page_title="わが家の資産管理", layout="wide", page_icon="💰")

# ==========================================
# 設定エリア（ここだけ書き換えてください）
# ==========================================
# あなたのスプレッドシートのURLをここに貼ってください
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1CGZvOLZUzV-SSXs4mlXHnj29fvfq-7nsDCpSV-axuhU/edit?gid=0#gid=0"

# ユーザーパスワード設定
USERS = {
    "夫": "0000",
    "妻": "0000",
}

# ==========================================
# スプレッドシート接続機能
# ==========================================
def get_gspread_client():
    # secrets.toml から鍵情報を読み込む
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def load_data():
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["日付", "銀行名", "種類", "所有者", "金額", "メモ"])
        df = pd.DataFrame(data)
        # 日付カラムを日付型に変換
        df["日付"] = pd.to_datetime(df["日付"]).dt.date
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return pd.DataFrame(columns=["日付", "銀行名", "種類", "所有者", "金額", "メモ"])

def save_data(df):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(SPREADSHEET_URL).sheet1
        
        # DataFrameの日付を文字列に変換（JSONシリアライズ対策）
        save_df = df.copy()
        save_df["日付"] = save_df["日付"].astype(str)
        
        # スプレッドシートをクリアして書き込み
        sheet.clear()
        # ヘッダー書き込み
        sheet.append_row(save_df.columns.tolist())
        # データ書き込み
        sheet.append_rows(save_df.values.tolist())
    except Exception as e:
        st.error(f"データ保存エラー: {e}")

# ==========================================
# ログイン機能のロジック
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 家計簿アプリ ログイン</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.selectbox("ユーザーを選択", ["夫", "妻"])
            password = st.text_input("パスワード", type="password")
            submit = st.form_submit_button("ログイン", use_container_width=True)
            
            if submit:
                if password == USERS[username]:
                    st.session_state.logged_in = True
                    st.session_state.current_user = username
                    st.rerun()
                else:
                    st.error("パスワードが違います")

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.rerun()

# ==========================================
# アプリのメイン処理
# ==========================================
if not st.session_state.logged_in:
    login()
else:
    # データロード
    full_df = load_data()
    
    current_user = st.session_state.current_user
    
    # 権限設定
    if current_user == "夫":
        accessible_df = full_df[full_df["所有者"].isin(["夫", "夫婦"])]
        allowed_owners = ["夫", "夫婦"]
    elif current_user == "妻":
        accessible_df = full_df[full_df["所有者"].isin(["妻", "夫婦"])]
        allowed_owners = ["妻", "夫婦"]
    else:
        accessible_df = pd.DataFrame()

    # --- サイドバー ---
    with st.sidebar:
        st.write(f"👤 **{current_user}** でログイン中")
        if st.button("ログアウト", type="secondary"):
            logout()
        
        st.divider()
        st.title("メニュー")
        page = st.radio(
            "移動先", 
            ["📊 ダッシュボード", "📝 データ管理"],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.write("### ⚙️ 表示設定")
        filter_options = ["全員（自分＋夫婦）"] + allowed_owners
        selected_filter = st.selectbox("表示範囲", filter_options)
        
        # フィルタリング
        if selected_filter == "全員（自分＋夫婦）":
            view_df = accessible_df
        else:
            view_df = accessible_df[accessible_df["所有者"] == selected_filter]

    # ==========================================
    # ページ1: 📊 ダッシュボード
    # ==========================================
    if page == "📊 ダッシュボード":
        st.title(f"📊 資産ダッシュボード")
        
        if view_df.empty:
            st.info("データがありません。")
        else:
            latest_status_df = view_df.sort_values("日付").drop_duplicates(subset=["銀行名", "所有者"], keep="last")
            total_assets = latest_status_df["金額"].sum()
            daily_sum = view_df.groupby("日付")["金額"].sum().reset_index()

            st.markdown(f"""
                <div style="background-color:#f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <h3 style="margin:0; color:#555;">資産合計 ({selected_filter})</h3>
                    <h1 style="margin:0; color:#000;">{total_assets:,.0f} 円</h1>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 1.5])
            with col1:
                st.subheader("内訳グラフ")
                if total_assets > 0:
                    fig = px.pie(latest_status_df, values='金額', names='銀行名', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(latest_status_df[["銀行名", "種類", "金額", "所有者"]].sort_values("金額", ascending=False), use_container_width=True, hide_index=True)

            with col2:
                st.subheader("推移チャート")
                st.area_chart(daily_sum.set_index("日付"), color="#636EFA")

    # ==========================================
    # ページ2: 📝 データ管理
    # ==========================================
    elif page == "📝 データ管理":
        st.title("📝 データ管理")

        with st.expander("➕ 新規登録", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                date_in = st.date_input("日付", datetime.date.today())
                exist_banks = sorted(list(accessible_df["銀行名"].unique())) if not accessible_df.empty else []
                bank_in = st.text_input("銀行名", placeholder="例: A銀行")
                if exist_banks: st.caption(f"登録済: {', '.join(exist_banks[:3])}...")
                amount_in = st.number_input("金額", min_value=0, step=1000)
            with col2:
                kind_in = st.selectbox("種類", ["普通預金", "定期預金", "投資信託", "株式", "現金", "ポイント", "その他"])
                owner_in = st.radio("所有者", allowed_owners, horizontal=True)
                memo_in = st.text_input("メモ")
            
            if st.button("登録する", type="primary"):
                if not bank_in:
                    st.error("銀行名を入れてください")
                else:
                    new_row = pd.DataFrame([{"日付": date_in, "銀行名": bank_in, "種類": kind_in, "所有者": owner_in, "金額": amount_in, "メモ": memo_in}])
                    if full_df.empty: full_df = new_row
                    else: full_df = pd.concat([full_df, new_row], ignore_index=True)
                    save_data(full_df)
                    st.success("保存しました！")
                    st.rerun()

        st.divider()
        st.subheader("📋 データの修正・削除")
        st.info("編集後、「変更を保存」ボタンを押してください。")
        
        # 編集用データ作成
        edit_df = view_df.sort_values("日付", ascending=False).copy()
        edit_df.insert(0, "削除", False)
        
        edited = st.data_editor(
            edit_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "削除": st.column_config.CheckboxColumn(default=False),
                "日付": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "所有者": st.column_config.SelectboxColumn(options=allowed_owners),
            }
        )
        
        if st.button("変更を保存する", type="primary"):
            # 1. 削除フラグのない行だけ残す
            to_keep = edited[~edited["削除"]].drop(columns=["削除"])
            
            # 2. 編集対象外のデータ（相手のデータ）を取得
            hidden_data = full_df[~full_df["所有者"].isin(allowed_owners)]
            
            # 3. 合体して保存
            final_df = pd.concat([hidden_data, to_keep], ignore_index=True)
            save_data(final_df)
            st.success("更新しました！")
            st.rerun()