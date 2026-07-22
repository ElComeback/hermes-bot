"""Railway Telegram Bot — powered by Hermes Agent."""
import asyncio, os, logging, sys, json, urllib.request, subprocess

_HERMES = os.path.join(os.path.dirname(sys.executable), "hermes")
urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.ProxyHandler({})))

# Setup Hermes config at startup
def md_to_html(text):
    """Convert simple markdown to Telegram-compatible HTML."""
    import re
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = re.sub(r'```(.+?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    return text

_HERMES_HOME = os.path.expanduser("~/.hermes")
os.makedirs(_HERMES_HOME, exist_ok=True)
with open(f"{_HERMES_HOME}/config.yaml", "w") as f:
    f.write("model:\n  default: deepseek-chat\n  provider: deepseek\n  base_url: https://api.deepseek.com\n")
with open(f"{_HERMES_HOME}/.env", "w") as f:
    f.write(f"DEEPSEEK_API_KEY={os.environ.get('DEEPSEEK_API_KEY', '')}\n")
    f.write(f"TELEGRAM_BOT_TOKEN={os.environ.get('TELEGRAM_BOT_TOKEN', '')}\n")

from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
ALLOWED = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 8080))
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

def tg_call(method, data):
    req = urllib.request.Request(f"{URL}/{method}",
        data=json.dumps(data).encode(), headers={"Content-Type": "application/json"},
        method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

def clean_hermes(text):
    """Extract response from Hermes CLI box output."""
    lines = text.split("\n")
    inside, out = False, []
    for line in lines:
        if "╭─" in line:
            inside = True
            continue
        if inside and "╰─" in line:
            inside = False
            continue
        if inside:
            c = line.strip().strip("║│ ")
            if c:
                out.append(c)
    return "\n".join(out).strip() or text[:4000]

def ask_hermes(text):
    """Call full Hermes CLI with skills and tools."""
    # Tell Hermes to use markdown, we'll convert to HTML
    enhanced = f"(Responde en español, sé conciso.)\n\n{text}"
    try:
        proc = subprocess.run(
            [_HERMES, "chat", "-q", enhanced],
            capture_output=True, text=True, timeout=120,
            cwd=_HERMES_HOME,
            env={**os.environ, "TERM": "xterm-256color", "PAGER": "cat"}
        )
        reply = clean_hermes(proc.stdout)
        if not reply:
            print(f"HERMES STDERR: {proc.stderr[:500]}", flush=True)
        return reply or "Sin respuesta."
    except subprocess.TimeoutExpired:
        print("HERMES TIMEOUT", flush=True)
        return "La respuesta tardó mucho."
    except FileNotFoundError:
        print(f"HERMES NOT FOUND at {_HERMES}", flush=True)
        return "Error: Hermes no instalado."
    except Exception as e:
        print(f"HERMES ERR: {e}", flush=True)
        return f"Error: {str(e)[:200]}"

async def bot_loop():
    offset = 0
    try:
        r = urllib.request.urlopen(f"{URL}/getMe", timeout=10)
        info = json.loads(r.read())
        print(f"TG OK: @{info['result']['username']}", flush=True)
    except Exception as e:
        print(f"TG FAIL: {e}", flush=True)
    print("BOT LISTO", flush=True)
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
                    tg_call("sendMessage", {"chat_id": chat_id, "text": "No autorizado.", "parse_mode": "HTML"})
                    continue
                reply = await asyncio.to_thread(ask_hermes, text)
                tg_call("sendMessage", {"chat_id": chat_id, "text": md_to_html(reply)[:4000], "parse_mode": "HTML"})
        except urllib.error.HTTPError as e:
            if e.code == 409:
                print("409 - esperando...", flush=True)
                await asyncio.sleep(10)
                continue
            print(f"ERR {e.code}: {e.reason}", flush=True)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"ERR: {e}", flush=True)
            await asyncio.sleep(3)

@app.on_event("startup")
async def startup():
    asyncio.create_task(bot_loop())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
