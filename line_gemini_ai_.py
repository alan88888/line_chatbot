import os
import json
from flask import Flask, request, abort
import google.generativeai as genai
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 讀取環境變數
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")  # LINE Bot Access Token
LINE_SECRET = os.getenv("LINE_SECRET")              # LINE Channel Secret
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")        # Gemini API Key

# 確保 API Key 存在
if not LINE_ACCESS_TOKEN or not LINE_SECRET or not GEMINI_API_KEY:
    raise ValueError("❌ LINE 或 GEMINI API Key 未設定，請確認環境變數！")

# 設定 Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-pro")  # 選擇 Gemini 1.5 Pro

# 設定 LINE Bot
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

app = Flask(__name__)

# **全局變數：記錄使用者對話歷史**
conversation_history = {}

@app.route("/", methods=['POST'])
def linebot():
    """ 接收來自 LINE 的 Webhook 事件 """
    body = request.get_data(as_text=True)  # 取得請求的 JSON 資料
    signature = request.headers.get('X-Line-Signature')  # 獲取 LINE 簽名

    try:
        handler.handle(body, signature)  # 驗證 LINE 的請求
    except InvalidSignatureError:
        abort(400)  # 驗證失敗時回傳 400 錯誤

    return 'OK'  # LINE Webhook 驗證時需要回應 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """ 處理使用者傳送的訊息，並記錄歷史對話 """
    user_id = event.source.user_id  # 取得使用者 ID
    user_message = event.message.text  # 取得使用者輸入的訊息
    reply_token = event.reply_token  # 取得回應的 Token

    print(f"👤 使用者 [{user_id}]：{user_message}")

    # **處理清除歷史指令**
    if user_message.lower() == "/reset":
        conversation_history.pop(user_id, None)
        reply = "✅ 已清除對話記錄，你可以重新開始對話！"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=reply))
        return

    # **確保使用者有對話紀錄**
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # **加入對話歷史（最多保留 5 則）**
    conversation_history[user_id].append({"role": "user", "parts": [{"text": user_message}]})
    if len(conversation_history[user_id]) > 5:
        conversation_history[user_id].pop(0)  # 移除最舊的對話，保留 5 則

    # **呼叫 Gemini API**
    try:
        response = gemini_model.generate_content(conversation_history[user_id])
        ai_reply = response.text
    except Exception as e:
        print(f"❌ Gemini API 錯誤：{e}")
        ai_reply = "抱歉，我無法處理你的請求，請稍後再試。"

    # **加入 AI 回應到歷史紀錄**
    conversation_history[user_id].append({"role": "model", "parts": [{"text": ai_reply}]})
    if len(conversation_history[user_id]) > 5:
        conversation_history[user_id].pop(0)

    # **發送回應**
    line_bot_api.reply_message(reply_token, TextSendMessage(text=ai_reply))
    print(f"🤖 AI 回應：{ai_reply}")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
