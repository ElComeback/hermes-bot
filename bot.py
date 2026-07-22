"""Railway Telegram Bot — bypasses proxy for Telegram API calls."""
import asyncio, os, logging, sys, json

# Force no proxy for all urllib requests (Railway injects HTTP_PROXY)
import urllib.request
urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.ProxyHandler({})))
from openai import AsyncOpenAI
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
ALLOWED = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 8080))

client = AsyncOpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com",
                     http_client=__import__("httpx").AsyncClient(trust_env=False))
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

def tg_call(method, data):
    req = urllib.request.Request(f"{URL}/{method}",
        data=json.dumps(data).encode(), headers={"Content-Type": "application/json"},
        method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

async def ask_deepseek(text):
    r = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": text}],
        max_tokens=1000
    )
    return r.choices[0].message.content or "..."

async def bot_loop():
    offset = 0
    # Test API on startup
    try:
        import urllib.request as _ur
        r = _ur.urlopen(f"{URL}/getMe", timeout=10)
        info = json.loads(r.read())
        print(f"TG OK: @{info['result']['username']}", flush=True)
    except Exception as e:
        print(f"TG FAIL: {e}", flush=True)
    print("BOT LISTO", flush=True)
    # Drop pending updates so we don't reprocess old messages
    try: tg_call("deleteWebhook", {"drop_pending_updates": True})
    except: pass
    while True:
        try:
            data = tg_call("getUpdates", {"offset": offset, "timeout": 15})
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                uid = str(msg.get("from", {}).get("id", ""))
                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                if uid not in ALLOWED:
                    tg_call("sendMessage", {"chat_id": chat_id, "text": "No autorizado."})
                    continue
                reply = await ask_deepseek(text)
                tg_call("sendMessage", {"chat_id": chat_id, "text": reply[:4000]})
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"ERR: {e}", flush=True)
            await asyncio.sleep(3)

@app.on_event("startup")
async def startup():
    asyncio.create_task(bot_loop())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
