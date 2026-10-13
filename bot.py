import os
import re
import io
import time
import socket
import threading
import requests
import urllib3.util.connection as urllib3_cn
import telebot
from telebot import apihelper

# ============================================================================
# 1. TURBO IPv4 FORCE (Eliminates IPv6 timeout & makes uploads ultra-fast)
# ============================================================================
def allowed_gai_family():
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family

# Persistent Keep-Alive Session for Telegram API
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=64, max_retries=2)
session.mount("https://", adapter)
session.mount("http://", adapter)
apihelper.SESSION_TIME_TO_LIVE = None

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8726477301:AAGZjQ9V4T_oeA04RDTrnuVuqmuvaG1b09E").strip()
MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", str(5 * 3600 + 20 * 60)))  # 5h 20m auto-exit for GitHub Actions

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=8)

# ============================================================================
# 2. CLEANER & UNICODE SANS-SERIF BOLD ENGINE
# ============================================================================
EMOJI_PATTERN = re.compile(
    "["
    "\\U0001F300-\\U0001F9FF"
    "\\U0001FA00-\\U0001FAFF"
    "\\U00002600-\\U000027BF"
    "\\U0001F100-\\U0001F1FF"
    "\\U00013000-\\U0001342F"
    "\\U00012000-\\U0001254F"
    "\\uFE0F\\u200D"
    "]+",
    flags=re.UNICODE,
)

WATERMARK_KEYWORDS = [
    "Powered by", "Extracted by", "Downloaded by", "Uploaded by",
    "Provided by", "Leaked by", "MadXABhi", "Mad X Abhi", "AS MULTIVERSE",
    "𓊈", "𓊉", "𒆜", "🄼🄰🄳", "🄰🄱🄷🄸", "🚩"
]

FILENAME_BLOCKED_TOKENS = [
    "_MadXABhi", "-MadXABhi", "MadXABhi", "MadXAbhi", "MAD_X_ABHI",
    "AS_MULTIVERSE", "AS MULTIVERSE"
]

RENAMED_FILE_CACHE = {}
LAST_DOC_BY_CHAT = {}

def to_sans_bold(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if 65 <= cp <= 90:
            out.append(chr(0x1D5D4 + (cp - 65)))
        elif 97 <= cp <= 122:
            out.append(chr(0x1D5EE + (cp - 97)))
        elif 48 <= cp <= 57:
            out.append(chr(0x1D7EC + (cp - 48)))
        else:
            out.append(ch)
    return "".join(out)

def normalize_styled_unicode(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x1D5D4 <= cp <= 0x1D5ED:
            out.append(chr(65 + (cp - 0x1D5D4)))
        elif 0x1D5EE <= cp <= 0x1D607:
            out.append(chr(97 + (cp - 0x1D5EE)))
        elif 0x1D7EC <= cp <= 0x1D7F5:
            out.append(chr(48 + (cp - 0x1D7EC)))
        else:
            out.append(ch)
    return "".join(out)

def smart_title_case(text: str) -> str:
    def repl(m):
        w = m.group(0)
        if len(w) >= 2 and w.isupper():
            return w
        return w[0].upper() + w[1:].lower()
    return re.sub(r"[A-Za-z0-9’']+", repl, text)

def strip_emojis(text: str) -> str:
    text = EMOJI_PATTERN.sub("", text)
    return re.sub(r"[𓊈𓊉𒆜乂]", "", text)

def clean_title_value(raw_title: str) -> str:
    text = normalize_styled_unicode(strip_emojis(raw_title))
    for tok in FILENAME_BLOCKED_TOKENS:
        if tok.strip():
            text = re.sub(r"[\s_\-|]*" + re.escape(tok.strip()), "", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s_\-|]*mad\s*x?\s*abhi", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?:\s*[-|–—_]\s*)?(?:\\b(?:144|240|360|480|720|1080|1440|2160)p\\b)?\s*\.(?:mp4|mkv|avi|mov|webm|flv|m4v|pdf|zip|rar)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:\s*[-|–—_]\s*|\s+)\b(?:144|240|360|480|720|1080|1440|2160)p\b\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\.(?:mp4|mkv|avi|mov|webm|pdf)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(and|or|the|of|in|to|for|with|by)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\band\b", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s\-–—_]+$", "", re.sub(r"[_\s]{2,}", " ", text)).strip()
    return smart_title_case(text)

def clean_pdf_filename(raw_name: str, fallback_title: str = "") -> tuple[str, bool]:
    if not raw_name or not raw_name.strip():
        safe = re.sub(r'[\\/:*?"<>|]', "", fallback_title or "Class_Notes").strip()
        return f"{safe}.pdf", True

    orig = raw_name.strip()
    m = re.search(r"(\.[a-zA-Z0-9]{2,5})$", orig)
    ext = m.group(1) if m else ".pdf"
    base = orig[:-len(ext)] if m else orig
    base = normalize_styled_unicode(strip_emojis(base))

    for tok in FILENAME_BLOCKED_TOKENS:
        if tok.strip():
            base = re.sub(r"[\s_\-|]*" + re.escape(tok.strip()) + r"[\s_\-|]*", " ", base, flags=re.IGNORECASE)

    base = re.sub(r"[\s_\-|]*mad\s*x?\s*abhi[\s_\-|]*", " ", base, flags=re.IGNORECASE)
    base = re.sub(r"_[A-Za-z0-9]+$", "", base)
    base = re.sub(r"[\s_\-|]*@[a-zA-Z0-9_]{3,}[\s_\-|]*", " ", base)
    base = re.sub(r"\[[^\]]*\]", "", base)
    base = re.sub(r"^[\s_\-|]+|[\s_\-|]+$", "", re.sub(r"[_\s]{2,}", " ", base)).strip()

    if not base and fallback_title:
        base = re.sub(r'[\\/:*?"<>|]', "", fallback_title).strip()

    clean_name = f"{base or 'Class_Notes'}{ext}"
    return clean_name, (clean_name != orig)

def is_watermark_line(line: str) -> bool:
    s = normalize_styled_unicode(line.strip())
    if not s:
        return False
    if re.search(r"[𓊈𓊉𒆜乂【】『』〖〗༺༻꧁꧂]", s):
        return True
    if re.match(r"^\W*(?:powered\s*by|extracted\s*by|uploaded\s*by|downloaded\s*by|provided\s*by|leaked\s*by|credit\s*:)", s, re.IGNORECASE):
        return True
    low = s.lower()
    for kw in WATERMARK_KEYWORDS:
        ckw = kw.strip().lower()
        if ckw == "🚩" and re.match(r"^(?:🚩|\s)*(?:title|subject|topic)\s*:", s, re.IGNORECASE):
            continue
        if ckw and ckw in low:
            return True
    return False

def format_caption(raw_text: str, fallback_filename: str = "") -> tuple[str, str]:
    lines = (raw_text or "").replace("\r\n", "\n").split("\n")
    title, subject, topic, others = "", "", "", []

    for raw_line in lines:
        s = raw_line.strip()
        if not s:
            continue
        ascii_line = normalize_styled_unicode(s)

        tm = re.match(r"^\W*Title\s*:\s*(.*)$", ascii_line, re.IGNORECASE)
        if tm:
            title = clean_title_value(tm.group(1))
            continue

        sm = re.match(r"^\W*Subject\s*:\s*(.*)$", ascii_line, re.IGNORECASE)
        if sm:
            subject = re.sub(r"\s{2,}", " ", normalize_styled_unicode(strip_emojis(sm.group(1)))).strip()
            continue

        topm = re.match(r"^\\W*Topic\\s*:\\s*(.*)$", ascii_line, re.IGNORECASE)
        if topm:
            topic = re.sub(r"\s{2,}", " ", normalize_styled_unicode(strip_emojis(topm.group(1)))).strip()
            continue

        if re.match(r"^\W*(?:quality|resolution|video\s*quality)\s*[:\-]", ascii_line, re.IGNORECASE):
            continue

        if is_watermark_line(raw_line):
            continue

        cleaned_other = clean_title_value(raw_line)
        if cleaned_other:
            others.append(cleaned_other)

    if not title and fallback_filename:
        title = clean_title_value(fallback_filename)

    parts = []
    if title:
        parts.append(f"🔖 {to_sans_bold('Title:')} {to_sans_bold(title)}")
    if subject:
        parts.append(f"📚 {to_sans_bold('Subject:')} {subject}")
    if topic:
        parts.append(f"📌 {to_sans_bold('Topic:')} {topic}")
    for o in others:
        parts.append(o)

    return "\n\n".join(parts), title

def send_renamed_pdf_fast(chat_id, file_id, file_unique_id, clean_name, caption):
    cache_key = f"{file_unique_id}::{clean_name}" if file_unique_id else None
    if cache_key and cache_key in RENAMED_FILE_CACHE:
        try:
            bot.send_document(chat_id, RENAMED_FILE_CACHE[cache_key], caption=caption)
            return True
        except Exception:
            RENAMED_FILE_CACHE.pop(cache_key, None)

    file_info = bot.get_file(file_id)
    dl_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    resp = session.get(dl_url, timeout=15)
    resp.raise_for_status()

    bio = io.BytesIO(resp.content)
    bio.name = clean_name
    sent = bot.send_document(chat_id, bio, caption=caption, visible_file_name=clean_name)
    if sent and getattr(sent, "document", None) and cache_key:
        RENAMED_FILE_CACHE[cache_key] = sent.document.file_id
    return True

# ============================================================================
# 3. BOT HANDLERS
# ============================================================================
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.send_message(message.chat.id, "⚡ Ready.")

@bot.message_handler(commands=["name"])
def handle_name_cmd(message):
    chat_id = message.chat.id
    last_doc = LAST_DOC_BY_CHAT.get(chat_id)
    if not last_doc:
        bot.send_message(chat_id, "Send PDF first.")
        return

    arg = re.sub(r"^/name(?:@\S+)?\s*", "", message.text or "", flags=re.IGNORECASE).strip()
    if not arg:
        last_doc["awaiting"] = True
        bot.send_message(chat_id, "Send new name:")
        return

    final_name = arg if re.search(r"\.[a-z0-9]{2,5}$", arg, re.IGNORECASE) else f"{arg}{last_doc['ext']}"
    last_doc["awaiting"] = False
    send_renamed_pdf_fast(chat_id, last_doc["file_id"], last_doc["unique_id"], final_name, last_doc["caption"])

@bot.message_handler(content_types=["video", "document", "photo", "animation", "audio"])
def handle_media(message):
    chat_id = message.chat.id
    doc = message.document
    vid = message.video
    fname = doc.file_name if doc else (vid.file_name if vid else "")
    raw_caption = message.caption or (f"Title: {fname}" if fname else "")
    cleaned_caption, extracted_title = format_caption(raw_caption, fname or "")

    if doc:
        ext_m = re.search(r"(\.[a-zA-Z0-9]{2,5})$", fname or "")
        LAST_DOC_BY_CHAT[chat_id] = {
            "file_id": doc.file_id,
            "unique_id": getattr(doc, "file_unique_id", ""),
            "ext": ext_m.group(1) if ext_m else ".pdf",
            "caption": cleaned_caption,
            "awaiting": False,
        }
        clean_name, was_modified = clean_pdf_filename(fname or "", extracted_title)
        if was_modified and (not doc.file_size or doc.file_size <= 20 * 1024 * 1024):
            try:
                send_renamed_pdf_fast(chat_id, doc.file_id, getattr(doc, "file_unique_id", ""), clean_name, cleaned_caption)
                return
            except Exception as e:
                print("PDF rename fallback:", e)

    bot.copy_message(
        chat_id=chat_id,
        from_chat_id=chat_id,
        message_id=message.message_id,
        caption=cleaned_caption,
    )

@bot.message_handler(content_types=["text"])
def handle_text(message):
    chat_id = message.chat.id
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        return

    last_doc = LAST_DOC_BY_CHAT.get(chat_id)
    if last_doc and last_doc.get("awaiting"):
        last_doc["awaiting"] = False
        final_name = txt if re.search(r"\.[a-z0-9]{2,5}$", txt, re.IGNORECASE) else f"{txt}{last_doc['ext']}"
        send_renamed_pdf_fast(chat_id, last_doc["file_id"], last_doc["unique_id"], final_name, last_doc["caption"])
        return

    cleaned_caption, _ = format_caption(txt)
    if cleaned_caption:
        bot.send_message(chat_id, cleaned_caption)

# ============================================================================
# 4. 5-HOUR AUTO-RESTART TIMER
# ============================================================================
def auto_shutdown_timer():
    time.sleep(MAX_RUNTIME_SECONDS)
    print("Restarting for GitHub 24/7...")
    bot.stop_polling()
    os._exit(0)

if __name__ == "__main__":
    try:
        session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url": "https://example.com/reset"}, timeout=5)
        session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", json={"drop_pending_updates": False}, timeout=5)
    except Exception:
        pass

    t = threading.Thread(target=auto_shutdown_timer, daemon=True)
    t.start()

    print("⚡ TeleClean Turbo Bot active...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=False)
