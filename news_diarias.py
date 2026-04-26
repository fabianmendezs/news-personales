import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, json
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
import feedparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

BASE_DIR       = Path(__file__).parent
INTERESTS_FILE = BASE_DIR / "interests.json"
DAX_FILE       = BASE_DIR / "dax_formulas.json"
PYTHON_FILE    = BASE_DIR / "python_tips.json"
SQL_FILE       = BASE_DIR / "sql_tips.json"
HISTORY_FILE   = BASE_DIR / "news_history.html"
LOGS_DIR       = BASE_DIR / "logs"
MAX_ITEMS      = int(os.getenv("MAX_ITEMS", 5))

SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", 587))
SMTP_USER    = os.getenv("SMTP_USER")
SMTP_PASS    = os.getenv("SMTP_PASS")
DESTINATARIO = os.getenv("DESTINATARIO", SMTP_USER)
REMITENTE    = os.getenv("REMITENTE", f"News Personales <{SMTP_USER}>")

MESES = {
    1:"enero", 2:"febrero", 3:"marzo",    4:"abril",
    5:"mayo",  6:"junio",   7:"julio",    8:"agosto",
    9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre"
}
MARKER = "<!-- NEXT_DAY -->"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fecha_es(d: date = None) -> str:
    d = d or date.today()
    return f"{d.day} de {MESES[d.month]} de {d.year}"

def fetch_interest(feeds: list, max_items: int) -> list:
    items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for e in feed.entries[:max_items]:
                pub = ""
                if getattr(e, "published_parsed", None):
                    pub = datetime(*e.published_parsed[:6]).strftime("%d/%m %H:%M")
                items.append({
                    "title": e.get("title", "Sin título").strip(),
                    "link":  e.get("link", "#"),
                    "pub":   pub,
                })
        except Exception as ex:
            print(f"  ⚠ Feed error [{url}]: {ex}")

    seen, unique = set(), []
    for it in items:
        if it["link"] not in seen:
            seen.add(it["link"])
            unique.append(it)
    return unique[:max_items]

# ─── DAX ──────────────────────────────────────────────────────────────────────

def get_tip(filepath: Path) -> dict:
    with open(filepath, encoding="utf-8") as f:
        items = json.load(f)
    idx = date.today().timetuple().tm_yday % len(items)
    return items[idx]

def render_tip_block(tip: dict, titulo: str) -> str:
    ejemplo_html = tip["ejemplo"].replace("\n", "<br>")
    return (
        f'<hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0 14px">'
        f'<p style="font-weight:bold;margin:0 0 8px;color:#0f172a">{titulo} — '
        f'<code style="font-size:13px">{tip["nombre"]}</code></p>'
        f'<code style="display:block;background:#f1f5f9;padding:10px 12px;border-radius:6px;'
        f'font-size:12px;font-family:Consolas,monospace;color:#1e293b;white-space:pre-wrap">'
        f'{tip["formula"]}</code>'
        f'<p style="margin:10px 0 2px;font-size:12px;color:#475569"><strong>Ejemplo:</strong></p>'
        f'<code style="display:block;background:#f8fafc;padding:8px 12px;border-radius:6px;'
        f'font-size:11px;font-family:Consolas,monospace;color:#334155;white-space:pre-wrap">'
        f'{ejemplo_html}</code>'
        f'<p style="margin:8px 0 0;font-size:12px;color:#64748b">{tip["descripcion"]}</p>'
    )

# ─── HTML ─────────────────────────────────────────────────────────────────────

def render_section(fecha_str: str, noticias: dict, is_open: bool = False,
                   tips: list = None) -> str:
    open_attr = " open" if is_open else ""
    body = ""
    for topic, items in noticias.items():
        if not items:
            continue
        rows = "".join(
            f'<li>'
            f'<a href="{it["link"]}" style="color:#3b82f6;text-decoration:none">{it["title"]}</a>'
            + (f' <small style="color:#94a3b8">{it["pub"]}</small>' if it["pub"] else "")
            + "</li>"
            for it in items
        )
        body += (
            f'<p style="font-weight:bold;margin:14px 0 4px;color:#0f172a">{topic}</p>'
            f'<ul style="margin:0;padding-left:18px;line-height:1.9">{rows}</ul>'
        )
    for titulo, tip in (tips or []):
        body += render_tip_block(tip, titulo)
    return (
        f'<details{open_attr} style="background:#fff;border-radius:8px;padding:16px;'
        f'margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.08)">'
        f'<summary style="cursor:pointer;font-weight:bold;font-size:15px;color:#0f172a">'
        f'📅 {fecha_str}</summary>'
        f'<div style="padding-top:10px">{body}</div>'
        f'</details>'
    )

def build_email(fecha_str: str, noticias: dict, tips: list) -> str:
    section = render_section(fecha_str, noticias, is_open=True, tips=tips)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0">'
        '<div style="max-width:600px;margin:auto">'
        '<h2 style="color:#0f172a;margin-bottom:16px">🗞 News Personales</h2>'
        f'{section}'
        f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">'
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>'
        '</div></body></html>'
    )

# ─── HISTORIAL ────────────────────────────────────────────────────────────────

HISTORY_SHELL = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>News Personales</title>'
    '<style>'
    'body{font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:24px;margin:0}'
    '.wrap{max-width:720px;margin:auto}'
    'h1{color:#0f172a;margin-bottom:20px}'
    'a{color:#3b82f6;text-decoration:none} a:hover{text-decoration:underline}'
    'ul{line-height:1.9}'
    'details>summary{list-style:none} details>summary::-webkit-details-marker{display:none}'
    '</style></head>'
    '<body><div class="wrap">'
    '<h1>🗞 News Personales</h1>'
    f'{MARKER}'
    '</div></body></html>'
)

def update_history(fecha_str: str, noticias: dict, tips: list) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(HISTORY_SHELL, encoding="utf-8")

    html = HISTORY_FILE.read_text(encoding="utf-8")
    if f"📅 {fecha_str}" in html:
        return  # ya guardado hoy

    section = render_section(fecha_str, noticias, tips=tips)
    HISTORY_FILE.write_text(
        html.replace(MARKER, section + "\n" + MARKER, 1),
        encoding="utf-8"
    )

# ─── ENVÍO ────────────────────────────────────────────────────────────────────

def send_email(html_body: str, fecha_str: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"]    = REMITENTE
    msg["To"]      = DESTINATARIO
    msg["Subject"] = f"🗞 News Personales — {fecha_str}"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_USER, DESTINATARIO, msg.as_string())

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    with open(INTERESTS_FILE, encoding="utf-8") as f:
        interests = json.load(f)

    fecha_str = fecha_es()
    print(f"\n{'─'*50}")
    print(f"  News Personales — {fecha_str}")
    print(f"{'─'*50}")

    noticias = {}
    for topic, feeds in interests.items():
        items = fetch_interest(feeds, MAX_ITEMS)
        noticias[topic] = items
        print(f"  {topic}: {len(items)} noticias")

    tips = [
        ("💡 DAX del día",    get_tip(DAX_FILE)),
        ("🐍 Python del día", get_tip(PYTHON_FILE)),
        ("🗄️ SQL del día",    get_tip(SQL_FILE)),
    ]
    for titulo, tip in tips:
        print(f"  {titulo}: {tip['nombre']}")

    update_history(fecha_str, noticias, tips)
    send_email(build_email(fecha_str, noticias, tips), fecha_str)

    total = sum(len(v) for v in noticias.values())
    print(f"\n  ✓ {total} noticias enviadas a {DESTINATARIO}")
    print(f"  ✓ Historial actualizado: news_history.html")
    print(f"{'─'*50}\n")


if __name__ == "__main__":
    main()
