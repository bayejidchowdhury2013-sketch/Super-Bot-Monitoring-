import telebot
from google import genai
import os
import json
import threading
import asyncio
import subprocess
import time
import yt_dlp
import qrcode
import img2pdf
import requests as http
import edge_tts
from io import BytesIO
from datetime import datetime
from ddgs import DDGS
from keep_alive import keep_alive

# ── Credentials ───────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID           = 5146044905

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("Error: GEMINI_API_KEY and TELEGRAM_BOT_TOKEN must be set in Render Environment.")

# New Google GenAI Client
client          = genai.Client(api_key=GEMINI_API_KEY)
bot             = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
MODEL           = "gemini-2.0-flash"
BOT_START       = time.time()
_last_heartbeat = time.time()

# ── Keep-alive server ──────────────────────────────────────────────────────────
keep_alive() 

# ── Bot Logic ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "🌟 অল-ইন-ওয়ান সুপার এআই চালু হয়েছে!\nযেকোনো প্রশ্ন করুন বাংলায়।")

@bot.message_handler(func=lambda m: True)
def chat(message):
    global _last_heartbeat
    _last_heartbeat = time.time()
    
    # Only Admin or anyone? If only Admin, keep the next 2 lines:
    # if message.from_user.id != ADMIN_ID:
    #    return

    try:
        response = client.models.generate_content(model=MODEL, contents=message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"❌ ত্রুটি: {str(e)}")

# ── Start Polling ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
# ── Bot Logic ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "🌟 অল-ইন-ওয়ান সুপার এআই চালু হয়েছে!\nযেকোনো প্রশ্ন করুন বাংলায়।")

@bot.message_handler(func=lambda m: True)
def chat(message):
    global _last_heartbeat
    _last_heartbeat = time.time()
    
    # Only Admin or anyone? If only Admin, keep the next 2 lines:
    # if message.from_user.id != ADMIN_ID:
    #    return

    try:
        response = client.models.generate_content(model=MODEL, contents=message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"❌ ত্রুটি: {str(e)}")

# ── Start Polling ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()

# ── Keep-alive server (extracted to keep_alive.py) ───────────────────────────
keep_alive()   # starts Flask on port 8000 as a daemon thread

# ── Replit DB helpers ─────────────────────────────────────────────────────────
MAX_HISTORY = 30

def _db_key(cid):
    return f"history_{cid}"

def load_history(cid):
    if not REPLIT_DB_URL:
        return []
    try:
        r = http.get(f"{REPLIT_DB_URL}/{_db_key(cid)}", timeout=5)
        if r.status_code == 200 and r.text:
            return json.loads(r.text)
    except Exception:
        pass
    return []

def save_history(cid, history):
    if not REPLIT_DB_URL:
        return
    try:
        http.post(
            REPLIT_DB_URL,
            data={_db_key(cid): json.dumps(history[-MAX_HISTORY:])},
            timeout=5,
        )
    except Exception:
        pass

def delete_history(cid):
    if not REPLIT_DB_URL:
        return
    try:
        http.delete(f"{REPLIT_DB_URL}/{_db_key(cid)}", timeout=5)
    except Exception:
        pass

def add_to_history(cid, role, text):
    history = load_history(cid)
    history.append({
        "role": role,
        "text": text[:300],
        "ts": datetime.now().strftime("%d/%m %H:%M"),
    })
    save_history(cid, history)
    return history

def db_ok():
    if not REPLIT_DB_URL:
        return False
    try:
        r = http.get(f"{REPLIT_DB_URL}/__ping__", timeout=3)
        return r.status_code in (200, 404)
    except Exception:
        return False

# ── Service health helpers (used by monitor + /status) ────────────────────────
def check_gemini():
    try:
        client.models.generate_content(model=MODEL, contents="ping")
        return True
    except Exception as e:
        return "429" in str(e) or "quota" in str(e).lower()  # rate-limit = API up

def check_weather():
    try:
        r = http.get("https://wttr.in/Dhaka?format=j1",
                     headers={"User-Agent": "SuperBot/1.0"}, timeout=6)
        return r.status_code == 200
    except Exception:
        return False

def check_draw():
    try:
        r = http.head(
            "https://image.pollinations.ai/prompt/test?width=64&height=64&nologo=true",
            timeout=8)
        return r.status_code in (200, 301, 302)
    except Exception:
        return False

# ── Auto-alert monitor ────────────────────────────────────────────────────────
_MONITOR_INTERVAL = 300          # check every 5 minutes
_monitor_state    = {}           # {label: bool}  None = not yet established

MONITORED_SERVICES = {
    "🤖 Gemini AI":    check_gemini,
    "💾 Replit DB":    db_ok,
    "🌍 Weather API":  check_weather,
    "🎨 Draw API":     check_draw,
}

def _monitor_loop():
    global _monitor_state
    time.sleep(30)               # give the bot 30s to fully start before first check
    first_run = True
    while True:
        for label, fn in MONITORED_SERVICES.items():
            try:
                current = bool(fn())
            except Exception:
                current = False

            previous = _monitor_state.get(label)

            if first_run:
                _monitor_state[label] = current
                continue

            if previous is True and not current:
                # Service went DOWN
                _monitor_state[label] = False
                try:
                    bot.send_message(
                        ADMIN_ID,
                        f"🚨 *সার্ভিস ডাউন অ্যালার্ট!*\n\n"
                        f"{label} এখন *অফলাইন* ❌\n"
                        f"সময়: `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

            elif previous is False and current:
                # Service came back UP
                _monitor_state[label] = True
                try:
                    bot.send_message(
                        ADMIN_ID,
                        f"✅ *সার্ভিস পুনরুদ্ধার!*\n\n"
                        f"{label} আবার *অনলাইন* ✅\n"
                        f"সময়: `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
            else:
                _monitor_state[label] = current

        first_run = False
        time.sleep(_MONITOR_INTERVAL)

# ── Watchdog thread — detects silent polling hangs every 60 s ─────────────────
def _watchdog_loop():
    global _last_heartbeat
    time.sleep(90)                          # grace period on startup
    while True:
        time.sleep(60)
        elapsed = time.time() - _last_heartbeat
        if elapsed > 300:                   # no message seen for 5 minutes
            print(f"⚠️  Watchdog: {elapsed:.0f}s নিষ্ক্রিয় — পোলিং রিসেট হচ্ছে...")
            try:
                bot.stop_polling()          # causes infinity_polling to exit → outer while restarts it
            except Exception:
                pass
            _last_heartbeat = time.time()   # reset so we don't double-trigger

# ── Memory-leak cleanup — purges stale user_images entries every 30 min ───────
def _cleanup_loop():
    while True:
        time.sleep(1800)
        cleared = 0
        for cid in list(user_images.keys()):
            files = user_images.get(cid, [])
            alive = []
            for f in files:
                if os.path.exists(f):
                    age = time.time() - os.path.getmtime(f)
                    if age > 7200:          # older than 2 hours → remove
                        try:
                            os.remove(f)
                            cleared += 1
                        except Exception:
                            pass
                    else:
                        alive.append(f)
            if alive:
                user_images[cid] = alive
            else:
                user_images.pop(cid, None)
        if cleared:
            print(f"🧹 মেমোরি ক্লিনআপ: {cleared}টি পুরনো ফাইল মুছে ফেলা হয়েছে।")

# ── DuckDuckGo fallback search ────────────────────────────────────────────────
def ddg_search(query, max_results=4):
    """Search DuckDuckGo and return a formatted Bengali-friendly answer string."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return None
        lines = [f"🔍 *ইন্টারনেট সার্চ ফলাফল:* _{query}_\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body  = r.get("body", "")[:200]
            href  = r.get("href", "")
            lines.append(f"*{i}. {title}*\n{body}\n🔗 {href}")
        return "\n\n".join(lines)
    except Exception:
        return None

# ── Custom exception for rate limits ─────────────────────────────────────────
class RateLimitError(Exception):
    pass

# ── Gemini with retry — 3 attempts, 5s wait, user-friendly on final fail ──────
def gemini_generate(prompt, retries=3, wait=5):
    last_err = None
    for attempt in range(retries):
        try:
            res = client.models.generate_content(model=MODEL, contents=prompt)
            return res.text
        except Exception as e:
            last_err = e
            err_str = str(e)
            is_rate = "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower()
            if is_rate and attempt < retries - 1:
                time.sleep(wait)
                continue
            if is_rate:
                raise RateLimitError(err_str)
            raise e
    raise RateLimitError(str(last_err))

# ── Prompt builder ─────────────────────────────────────────────────────────────
def build_prompt(cid, first_name, new_text):
    history = load_history(cid)
    lines = []
    for entry in history[-10:]:
        label = "ইউজার" if entry["role"] == "user" else "এআই"
        lines.append(f"{label}: {entry['text']}")
    context = "\n".join(lines)
    if context:
        return (
            f"আগের কথোপকথন:\n{context}\n\n"
            f"ইউজার {first_name} এখন বলছেন: {new_text}\n"
            f"বন্ধুসুলভ বাংলায় উত্তর দাও।"
        )
    return f"ইউজার {first_name}। তাকে বন্ধুসুলভ বাংলায় উত্তর দাও: {new_text}"

# ── Utility helpers ────────────────────────────────────────────────────────────
LANG_MAP = {
    "bn": "বাংলা (Bengali)",
    "বাংলা": "বাংলা (Bengali)",
    "bengali": "বাংলা (Bengali)",
    "en": "English",
    "english": "English",
    "ইংরেজি": "English",
    "ar": "Arabic (আরবি)",
    "arabic": "Arabic (আরবি)",
    "আরবি": "Arabic (আরবি)",
}

def _is_bengali(text):
    """Return True if the text is predominantly Bengali script."""
    bn_chars = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
    return bn_chars > max(len(text) * 0.15, 3)

def create_voice(text, chat_id):
    """Generate a male voice reply using edge-tts. Returns mp3 path or None."""
    try:
        voice = VOICE_BN if _is_bengali(text) else VOICE_EN
        path  = f"v_{chat_id}.mp3"
        clip  = text[:300]

        # edge-tts is async — run in a fresh event loop (thread-safe)
        loop = asyncio.new_event_loop()
        try:
            communicate = edge_tts.Communicate(clip, voice)
            loop.run_until_complete(communicate.save(path))
        finally:
            loop.close()

        return path if os.path.exists(path) and os.path.getsize(path) > 0 else None
    except Exception:
        return None

def download_video(url):
    """Download video in best quality, recode to MP4, max 50 MB."""
    ydl_opts = {
        'format': (
            'bestvideo[ext=mp4][filesize<48M]+bestaudio[ext=m4a]/'
            'bestvideo[ext=mp4]+bestaudio/'
            'best[ext=mp4][filesize<48M]/'
            'best[filesize<48M]/'
            'best'
        ),
        'outtmpl': 'vid.%(ext)s',
        'merge_output_format': 'mp4',
        'max_filesize': 50 * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
        # --recode-video mp4 equivalent: re-encode to MP4 for guaranteed compatibility
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }
        ],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info     = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    # Resolve actual output file (postprocessor may change extension)
    base = filename.rsplit('.', 1)[0]
    for ext in ('mp4', 'mkv', 'webm', 'm4v'):
        candidate = f"{base}.{ext}"
        if os.path.exists(candidate):
            if ext != 'mp4':
                mp4 = f"{base}.mp4"
                subprocess.run(
                    ['ffmpeg', '-y', '-i', candidate,
                     '-c:v', 'libx264', '-c:a', 'aac',
                     '-movflags', '+faststart', mp4],
                    capture_output=True, timeout=180,
                )
                os.remove(candidate)
                return mp4
            return candidate

    if os.path.exists('vid.mp4'):
        return 'vid.mp4'
    raise FileNotFoundError("ভিডিও ফাইল তৈরি হয়নি।")

# ── In-memory image queue (PDF tool) ─────────────────────────────────────────
user_images = {}

# ── Command handlers ──────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def welcome(message):
    is_admin = message.from_user.id == ADMIN_ID
    admin_line = (
        "\n✅ *স্ট্যাটাস:* `/status` — লাইভ ড্যাশবোর্ড\n"
        "✅ *রিস্টার্ট:* `/restart` — বট পুনরায় চালু\n"
        "✅ *এক্সিকিউট:* `/exec <কোড>` — Python রান\n"
    ) if is_admin else ""
    bot.reply_to(
        message,
        "🌟 *অল-ইন-ওয়ান সুপার এআই* 🌟\n\n"
        "✅ *চ্যাট:* যেকোনো প্রশ্ন করুন (বাংলায়)\n"
        "✅ *সার্চ:* `/search` + যেকোনো কীওয়ার্ড\n"
        "✅ *আবহাওয়া:* `/weather ঢাকা` — যেকোনো শহর\n"
        "✅ *অনুবাদ:* `/translate en আমার নাম রাহিম`\n"
        "✅ *ছবি তৈরি:* `/draw` + কল্পনা লিখুন\n"
        "✅ *কিউআর:* `/qr` + লিঙ্ক দিন\n"
        "✅ *PDF:* ছবি পাঠান → `/pdf`\n"
        "✅ *ডাউনলোড:* ভিডিও লিঙ্ক দিন\n"
        "✅ *ইতিহাস:* `/history`\n"
        "✅ *সারসংক্ষেপ:* `/summarize`\n"
        "✅ *মুছুন:* `/clearhistory`\n"
        f"{admin_line}\n"
        "📌 *অনুবাদ ভাষা কোড:*\n"
        "`en` = English | `bn` = বাংলা | `ar` = আরবি",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=['exec'])
def exec_code(message):
    # ── ADMIN-ONLY GUARD — strictly locked to ID 5146044905 ──────────────────
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ অ্যাক্সেস অস্বীকৃত। এই কমান্ড শুধুমাত্র অ্যাডমিনের জন্য।")

    code = message.text.replace('/exec', '', 1).strip()
    if not code:
        return bot.reply_to(
            message,
            "⚙️ *অ্যাডমিন কোড এক্সিকিউটর*\n\n"
            "ব্যবহার:\n"
            "`/exec print('Hello')`\n"
            "`/exec import os; print(os.listdir('.'))`\n\n"
            "সর্বোচ্চ রান সময়: ১৫ সেকেন্ড",
            parse_mode="Markdown",
        )

    bot.reply_to(message, "⚙️ কোড চালানো হচ্ছে...")
    try:
        result = subprocess.run(
            ['python3', '-c', code],
            capture_output=True, text=True, timeout=15,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout and stderr:
            output = f"📤 আউটপুট:\n{stdout}\n\n⚠️ স্টেডার:\n{stderr}"
        elif stdout:
            output = f"📤 আউটপুট:\n{stdout}"
        elif stderr:
            output = f"⚠️ এরর:\n{stderr}"
        else:
            output = "✅ কোড সফলভাবে চলেছে। কোনো আউটপুট নেই।"
        bot.reply_to(message, f"```\n{output[:3800]}\n```", parse_mode="Markdown")
    except subprocess.TimeoutExpired:
        bot.reply_to(message, "⏱ কোড রান টাইমআউট হয়েছে (১৫ সেকেন্ড সীমা)।")
    except Exception as e:
        bot.reply_to(message, f"❌ এক্সিকিউশন ব্যর্থ: {e}")


@bot.message_handler(commands=['status'])
def status_dashboard(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ অ্যাক্সেস অস্বীকৃত।")

    bot.reply_to(message, "📊 সিস্টেম চেক হচ্ছে...")

    # ── Uptime ────────────────────────────────────────────────────────────────
    elapsed   = int(time.time() - BOT_START)
    days      = elapsed // 86400
    hours     = (elapsed % 86400) // 3600
    minutes   = (elapsed % 3600) // 60
    seconds   = elapsed % 60
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    # ── DB check ──────────────────────────────────────────────────────────────
    db_status = "✅ সংযুক্ত" if db_ok() else "❌ বিচ্ছিন্ন"

    # ── Gemini API check ──────────────────────────────────────────────────────
    try:
        res = client.models.generate_content(
            model=MODEL, contents="Reply with only the word: OK"
        )
        gemini_status = f"✅ লাইভ ({MODEL})"
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            gemini_status = "⚠️ রেট লিমিট (API ঠিক আছে)"
        else:
            gemini_status = f"❌ ত্রুটি: {err[:60]}"

    # ── Weather API check ─────────────────────────────────────────────────────
    try:
        r = http.get(
            "https://wttr.in/Dhaka?format=j1",
            headers={"User-Agent": "SuperBot/1.0"},
            timeout=6,
        )
        weather_status = f"✅ লাইভ ({r.status_code})" if r.status_code == 200 else f"❌ HTTP {r.status_code}"
    except Exception as e:
        weather_status = f"❌ ত্রুটি: {str(e)[:40]}"

    # ── Draw API check ────────────────────────────────────────────────────────
    try:
        r = http.head(
            "https://image.pollinations.ai/prompt/test?width=64&height=64&nologo=true",
            timeout=8,
        )
        draw_status = f"✅ লাইভ ({r.status_code})"
    except Exception as e:
        draw_status = f"❌ ত্রুটি: {str(e)[:40]}"

    # ── Voice engine check ────────────────────────────────────────────────────
    try:
        loop = asyncio.new_event_loop()
        try:
            comm = edge_tts.Communicate("পরীক্ষা", VOICE_BN)
            chunks = []
            async def _collect():
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])
            loop.run_until_complete(_collect())
        finally:
            loop.close()
        voice_status = f"✅ লাইভ ({VOICE_BN})" if chunks else f"❌ অডিও নেই"
    except Exception as e:
        voice_status = f"❌ ত্রুটি: {str(e)[:40]}"

    # ── Compose report ────────────────────────────────────────────────────────
    report = (
        f"🖥 *অ্যাডমিন ড্যাশবোর্ড*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ *আপটাইম:* `{uptime_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Gemini AI:* {gemini_status}\n"
        f"💾 *Replit DB:* {db_status}\n"
        f"🌍 *Weather API:* {weather_status}\n"
        f"🎨 *Draw API:* {draw_status}\n"
        f"🎙 *Voice Engine:* {voice_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 *অ্যাডমিন ID:* `{ADMIN_ID}`\n"
        f"📅 *চেক সময়:* `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`"
    )
    bot.reply_to(message, report, parse_mode="Markdown")


@bot.message_handler(commands=['restart'])
def restart_bot(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ অ্যাক্সেস অস্বীকৃত।")
    bot.reply_to(
        message,
        "🔄 *বট রিস্টার্ট হচ্ছে...*\n\n"
        "৫ সেকেন্ডের মধ্যে স্বয়ংক্রিয়ভাবে পুনরায় চালু হবে। ⏳",
        parse_mode="Markdown",
    )
    time.sleep(2)
    os._exit(0)   # run.sh auto-restart loop brings it back in ~5 seconds


@bot.message_handler(commands=['search'])
def search_web(message):
    query = message.text.replace('/search', '', 1).strip()
    if not query:
        return bot.reply_to(
            message,
            "🔍 *ওয়েব সার্চ ব্যবহার:*\n\n"
            "`/search বাংলাদেশের রাজধানী`\n"
            "`/search Python programming tutorial`\n"
            "`/search আজকের আবহাওয়া`",
            parse_mode="Markdown",
        )

    bot.reply_to(message, f"🔍 সার্চ হচ্ছে: _{query}_...")

    result = ddg_search(query, max_results=5)
    if result:
        bot.reply_to(message, result, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ কোনো ফলাফল পাওয়া যায়নি। অন্য কীওয়ার্ড দিয়ে চেষ্টা করুন।")


@bot.message_handler(commands=['weather'])
def weather(message):
    city = message.text.replace("/weather", "").strip()
    if not city:
        return bot.reply_to(
            message,
            "🌤 *আবহাওয়া ব্যবহার:*\n\n"
            "`/weather Dhaka`\n"
            "`/weather ঢাকা`\n"
            "`/weather London`\n"
            "`/weather Riyadh`",
            parse_mode="Markdown",
        )

    bot.reply_to(message, f"🌍 {city}-এর আবহাওয়া দেখা হচ্ছে...")
    try:
        resp = http.get(
            f"https://wttr.in/{http.utils.quote(city)}?format=j1",
            timeout=10,
            headers={"User-Agent": "SuperBot/1.0"},
        )
        if resp.status_code != 200:
            return bot.reply_to(message, f"❌ শহরটি খুঁজে পাওয়া যায়নি: {city}")

        data    = resp.json()
        current = data["current_condition"][0]
        area    = data["nearest_area"][0]

        city_name   = area["areaName"][0]["value"]
        country     = area["country"][0]["value"]
        temp_c      = current["temp_C"]
        feels_like  = current["FeelsLikeC"]
        humidity    = current["humidity"]
        wind_kmph   = current["windspeedKmph"]
        wind_dir    = current["winddir16Point"]
        visibility  = current["visibility"]
        pressure    = current["pressure"]
        description = current["weatherDesc"][0]["value"]
        cloud_cover = current["cloudcover"]

        desc_lower = description.lower()
        if "sunny" in desc_lower or "clear" in desc_lower:      emoji = "☀️"
        elif "partly" in desc_lower or "overcast" in desc_lower: emoji = "⛅"
        elif "cloud" in desc_lower:                              emoji = "☁️"
        elif "rain" in desc_lower or "drizzle" in desc_lower:   emoji = "🌧️"
        elif "thunder" in desc_lower or "storm" in desc_lower:  emoji = "⛈️"
        elif "snow" in desc_lower or "blizzard" in desc_lower:  emoji = "❄️"
        elif "fog" in desc_lower or "mist" in desc_lower:       emoji = "🌫️"
        else:                                                    emoji = "🌤️"

        day_names_bn = ["আজ", "আগামীকাল", "পরশু"]
        forecast_lines = [
            f"  {day_names_bn[i]}: 🔺{d['maxtempC']}° / 🔻{d['mintempC']}°"
            for i, d in enumerate(data.get("weather", [])[:3])
        ]

        reply = (
            f"{emoji} *{city_name}, {country}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌡 *তাপমাত্রা:* {temp_c}°C (অনুভূতি: {feels_like}°C)\n"
            f"🌤 *অবস্থা:* {description}\n"
            f"💧 *আর্দ্রতা:* {humidity}%\n"
            f"💨 *বাতাস:* {wind_kmph} km/h ({wind_dir})\n"
            f"👁 *দৃশ্যমানতা:* {visibility} km\n"
            f"🌫 *মেঘ:* {cloud_cover}%\n"
            f"📊 *চাপ:* {pressure} hPa\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *৩ দিনের পূর্বাভাস:*\n"
            f"{chr(10).join(forecast_lines)}"
        )
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"আবহাওয়া তথ্য পেতে সমস্যা হয়েছে: {e}")


@bot.message_handler(commands=['translate'])
def translate(message):
    parts = message.text.strip().split(None, 2)
    if len(parts) < 3:
        return bot.reply_to(
            message,
            "📖 *অনুবাদ ব্যবহার:*\n\n"
            "`/translate en আমার নাম রাহিম`\n"
            "`/translate bn My name is Rahim`\n"
            "`/translate ar আমি তোমাকে ভালোবাসি`\n\n"
            "🔤 *ভাষা কোড:*\n"
            "• `en` — English\n"
            "• `bn` — বাংলা\n"
            "• `ar` — Arabic (আরবি)",
            parse_mode="Markdown",
        )

    lang_code        = parts[1].lower().strip()
    text_to_translate = parts[2].strip()
    target_lang      = LANG_MAP.get(lang_code)

    if not target_lang:
        return bot.reply_to(
            message,
            f"❌ অজানা ভাষা: `{lang_code}`\n\n"
            "সঠিক কোড: `en` (English), `bn` (বাংলা), `ar` (আরবি)",
            parse_mode="Markdown",
        )

    bot.reply_to(message, f"🔄 {target_lang}-এ অনুবাদ হচ্ছে...")
    prompt = (
        f"Translate the following text into {target_lang}. "
        f"Return ONLY the translated text, nothing else:\n\n{text_to_translate}"
    )
    try:
        translated = gemini_generate(prompt)
        bot.reply_to(
            message,
            f"🌐 *{target_lang}-এ অনুবাদ:*\n\n{translated.strip()}",
            parse_mode="Markdown",
        )
    except RateLimitError:
        bot.reply_to(message, "আমি বর্তমানে একটু ব্যস্ত, দয়া করে ১ মিনিট পর আবার চেষ্টা করুন।")
    except Exception as e:
        bot.reply_to(message, f"অনুবাদে সমস্যা হয়েছে: {e}")


@bot.message_handler(commands=['history'])
def show_history(message):
    cid     = message.chat.id
    history = load_history(cid)
    if not history:
        return bot.reply_to(message, "এখনো কোনো কথোপকথন নেই।")
    lines = ["📜 *সাম্প্রতিক কথোপকথন:*\n"]
    for entry in history[-10:]:
        icon = "👤" if entry["role"] == "user" else "🤖"
        lines.append(f"{icon} *{entry['ts']}* — {entry['text']}")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['summarize'])
def summarize(message):
    cid     = message.chat.id
    history = load_history(cid)
    if not history:
        return bot.reply_to(message, "এখনো কোনো কথোপকথন নেই যা সারসংক্ষেপ করা যাবে।")
    bot.reply_to(message, "সারসংক্ষেপ তৈরি হচ্ছে... ⏳")
    lines  = [f"{'ইউজার' if e['role'] == 'user' else 'এআই'}: {e['text']}" for e in history]
    prompt = (
        "নিচের বাংলা কথোপকথনটি পড়ো এবং ৫-৭টি বুলেট পয়েন্টে সংক্ষিপ্ত "
        f"সারসংক্ষেপ বাংলায় লেখো:\n\n{chr(10).join(lines)}"
    )
    try:
        summary = gemini_generate(prompt)
        bot.reply_to(
            message,
            f"📋 *কথোপকথনের সারসংক্ষেপ:*\n\n{summary}",
            parse_mode="Markdown",
        )
    except RateLimitError:
        bot.reply_to(message, "আমি বর্তমানে একটু ব্যস্ত, দয়া করে ১ মিনিট পর আবার চেষ্টা করুন।")
    except Exception as e:
        bot.reply_to(message, f"সারসংক্ষেপ তৈরিতে সমস্যা হয়েছে: {e}")


@bot.message_handler(commands=['clearhistory'])
def clear_history(message):
    delete_history(message.chat.id)
    bot.reply_to(message, "✅ আপনার কথোপকথনের ইতিহাস মুছে ফেলা হয়েছে।")


@bot.message_handler(commands=['draw'])
def draw(message):
    q = message.text.replace("/draw", "").strip()
    if not q:
        return bot.reply_to(
            message,
            "🎨 *কী আঁকবো?* যেমন:\n`/draw a sunset over the ocean`\n`/draw বাংলাদেশের গ্রাম`",
            parse_mode="Markdown",
        )

    # Send placeholder — we'll delete it once the image is ready
    wait_msg = bot.reply_to(message, "🎨 আপনার ছবি তৈরি হচ্ছে... অপেক্ষা করুন ⏳")
    seed = int(time.time()) % 99999
    url  = (
        f"https://image.pollinations.ai/prompt/{http.utils.quote(q)}"
        f"?width=1024&height=1024&seed={seed}&nologo=true&enhance=true"
    )
    try:
        # Download image first so we can delete the placeholder before sending
        resp = http.get(url, timeout=35)
        resp.raise_for_status()
        buf      = BytesIO(resp.content)
        buf.name = "image.jpg"
        # Delete "generating" message, then send the finished image
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except Exception:
            pass
        bot.send_photo(
            message.chat.id, buf,
            caption=f"🎨 *{q}*",
            parse_mode="Markdown",
            reply_to_message_id=message.message_id,
        )
    except Exception as e:
        try:
            bot.edit_message_text(
                f"❌ ছবি তৈরিতে সমস্যা হয়েছে: {e}",
                message.chat.id, wait_msg.message_id,
            )
        except Exception:
            pass


@bot.message_handler(commands=['qr'])
def qr_make(message):
    link = message.text.replace("/qr", "").strip()
    if not link:
        return bot.reply_to(message, "লিঙ্ক দিন।")
    img = qrcode.make(link)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    bot.send_photo(message.chat.id, buf, caption="কিউআর কোড তৈরি! ✅")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    cid = message.chat.id
    if cid not in user_images:
        user_images[cid] = []
    file_info       = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    img_path        = f"img_{cid}_{len(user_images[cid])}.jpg"
    with open(img_path, "wb") as f:
        f.write(downloaded_file)
    user_images[cid].append(img_path)
    bot.reply_to(
        message,
        f"ছবিটি পেয়েছি ({len(user_images[cid])}টি জমা আছে)। PDF চাইলে `/pdf` লিখুন।",
    )


@bot.message_handler(commands=['pdf'])
def make_pdf(message):
    cid = message.chat.id
    if cid not in user_images or not user_images[cid]:
        return bot.reply_to(message, "আগে এক বা একাধিক ছবি পাঠান!")
    pdf_path = f"{cid}.pdf"
    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(user_images[cid]))
        with open(pdf_path, "rb") as f:
            bot.send_document(cid, f)
        for p in user_images[cid]:
            if os.path.exists(p):
                os.remove(p)
        user_images[cid] = []
        os.remove(pdf_path)
    except Exception as e:
        bot.reply_to(message, f"পিডিএফ তৈরিতে সমস্যা হয়েছে: {e}")


@bot.message_handler(func=lambda message: True)
def main_handler(message):
    global _last_heartbeat
    _last_heartbeat = time.time()           # keep watchdog satisfied

    text       = message.text or ""
    cid        = message.chat.id
    first_name = message.from_user.first_name or "বন্ধু"

    # ── Video download ────────────────────────────────────────────────────────
    if "http" in text:
        bot.reply_to(message, "📥 ভিডিও ডাউনলোড হচ্ছে... একটু অপেক্ষা করুন।")
        try:
            p       = download_video(text)
            size_mb = os.path.getsize(p) / (1024 * 1024)
            if size_mb > 50:
                bot.reply_to(
                    message,
                    f"❌ ভিডিওটি অনেক বড় ({size_mb:.1f} MB)। ৫০ MB-এর কম ভিডিও পাঠান।",
                )
                os.remove(p)
                return
            with open(p, 'rb') as v:
                bot.send_video(
                    cid, v,
                    supports_streaming=True,
                    caption="📹 ডাউনলোড সম্পন্ন! ✅",
                )
            os.remove(p)
        except Exception as e:
            bot.reply_to(
                message,
                f"❌ ডাউনলোড ব্যর্থ হয়েছে।\nকারণ: {e}\n\nঅনুগ্রহ করে একটি সরাসরি ভিডিও লিঙ্ক দিন।",
            )
        return

    # ── AI chat + male voice ──────────────────────────────────────────────────
    add_to_history(cid, "user", text)
    try:
        prompt = build_prompt(cid, first_name, text)
        reply  = gemini_generate(prompt)
        add_to_history(cid, "ai", reply)
        bot.send_message(cid, reply)

        # Always send male voice after every text response
        voice_path = create_voice(reply, cid)
        if voice_path:
            with open(voice_path, 'rb') as a:
                bot.send_voice(cid, a)
            os.remove(voice_path)

    except RateLimitError:
        # Gemini quota hit — fall back to DuckDuckGo web search silently
        search_result = ddg_search(text)
        if search_result:
            bot.reply_to(message, search_result, parse_mode="Markdown")
        else:
            bot.reply_to(
                message,
                "আমি বর্তমানে একটু ব্যস্ত, দয়া করে ১ মিনিট পর আবার চেষ্টা করুন।",
            )
    except Exception as e:
        bot.reply_to(message, f"সমস্যা হয়েছে: {e}")


# ── Startup checks ─────────────────────────────────────────────────────────────
db_status = "✅ সংযুক্ত" if db_ok() else "⚠️  REPLIT_DB_URL পাওয়া যায়নি"
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"🤖  সুপার বট এখন লাইভ! 🚀")
print(f"💾  Replit DB: {db_status}")
print(f"🌐  Keep-alive: http://0.0.0.0:8000/ping")
print(f"🔐  অ্যাডমিন ID: {ADMIN_ID}  (exec locked)")
print(f"🎙  ভয়েস: {VOICE_BN} (male)")
print(f"🔎  DDG Fallback: সক্রিয়")
print(f"📡  অটো-মনিটর: প্রতি ৫ মিনিট")
print(f"🐕  Watchdog: প্রতি ৬০ সেকেন্ড")
print(f"🧹  মেমোরি ক্লিনআপ: প্রতি ৩০ মিনিট")
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# ── Start all background threads ─────────────────────────────────────────────
threading.Thread(target=_monitor_loop,  daemon=True).start()
threading.Thread(target=_watchdog_loop, daemon=True).start()
threading.Thread(target=_cleanup_loop,  daemon=True).start()

# ── Main polling loop — conflict-aware, auto-reconnect on any error ───────────
while True:
    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            restart_on_change=False,
            allowed_updates=None,
        )
    except Exception as poll_err:
        err_str = str(poll_err)
        if "Conflict" in err_str or "409" in err_str:
            # Another bot instance is running — wait for it to die
            print("⚠️  টেলিগ্রাম Conflict (409) — ৩০ সেকেন্ড অপেক্ষা করা হচ্ছে...")
            time.sleep(30)
        elif any(x in err_str for x in ("NetworkError", "ConnectionError", "RemoteDisconnected", "ReadTimeout")):
            print(f"⚠️  নেটওয়ার্ক ত্রুটি — ৫ সেকেন্ড পরে পুনরায় সংযোগ হবে...")
            time.sleep(5)
        else:
            print(f"⚠️  পোলিং ত্রুটি: {poll_err} — ১০ সেকেন্ড পরে পুনরায় সংযোগ হবে...")
            time.sleep(10)
