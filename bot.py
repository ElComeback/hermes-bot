"""Railway Telegram Bot — uses DeepSeek API."""
import asyncio, os, logging, sys
import httpx
from openai import AsyncOpenAI
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 8080))

client = AsyncOpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com", http_client=httpx.AsyncClient(trust_env=False))
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

async def send(chat_id, text):
    async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
        await c.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": text})

async def ask_deepseek(text):
    r = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": text}],
        max_tokens=1000
    )
    return r.choices[0].message.content or "..."

async def bot_loop():
    offset = 0
    print("BOT LISTO", flush=True)
    async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
        while True:
            try:
                r = await c.post(f"{URL}/getUpdates", json={
                    "offset": offset, "timeout": 15
                }, timeout=20)
                for upd in r.json().get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    uid = str(msg.get("from", {}).get("id", ""))
                    text = msg.get("text", "")
                    chat_id = msg["chat"]["id"]
                    if uid not in ALLOWED:
                        await send(chat_id, "No autorizado.")
                        continue
                    reply = await ask_deepseek(text)
                    await send(chat_id, reply[:4000])
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
