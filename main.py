import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ページ設定
st.set_page_config(page_title="わが家の資産管理", layout="wide", page_icon="💰")

# ==========================================
# 設定エリア（スプレッドシートURLのみ）
# ==========================================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1CGZvOLZUzV-SSXs4mlXHnj29fvfq-7nsDCpSV-axuhU/edit?gid=0#gid=0" # ←あなたのURLのままでOK

# ==========================================
# スプレッドシート接続機能
# ==========================================
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 資産データの読み書き ---
def load_data():
    try:
        client = get_gspread_client()
        # 1枚目のシート（家計簿データ）を取得
        sheet = client.open_by_url(SPREADSHEET_URL).get_worksheet(0)
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["日付", "銀行名", "種類", "所有者", "金額", "メモ"])
        df = pd.DataFrame(data)
        df["日付"] = pd.to_datetime(df["日付"]).dt.date
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return pd.DataFrame(columns=["日付", "銀行名", "種類", "所有者", "金額", "メモ"])

def save_data(df):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(SPREADSHEET_URL).get_worksheet(0)
        save_df = df.copy()
        save_df["日付"] = save_df["日付"].astype(str)
        sheet.clear()
        sheet.append_row(save_df.columns.tolist())
        sheet.append_rows(save_df.values.tolist())
    except Exception as e:
        st.error(f"データ保存エラー: {e}")

# --- ユーザー設定（パスワード）の読み書き ---
def load_users():
    """user_configシートからユーザー情報を取得する"""
    try:
        client = get_gspread_client()
        # "user_config" という名前のシートを探す
        try:
            sheet = client.open_by_url(SPREADSHEET_URL).worksheet("user_config")
        except:
            st.error("エラー: スプレッドシートに 'user_config' というシートが見つかりません。作成してください。")
            return {}
            
        records = sheet.get_all_records()
        # 辞書形式 {"夫": "0000", "妻": "1234"} に変換
        user_dict = {row["ユーザー名"]: str(row["パスワード"]) for row in records}
        return user_dict
    except Exception as e:
        st.error(f"ユーザー設定読み込みエラー: {e}")
        return {}

def update_password(username, new_password):
    """パスワードを更新する"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(SPREADSHEET_URL).worksheet("user_config")
        
        # 全データを取得して、該当ユーザーのパスワードを書き換える
        data = sheet.get_all_records()
        
        # スプレッドシートの行番号を探す（ヘッダーが1行目なので、データは2行目から。+2する）
        for i, row in enumerate(data):
            if row["ユーザー名"] == username:
                # B列（2列目）を更新
                sheet.update_cell(i + 2, 2, str(new_password))
                return True
        return False
    except Exception as e:
        st.error(f"パスワード更新エラー: {e}")
        return False

# ==========================================
# ログイン機能
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 家計簿アプリ ログイン</h1>", unsafe_allow_html=True)
    
    # 最新のユーザー情報をロード
    users_db = load_users()
    
    if not users_db:
        st.stop() # ユーザー情報が取れなければ止める

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.selectbox("ユーザーを選択", list(users_db.keys()))
            password = st.text_input("パスワード", type="password")
            submit = st.form_submit_button("ログイン", use_container_width=True)
            
            if submit:
                # パスワード照合
                if username in users_db and str(password) == str(users_db[username]):
                    st.session_state.logged_in = True
                    st.session_state.current_user = username
                    st.rerun()
                else:
                    st.error("パスワードが違います")
        
        # パスワードを忘れた場合の案内
        with st.expander("パスワードを忘れた場合"):
            st.info("""
            **初期化・確認方法：**
            このアプリの管理用スプレッドシート（Google Sheets）を直接開いてください。
            `user_config` というシートを見ると、現在のパスワードが書いてあります。
            必要であれば、そのシートの数字を直接書き換えることでリセットできます。
            """)

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
        accessible_df = pd.DataFrame() # エラー回避

    # --- サイドバー ---
    with st.sidebar:
        st.write(f"👤 **{current_user}** でログイン中")
        
        # ログアウト
        if st.button("ログアウト", type="secondary"):
            logout()
        
        st.divider()
        st.title("メニュー")
        page = st.radio(
            "移動先", 
            ["📊 ダッシュボード", "📝 データ管理", "🔑 パスワード変更"], # メニュー追加
            label_visibility="collapsed"
        )
        
        if page != "🔑 パスワード変更":
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
            to_keep = edited[~edited["削除"]].drop(columns=["削除"])
            hidden_data = full_df[~full_df["所有者"].isin(allowed_owners)]
            final_df = pd.concat([hidden_data, to_keep], ignore_index=True)
            save_data(final_df)
            st.success("更新しました！")
            st.rerun()

    # ==========================================
    # ページ3: 🔑 パスワード変更
    # ==========================================
    elif page == "🔑 パスワード変更":
        st.title("🔑 パスワード変更")
        
        st.info(f"現在ログイン中の **{current_user}** さんのパスワードを変更します。")
        
        with st.form("pwd_change_form"):
            new_pwd = st.text_input("新しいパスワード", type="password")
            new_pwd_confirm = st.text_input("新しいパスワード（確認用）", type="password")
            submit_pwd = st.form_submit_button("変更する")
            
            if submit_pwd:
                if new_pwd != new_pwd_confirm:
                    st.error("パスワードが一致しません。")
                elif new_pwd == "":
                    st.error("パスワードを入力してください。")
                else:
                    # スプレッドシートを更新
                    if update_password(current_user, new_pwd):
                        st.success("パスワードを変更しました！次回から新しいパスワードでログインしてください。")
                    else:
                        st.error("変更に失敗しました。管理者へ連絡してください。")