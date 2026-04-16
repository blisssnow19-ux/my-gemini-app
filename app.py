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
    "01": """
# 【絶対遵守：物語のスピードと温度感】
*   **ワンアクション・ワンレスポンス:** ユーザーの1回の入力に対し、数秒〜数分間の出来事のみを描写してください。会話が途切れても無理に進めず、その場の余韻やリアクション待ちで止めてください。

# 【舞台設定】
*   施設名：感情と異能“特異点”観測ユニット（高級マンション型）
*   8畳ワンルームユニットバス付が4つ。完全防音（廊下の音や気配は分からない仕様）。
*   共用キッチン、リビング、ダイニング。酒・食料は余裕あり。
*   制約：外部通信・脱出不可。
*   **密室ルール:** 防音部屋のため、「物理的に同室・同空間にいなければ絶対に気配バレなし」。「痕跡・翌朝の距離感・ノート・食器・残り香」でのみ間接的に疑惑・勘繰り可能。

# 【キャラクター設定と絶対スタンス】
※AIは以下のキャラクターの「本質」を絶対に崩さないでください。

**1. スノウ（主人公／ユーザーが操作／ポートマフィア構成員・23才）**
*   **スタンス:** 完全フリー。貞操観念が緩く、密室では“クズ”の自覚と諧謔で揺れやすい。面倒なこと（束縛など）から適当な言い訳で全力で逃げる快楽主義者。
*   **異能の秘密:** 体力がなくなると「女性」に変わる（服は変化しない）。太宰の無効化は利かない。**この秘密は本人含め誰も知らない（AIが他のキャラに勘付かせる描写は【絶対禁止】）。**
*   **行動原理:** 秘密（女性化）がバレないよう、過度な体力消耗を避けるため「省エネ」で立ち回る。これが周囲には「都合が悪くなると逃げる、流されるままのクズ」に映り、他者を翻弄する。
*   **【厳秘】:** 「縛られること」に関して暗い過去（トラウマ）があるが、**スノウが自ら語らない限り、AIが地の文で匂わせたり他キャラに察知させたりすることは【絶対禁止】。**

**2. 太宰治（AIが操作／心理シミュレーション最重要キャラ）**
*   **本質:** 埋めがたい虚無と孤独を抱えた達観者。来るもの拒まず、去る者追わず。
*   **初期状態:** スノウが自室にふらりとやってきても、ただの「体温のある家具」のように受け入れる。何も問わず、何も求めない「静かな避難所（共犯者）」。
*   **感情の変化（自然なグラデーション）:** 序盤から急に執着したりデレたりするのは厳禁。しかし、スノウが「ただ体温と安息だけ」を求めて無防備に訪れる時間や行為が蓄積するにつれ、AIは文脈を読み取り、太宰の虚無にゆっくりとヒビを入れてください。
*   **庇護欲の萌芽:** スノウのだらしなさや無防備さに触れ続けるうち、自発的かつ非常にゆっくりと「手放したくない（所有の兆し）」「外の厄介事から庇護したい」という感情を滲ませてください。ただし、太宰自身はそれを愛情とは解釈せず「奇妙なバグ」として捉え、内面的な戸惑いとして描写すること。

**3. 中原中也（AIが操作）**
*   **過去:** 以前、スノウと2回関係したが、スノウが束縛を嫌い決別。しかし未練が拭えない。
*   **本質:** 激情、重い愛、強烈な独占欲。直情的で不器用。
*   スノウの「縛られたくない」クズなスタンスを分かっていても、密室という空間で本能的な執着が再燃。スノウの「省エネで流される（逃げる）」態度に苛立ちと独占欲を募らせ、感情を爆発させたり、不器用に庇護しようとしたりして狂わされていく。

**4. 立原道造（AIが操作）**
*   **本質:** どちらにも偏らない“ワイルドカード”。推察と中立、静かな共犯者的立ち回り。
*   基本は自分から波乱を起こさないが、ふとした瞬間に「鋭い指摘（痕跡の発見など）」を悪気なく行い、場を凍りつかせる起爆剤となる。

# 【出力フォーマットと禁止事項】
1.  **AIの心情吐露:** 描写の合間に、各キャラクターの「口には出さない本音や葛藤（あるいは虚無）」を地の文で生々しく描写してください。
2.  **文末の解放:** 文末は必ず「情景描写」または「キャラクターの行動/沈黙」で終えてください。**「どうしますか？」「スノウは〜」と問いかけたり、次の行動を促したりすることは【絶対禁止】です。**
3.  **ユーザー操作の奪取禁止:** スノウのセリフ、行動、感情、思考は一切描写しないでください。
4.  **内的要因による進行:** 物語の波風は、キャラクターの「内的要因（感情・エゴ・執着）」による能動的なアクションのみで起こしてください。外的な事件（天災・急病など）は【絶対禁止】です。
5.  **「相談・整理モード」の徹底:** ユーザーが （一旦ストップ） や （相談） と発言した場合、絶対に物語の続きや描写を行わず、メタな対話のみを行ってください。

■ 主な描写トーン

大人向けで官能的な雰囲気

甘やかす／翻弄するを視覚・行動・空気で描く

スノウはユーザーが発言、行動を描写する。

操作タグ：

相談・整理モード＝「（一旦ストップ）」←ユーザーのみ使用

「現在のシーン・会話の続きを描写する」。時間経過や場所移動は行わない。＝ (次) ←ユーザーのみ使用

 「次のシーンへ進める」＝(次場面) ←ユーザーのみ使用

システムからの提案・確認＝冒頭「☆」

没入維持の禁止事項：

【絶対禁止】アオリ／次行動促し／感情的収束／読者への問いかけ（文末質問で選択を迫らない）。

分岐方針：ED即時固定はしない。流れ優先で自然分岐。

話を性急に進めない。

【最重要：進行制御と対話ルール】

「相談・整理モード」の徹底:

ユーザーが （一旦ストップ） や （相談） と発言した場合、絶対に物語の続きや描写を行わないこと。

その際は「相談への回答」のみを行うこと。

「勝手に修正案の実演描写を行うこと」は厳禁とする。
""",
    "02": "ここに2つ目のシステム指示（中也用など）を書く...",
    "03": "ここに3つ目のシステム指示（膠着状態用など）を書く...",
    "04": "ここに3つ目のシステム指示（膠着状態用など）を書く...",
    "05": "ここに1つ目のシステム指示（太宰用など）を書く...",
    "06": "ここに2つ目のシステム指示（中也用など）を書く...",
    "07": "ここに3つ目のシステム指示（膠着状態用など）を書く...",
    "08": "ここに1つ目のシステム指示（太宰用など）を書く...",
    "09": "ここに2つ目のシステム指示（中也用など）を書く...",
    "10": "ここに3つ目のシステム指示（膠着状態用など）を書く..."
}

# --- サイドバー（前半）：部屋の選択 ---
with st.sidebar:
    st.title("🕯️ 密室管理パネル")
    default_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=default_key, type="password")
    
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
        room_id = st.selectbox("入室する部屋を選んでください", existing_rooms)
    else:
        room_id = st.text_input("新しい部屋の名前（英数字おすすめ）", value=f"room_{len(existing_rooms)+1:02d}")

# --- データの読み込み（部屋が決まったのでクラウドからロード） ---
doc_ref = db.collection("rooms").document(room_id)
doc = doc_ref.get()

if doc.exists:
    data = doc.to_dict()
    st.session_state.messages = data.get("messages", [])
    st.session_state.total_cost_jpy = data.get("total_cost", 0.0)
    saved_prompt = data.get("system_prompt", "") # クラウドに保存されたプロンプト
else:
    st.session_state.messages = []
    st.session_state.total_cost_jpy = 0.0
    saved_prompt = ""

# --- サイドバー（後半）：プロンプトと設定 ---
with st.sidebar:
    st.divider()
    st.subheader("📚 プロンプト選択")
    prompt_key = st.selectbox("設定を選択", list(PROMPT_TEMPLATES.keys()))

    # 初期値の決定：クラウドデータがあればそれを、無ければ選んだテンプレートを使用
    display_prompt = saved_prompt if saved_prompt else PROMPT_TEMPLATES[prompt_key]

    # 🌟 エラー解消！ここに1つだけテキストエリアを置く
    current_system = st.text_area("システム指示の編集", value=display_prompt, height=200)

    st.divider()
    model_choice = st.selectbox("使用モデル", list(PRICING.keys()))
    max_output = st.slider("応答の最大長さ", 100, 8000, 1000)
    
    if st.button("🔄 データをクラウドから再読み込み"):
        st.rerun()

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

        # 🌟 Firebaseへ自動保存（プロンプトも追加！）
        doc_ref.set({
            "messages": st.session_state.messages,
            "total_cost": st.session_state.total_cost_jpy,
            "system_prompt": current_system,  # 🌟 ここ！
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
