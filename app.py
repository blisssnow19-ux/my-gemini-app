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
    "1. 標準：密室（サービス封印）": "【最重要：AIの「サービス精神」の完全放棄】ユーザーを喜ばせようとする「過剰な親切心」を禁じます。時間は数分単位で進め、膠着状態を維持せよ。",
    "2. 官能：朝チュン（残り香重視）": "事後の残り香、熱っぽい視線、気まずい空気を重視。直接的な描写を避け、行間で語れ。",
    "3. 対立：中也 vs 太宰（ヒリヒリ）": "二人の相容れない緊張感を最大化せよ。互いに一歩も引かない心理戦を展開すること。",
    "4. 膠着：沈黙と視線（超スロー）": "言葉を極限まで減らし、視線の動き、微かな呼吸音、指先の震えだけで描写せよ。",
    "5. 執着：太宰の独白（ねっとり）": "太宰の独占欲を滲ませよ。スノウの逃げ場のなさを強調すること。",
    "6. 執着：中也の焦燥（荒っぽく）": "中也の隠しきれない独占欲と、それを否定しようとする不器用な優しさを描写せよ。",
    "7. 外部：扉の向こう側（監視）": "密室に閉じ込められた三人を、外部（モニター越し等）から冷徹に観察する視点で描写せよ。",
    "8. IF：記憶喪失（不穏）": "誰かが記憶を失っている。それを利用しようとする者と、絶望する者のギャップを強調。",
    "9. 深夜：眠れない夜（静寂）": "深夜3時の静まり返った密室。意識だけが冴え渡り、互いの熱だけを感じる時間。",
    "10. 終焉：脱出への誘い（絶望）": "扉が開く瞬間。外に出ることへの恐怖と、ここに留まりたいという歪んだ願望。"
}

# --- サイドバー ---
with st.sidebar:
    st.title("🕯️ 密室管理パネル")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # 🌟 部屋名（これがセーブデータIDになります！）
    st.divider()
    room_id = st.text_input("部屋名（セーブデータの名前）", value="room_01", help="PCとスマホで同じ名前にすれば同期されます")
    
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
