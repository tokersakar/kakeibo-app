import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ページ設定
st.set_page_config(page_title="わが家の資産管理", layout="wide", page_icon="💰")

# ==========================================
# 設定エリア
# ==========================================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/xxxxxxxxxxxxxxxx/edit" # ←あなたのURLのままでOK

# ==========================================
# スプレッドシート接続機能
# ==========================================
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- データの読み書き ---
def load_data():
    try:
        client = get_gspread_client()
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
    try:
        client = get_gspread_client()
        try:
            sheet = client.open_by_url(SPREADSHEET_URL).worksheet("user_config")
        except:
            st.error("エラー: 'user_config' シートが見つかりません。")
            return {}
        records = sheet.get_all_records()
        # 数値で取れてしまっても文字型(str)に強制変換して読み込む
        user_dict = {row["ユーザー名"]: str(row["パスワード"]) for row in records}
        return user_dict
    except Exception as e:
        st.error(f"ユーザー設定読み込みエラー: {e}")
        return {}

def update_password(username, new_password):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(SPREADSHEET_URL).worksheet("user_config")
        data = sheet.get_all_records()
        for i, row in enumerate(data):
            if row["ユーザー名"] == username:
                # 数字の0000などが消えないよう、あえて ' (アポストロフィ) を付けて保存する処理を入れるとより安全ですが、
                # アプリからの書き込みなら文字列として送られるので通常はそのままで大丈夫です。
                # 念のため文字列化して保存します。
                sheet.update_cell(i + 2, 2, str(new_password))
                return True
        return False
    except Exception as e:
        st.error(f"パスワード更新エラー: {e}")
        return False

# ==========================================
# ログイン画面 ＆ リセット機能
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 家計簿アプリ ログイン</h1>", unsafe_allow_html=True)
    
    users_db = load_users()
    if not users_db: st.stop()

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # --- 通常ログイン ---
        with st.container(border=True):
            st.subheader("ログイン")
            with st.form("login_form"):
                username = st.selectbox("ユーザー", list(users_db.keys()))
                password = st.text_input("パスワード", type="password")
                submit = st.form_submit_button("ログイン", use_container_width=True)
                
                if submit:
                    # 入力されたパスワードと、DBのパスワード(str)を比較
                    if username in users_db and str(password) == str(users_db[username]):
                        st.session_state.logged_in = True
                        st.session_state.current_user = username
                        st.rerun()
                    else:
                        st.error("パスワードが違います")
        
        st.write("") # 余白

        # --- パスワードリセット機能（マスターキー使用） ---
        with st.expander("🔑 パスワードを忘れた・リセットする"):
            st.warning("設定した「マスターキー」を使って、パスワードを強制変更します。")
            with st.form("reset_form"):
                target_user = st.selectbox("リセットするユーザー", list(users_db.keys()), key="reset_user")
                master_key_input = st.text_input("マスターキー（合言葉）", type="password", help="secrets.tomlで設定したキー")
                new_pass_reset = st.text_input("新しいパスワード", type="password", key="new_pass_reset")
                
                reset_btn = st.form_submit_button("リセット実行", type="primary")
                
                if reset_btn:
                    # マスターキーの照合
                    correct_master_key = st.secrets.get("master_key", "")
                    
                    if correct_master_key == "":
                        st.error("エラー: マスターキーが設定されていません。secrets.tomlを確認してください。")
                    elif master_key_input == correct_master_key:
                        if new_pass_reset:
                            if update_password(target_user, new_pass_reset):
                                st.success(f"成功: {target_user} のパスワードを変更しました！上のフォームからログインしてください。")
                            else:
                                st.error("更新に失敗しました。")
                        else:
                            st.error("新しいパスワードを入力してください。")
                    else:
                        st.error("マスターキーが違います。")

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.rerun()

# ==========================================
# アプリ本編
# ==========================================
if not st.session_state.logged_in:
    login()
else:
    # データロード
    full_df = load_data()
    current_user = st.session_state.current_user
    
    if current_user == "夫":
        accessible_df = full_df[full_df["所有者"].isin(["夫", "夫婦"])]
        allowed_owners = ["夫", "夫婦"]
    elif current_user == "妻":
        accessible_df = full_df[full_df["所有者"].isin(["妻", "夫婦"])]
        allowed_owners = ["妻", "夫婦"]
    else:
        accessible_df = pd.DataFrame()

    with st.sidebar:
        st.write(f"👤 **{current_user}** でログイン中")
        if st.button("ログアウト", type="secondary"):
            logout()
        st.divider()
        st.title("メニュー")
        page = st.radio("移動先", ["📊 ダッシュボード", "📝 データ管理", "🔑 パスワード変更"], label_visibility="collapsed")
        
        if page != "🔑 パスワード変更":
            st.divider()
            st.write("### ⚙️ 表示設定")
            filter_options = ["全員（自分＋夫婦）"] + allowed_owners
            selected_filter = st.selectbox("表示範囲", filter_options)
            if selected_filter == "全員（自分＋夫婦）":
                view_df = accessible_df
            else:
                view_df = accessible_df[accessible_df["所有者"] == selected_filter]

    # --- 各ページの内容 ---
    if page == "📊 ダッシュボード":
        st.title(f"📊 資産ダッシュボード")
        if view_df.empty:
            st.info("データがありません。")
        else:
            latest = view_df.sort_values("日付").drop_duplicates(subset=["銀行名", "所有者"], keep="last")
            total = latest["金額"].sum()
            daily = view_df.groupby("日付")["金額"].sum().reset_index()
            st.markdown(f"<div style='background-color:#f0f2f6; padding:20px; border-radius:10px;'><h3>資産合計</h3><h1>{total:,.0f} 円</h1></div><br>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1.5])
            with c1:
                if total > 0:
                    fig = px.pie(latest, values='金額', names='銀行名', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(latest[["銀行名", "種類", "金額"]].sort_values("金額", ascending=False), use_container_width=True, hide_index=True)
            with c2:
                st.area_chart(daily.set_index("日付"), color="#636EFA")

    elif page == "📝 データ管理":
        st.title("📝 データ管理")
        with st.expander("➕ 新規登録", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                d_in = st.date_input("日付", datetime.date.today())
                exist = sorted(list(accessible_df["銀行名"].unique())) if not accessible_df.empty else []
                b_in = st.text_input("銀行名", placeholder="例: A銀行")
                if exist: st.caption(f"登録済: {', '.join(exist[:3])}...")
                a_in = st.number_input("金額", min_value=0, step=1000)
            with c2:
                k_in = st.selectbox("種類", ["普通預金", "定期預金", "投資信託", "株式", "現金", "ポイント", "その他"])
                o_in = st.radio("所有者", allowed_owners, horizontal=True)
                m_in = st.text_input("メモ")
            if st.button("登録する", type="primary"):
                if not b_in: st.error("銀行名を入れてください")
                else:
                    new_r = pd.DataFrame([{"日付": d_in, "銀行名": b_in, "種類": k_in, "所有者": o_in, "金額": a_in, "メモ": m_in}])
                    if full_df.empty: full_df = new_r
                    else: full_df = pd.concat([full_df, new_r], ignore_index=True)
                    save_data(full_df)
                    st.success("保存しました！")
                    st.rerun()
        
        st.divider()
        st.subheader("📋 データの修正・削除")
        edit_df = view_df.sort_values("日付", ascending=False).copy()
        edit_df.insert(0, "削除", False)
        edited = st.data_editor(edit_df, hide_index=True, use_container_width=True, column_config={"削除": st.column_config.CheckboxColumn(default=False), "日付": st.column_config.DateColumn(format="YYYY-MM-DD"), "所有者": st.column_config.SelectboxColumn(options=allowed_owners)})
        if st.button("変更を保存する", type="primary"):
            to_keep = edited[~edited["削除"]].drop(columns=["削除"])
            hidden = full_df[~full_df["所有者"].isin(allowed_owners)]
            save_data(pd.concat([hidden, to_keep], ignore_index=True))
            st.success("更新しました！")
            st.rerun()

    elif page == "🔑 パスワード変更":
        st.title("🔑 パスワード変更")
        st.info(f"**{current_user}** さんのパスワードを変更します。")
        with st.form("pwd_chg"):
            p1 = st.text_input("新しいパスワード", type="password")
            p2 = st.text_input("確認用", type="password")
            if st.form_submit_button("変更する"):
                if p1!=p2: st.error("不一致")
                elif not p1: st.error("空欄不可")
                else:
                    if update_password(current_user, p1): st.success("変更しました！")
                    else: st.error("失敗")