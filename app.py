import streamlit as st
import google.generativeai as genai
import json
import datetime

# --- 基本設定 ---
st.set_page_config(page_title="執着密室：出張司令室", layout="wide")

# 2026年最新単価
PRICING = {
    "gemini-3.1-pro-preview": {"in": 2.00, "out": 12.00},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.00}
}
JPY_RATE = 150.0

# --- プロンプト・ライブラリ（10個まで増やせます） ---
PROMPT_TEMPLATES = {
    "密室：通常（サービス封印）": """# 【最重要：AIの「サービス精神」の完全放棄】
ユーザーを喜ばせようとする「過剰な親切心」を禁じます。時間は数分単位で進め、膠着状態を維持せよ。""",
    "密室：朝チュン（官能性重視）": """事後の残り香、熱っぽい視線、気まずい空気を重視。直接的な描写を避け、行間で語れ。""",
    "密室：対立（中也vs太宰）": """二人の相容れない緊張感を最大化せよ。""",
    "密室：膠着（沈黙と視線）": """言葉を極限まで減らし、視線の動き、微かな呼吸音だけで描写せよ。""",
    # あと6個、ここに追加していけます
}

# セッション状態の初期化
if "messages" not in st.session_state: st.session_state.messages = []
if "total_cost_jpy" not in st.session_state: st.session_state.total_cost_jpy = 0.0

# --- サイドバー：設定 ---
with st.sidebar:
    st.title("🕯️ 密室管理パネル")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.subheader("📚 プロンプト選択")
    # AI Studio風のセレクトボックス
    prompt_key = st.selectbox("設定を選択", list(PROMPT_TEMPLATES.keys()))
    current_system = st.text_area("システム指示の編集", value=PROMPT_TEMPLATES[prompt_key], height=200)

    st.divider()
    model_choice = st.selectbox("使用モデル", list(PRICING.keys()))
    max_output = st.slider("応答の最大長さ", 100, 8000, 1000)
    
    st.divider()
    st.metric("累計コスト", f"¥{st.session_state.total_cost_jpy:.2f}")

# --- クラウド保存のヒント（簡易版） ---
# 本来はGoogle Drive APIを使いますが、まずは「手動アップロード不要」な仕組みとして
# Streamlitの「Secrets」機能を使ってGoogle Driveと連携する準備ができます。
# 今回はまず、プロンプト選択機能を優先しました。

# --- メイン画面 ---
st.info(f"現在のモード: {prompt_key}")

# 履歴表示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 入力
if prompt := st.chat_input("密室に言葉を投げ入れる..."):
    if not api_key:
        st.error("API Keyを入力してください")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_choice, system_instruction=current_system)
        
        history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
        
        with st.spinner("思考中..."):
            response = model.generate_content(history, generation_config={"max_output_tokens": max_output})
        
        with st.chat_message("assistant"):
            st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
        # コスト計算
        usage = response.usage_metadata
        cost = ((usage.prompt_token_count / 1e6) * PRICING[model_choice]["in"] + 
                (usage.candidates_token_count / 1e6) * PRICING[model_choice]["out"]) * JPY_RATE
        st.session_state.total_cost_jpy += cost

# 章立て要約機能の強化案
if st.button("📸 新章を開始（履歴を要約）"):
    with st.spinner("これまでの物語を要約中..."):
        summary_model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
        summary_prompt = f"これまでの会話を、次の章から再開するために必要な情報を落とさず、300文字程度で要約してください。\n\n履歴: {str(st.session_state.messages)}"
        summary_res = summary_model.generate_content(summary_prompt)
        
        st.success("要約が完了しました。これをコピーしてSystem Instructionに貼り付け、チャットをクリアして再開してください。")
        st.code(summary_res.text)
        if st.button("チャット履歴をクリア"):
            st.session_state.messages = []
            st.rerun()
