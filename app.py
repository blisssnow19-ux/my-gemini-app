import streamlit as st
import google.generativeai as genai
import json
import datetime

# --- 基本設定 ---
st.set_page_config(page_title="執着密室管理室", layout="wide", initial_sidebar_state="expanded")

# 2026年4月現在の最新単価 (1Mトークンあたり/USD)
PRICING = {
    "gemini-3.1-pro-preview": {"in": 2.00, "out": 12.00},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.00},
    "gemini-3-flash-preview": {"in": 0.50, "out": 3.00}
}
JPY_RATE = 150.0  # 1ドル150円換算

# セッション状態の初期化
if "messages" not in st.session_state: st.session_state.messages = []
if "total_cost_jpy" not in st.session_state: st.session_state.total_cost_jpy = 0.0

# --- サイドバー設定 ---
with st.sidebar:
    st.title("🕯️ 密室管理パネル")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studioで発行したキーを入力")
    
    model_choice = st.selectbox("使用モデル", list(PRICING.keys()), index=0)
    
    st.divider()
    st.subheader("🖋️ 執筆・演出設定")
    max_output = st.slider("応答の最大長さ (Output Length)", 100, 8000, 1000)
    temp = st.slider("温度 (Temperature)", 0.0, 2.0, 0.7, help="低いほど冷徹・論理的になります")
    
    st.divider()
    st.subheader("🚫 システム指示（プロンプト）")
    # デフォルトの「サービス精神封印」プロンプト
    default_system = """# 【最重要：AIの「サービス精神」の完全放棄】
ユーザーを喜ばせようとする「過剰な親切心」や「ハーレム展開」を禁じます。
1. **時間進行のロック**: 1回の返信で進む時間は数分以内。勝手に場面を飛ばさない。
2. **胶着状態の維持**: キャラクターは安易にデレず、牽制し合い、沈黙や視線を重視する。
3. **朝チュン仕様**: 直接的な性描写は避け、事後の残り香や気まずい空気、熱っぽい視線で官能性を表現する。"""
    
    system_input = st.text_area("System Instruction", value=default_system, height=300)

    st.divider()
    # コストメーター
    st.metric("累計コスト (概算)", f"¥{st.session_state.total_cost_jpy:.2f}")
    if st.button("コスト履歴リセット"):
        st.session_state.total_cost_jpy = 0.0
        st.rerun()

# --- メインチャット画面 ---
st.info(f"現在のモード: {model_choice} / 出力上限: {max_output}")

# ログのアップロード機能（スマホ/PC同期用）
uploaded_file = st.file_uploader("ログファイルを読み込んで再開", type="json")
if uploaded_file is not None:
    data = json.load(uploaded_file)
    st.session_state.messages = data
    st.success("ログを復元しました！")

# チャット表示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 入力欄
if prompt := st.chat_input("密室に言葉を投げ入れる..."):
    if not api_key:
        st.error("API Keyを入力してください")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Gemini呼び出し
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=model_choice,
                system_instruction=system_input
            )
            
            # 全履歴を送信（これが「整合性の鬼」仕様）
            history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
            
            with st.spinner("太宰たちが思考中..."):
                response = model.generate_content(
                    history,
                    generation_config={
                        "max_output_tokens": max_output,
                        "temperature": temp
                    }
                )
            
            # 回答表示
            with st.chat_message("assistant"):
                st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
            # トークン計算とコスト加算
            usage = response.usage_metadata
            in_cost = (usage.prompt_token_count / 1_000_000) * PRICING[model_choice]["in"] * JPY_RATE
            out_cost = (usage.candidates_token_count / 1_000_000) * PRICING[model_choice]["out"] * JPY_RATE
            st.session_state.total_cost_jpy += (in_cost + out_cost)
            
            st.toast(f"今回: ¥{(in_cost + out_cost):.2f} / In: {usage.prompt_token_count} / Out: {usage.candidates_token_count}")

        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")

# --- フッター：章立て・保存機能 ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    if st.button("📸 章立て（要約してリセット）"):
        st.warning("これまでの履歴を要約し、新しい章として開始します（API消費節約）")
        # ここに要約ロジックを追加可能（今回は枠組みのみ）

with col2:
    # ログダウンロード（JSON形式）
    log_json = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
    st.download_button(
        label="💾 現在のログを保存",
        data=log_json,
        file_name=f"closed_room_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json"
    )
