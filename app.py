import streamlit as st
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json
import datetime

# --- 基本設定 ---
st.set_page_config(page_title="執着密室：シームレス司令室", layout="wide")

# Firebaseの初期化（一度だけ実行）
if not firebase_admin._apps:
    key_dict = json.loads(st.secrets["firebase_key"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 2026年最新単価
PRICING = {
    "gemini-3.1-pro-preview": {"in": 2.00, "out": 12.00},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.00}
}
JPY_RATE = 150.0

# --- 📚 プロンプト・ライブラリ（10種類選べる設定） ---
PROMPT_TEMPLATES = {
    "01": "ここに1つ目のシステム指示（太宰用など）を書く...",
    "02": "ここに2つ目のシステム指示（中也用など）を書く...",
    "03": "ここに3つ目のシステム指示（膠着状態用など）を書く..."
    "04": "ここに3つ目のシステム指示（膠着状態用など）を書く..."
    "05": "ここに1つ目のシステム指示（太宰用など）を書く...",
    "06": "ここに2つ目のシステム指示（中也用など）を書く...",
    "07": "ここに3つ目のシステム指示（膠着状態用など）を書く..."
    "08": "ここに1つ目のシステム指示（太宰用など）を書く...",
    "09": "ここに2つ目のシステム指示（中也用など）を書く...",
    "10": "ここに3つ目のシステム指示（膠着状態用など）を書く..."
}

# --- サイドバー ---
with st.sidebar:
    st.title("🕯️ 密室管理パネル")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # 🌟 部屋名（これがセーブデータIDになります！）
st.divider()
    st.subheader("📂 セーブデータの選択")
    
    # Firebaseから「今ある部屋の名前」を全部取得
    try:
        rooms_ref = db.collection("rooms")
        existing_rooms = [doc.id for doc in rooms_ref.stream()]
    except:
        existing_rooms = []
        
    if not existing_rooms:
        existing_rooms = ["room_01"] # 最初は仮の名前を入れておく

    # 「既存の部屋」か「新しい部屋」かを選ぶ
    room_mode = st.radio("操作モード", ["既存の部屋に入る", "新しい部屋を作る（新章）"], horizontal=True)

    if room_mode == "既存の部屋に入る":
        # プルダウンで選ぶだけ！記憶不要！
        room_id = st.selectbox("入室する部屋を選んでください", existing_rooms)
    else:
        # 新しい部屋を作る時は名前を決める
        room_id = st.text_input("新しい部屋の名前（英数字おすすめ）", value=f"room_{len(existing_rooms)+1:02d}")
    
    st.divider()
    st.subheader("📚 プロンプト選択")
    prompt_key = st.selectbox("設定を選択", list(PROMPT_TEMPLATES.keys()))
    current_system = st.text_area("システム指示の編集", value=PROMPT_TEMPLATES[prompt_key], height=200)

    st.divider()
    model_choice = st.selectbox("使用モデル", list(PRICING.keys()))
    max_output = st.slider("応答の最大長さ", 100, 8000, 1000)
    
    if st.button("🔄 データをクラウドから再読み込み"):
        st.rerun()

# --- データの読み込み ---
doc_ref = db.collection("rooms").document(room_id)
doc = doc_ref.get()

if doc.exists:
    st.session_state.messages = doc.to_dict().get("messages", [])
    st.session_state.total_cost_jpy = doc.to_dict().get("total_cost", 0.0)
else:
    st.session_state.messages = []
    st.session_state.total_cost_jpy = 0.0

# --- メイン画面 ---
st.info(f"現在の部屋: {room_id} | モード: {prompt_key}")
st.metric("累計コスト (概算)", f"¥{st.session_state.total_cost_jpy:.2f}")

# 履歴表示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 入力
if prompt := st.chat_input("密室に言葉を投げ入れる..."):
    if not api_key:
        st.error("API Keyを入力してください")
    else:
        # ユーザーの発言を保存
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_choice, system_instruction=current_system)
        
        history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
        
        with st.spinner("思考中..."):
            response = model.generate_content(history, generation_config={"max_output_tokens": max_output})
        
        # AIの回答を保存
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
        # コスト計算
        usage = response.usage_metadata
        cost = ((usage.prompt_token_count / 1e6) * PRICING[model_choice]["in"] + 
                (usage.candidates_token_count / 1e6) * PRICING[model_choice]["out"]) * JPY_RATE
        st.session_state.total_cost_jpy += cost

        # 🌟 Firebaseへ自動保存（1億トークンへの備え）
        doc_ref.set({
            "messages": st.session_state.messages,
            "total_cost": st.session_state.total_cost_jpy,
            "last_update": datetime.datetime.now()
        })
        st.rerun()

# --- 章立て機能 ---
if st.button("📸 新章を開始（履歴を要約）"):
    with st.spinner("要約中..."):
        summary_model = genai.GenerativeModel(model_name="gemini-3.1-pro-preview")
        summary_prompt = f"これまでの会話を300文字程度で要約してください。\n\n履歴: {str(st.session_state.messages)}"
        summary_res = summary_model.generate_content(summary_prompt)
        st.success("要約完了。これをコピーして次のSystem Instructionに活用してください。")
        st.code(summary_res.text)
        if st.button("クラウド上の履歴を完全削除"):
            doc_ref.delete()
            st.rerun()
