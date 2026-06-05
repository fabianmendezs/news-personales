import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, json, time, urllib.request, shutil
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
import feedparser
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Header

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

DESTINATARIO = os.getenv("DESTINATARIO", "")

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
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            feed = feedparser.parse(raw)
            for e in feed.entries[:max_items]:
                parsed_date = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
                pub = ""
                if parsed_date:
                    pub = datetime(*parsed_date[:6]).strftime("%d/%m %H:%M")
                items.append({
                    "title":      e.get("title", "Sin título").strip(),
                    "link":       e.get("link", "#"),
                    "pub":        pub,
                    "_sort_date": parsed_date,
                })
        except Exception as ex:
            print(f"  ⚠ Feed error [{url}]: {ex}")

    seen, unique = set(), []
    for it in items:
        if it["link"] not in seen:
            seen.add(it["link"])
            unique.append(it)

    unique.sort(key=lambda x: (
        x["_sort_date"] is None,
        -time.mktime(x["_sort_date"]) if x["_sort_date"] else 0,
    ))
    for it in unique:
        del it["_sort_date"]

    return unique[:max_items]

# ─── GROQ ─────────────────────────────────────────────────────────────────────

def get_ai_summary(topic: str, items: list) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not items:
        return ""
    try:
        from groq import Groq
        titulos = "\n".join(f"- {it['title']}" for it in items)
        prompt = (
            f"Se te dan los títulos de las noticias del día sobre '{topic}':\n{titulos}\n\n"
            f"Escribe un párrafo de 2 a 3 oraciones resumiendo estas noticias en español, "
            f"sin listas ni bullets, en tono informativo."
        )
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as ex:
        print(f"  ⚠ Groq error [{topic}]: {ex}")
        return ""

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

def build_email(fecha_str: str, noticias: dict, tips: list, resumenes: dict = None) -> str:
    resumenes = resumenes or {}

    summaries_content = ""
    for topic in noticias:
        resumen = resumenes.get(topic, "")
        if resumen:
            summaries_content += (
                f'<p style="font-weight:600;margin:10px 0 2px;color:#0f172a;font-size:13px">{topic}</p>'
                f'<p style="margin:0 0 10px;color:#334155;font-size:13px;line-height:1.6;text-align:justify">{resumen}</p>'
            )
    ai_block = ""
    if summaries_content:
        ai_block = (
            '<div style="background:#fff;border-radius:8px;padding:16px;'
            'margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.08)">'
            '<p style="font-weight:bold;font-size:15px;margin:0 0 10px;color:#0f172a">'
            '🤖 Resumen del día</p>'
            f'{summaries_content}'
            '</div>'
        )

    section = render_section(fecha_str, noticias, is_open=True, tips=tips)
    return (
        '<!DOCTYPE html><html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>@media(max-width:600px){body{padding:12px!important}.wrap{padding:0 4px!important}}</style>'
        '</head>'
        '<body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0;font-size:14px">'
        '<div class="wrap" style="max-width:600px;width:100%;margin:auto;box-sizing:border-box">'
        '<h2 style="color:#0f172a;margin-bottom:16px">🗞 News Personales</h2>'
        f'{ai_block}'
        f'{section}'
        f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">'
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>'
        '</div></body></html>'
    )

def build_plain_text(fecha_str: str, noticias: dict, tips: list, resumenes: dict = None) -> str:
    resumenes = resumenes or {}
    lines = [f"News Personales — {fecha_str}", "=" * 44, ""]

    if any(resumenes.get(t) for t in noticias):
        lines += ["RESUMEN DEL DÍA", "-" * 20, ""]
        for topic in noticias:
            resumen = resumenes.get(topic, "")
            if resumen:
                lines.append(f"{topic}: {resumen}")
                lines.append("")
        lines.append("")

    for topic, items in noticias.items():
        if not items:
            continue
        lines.append(topic)
        for it in items:
            pub = f" ({it['pub']})" if it["pub"] else ""
            lines.append(f"  * {it['title']}{pub}")
            lines.append(f"    {it['link']}")
        lines.append("")
    for titulo, tip in tips:
        lines.append(titulo)
        lines.append(f"  {tip['nombre']}: {tip['descripcion']}")
        lines.append("")
    lines.append(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    return "\n".join(lines)

# ─── HISTORIAL ────────────────────────────────────────────────────────────────

HISTORY_SHELL = (
    '<!DOCTYPE html><html><head>'
    '<meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    '<title>News Personales</title>'
    '<style>'
    'body{font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:24px;margin:0;font-size:14px}'
    '.wrap{max-width:720px;width:100%;margin:auto;box-sizing:border-box}'
    'h1{color:#0f172a;margin-bottom:20px}'
    'a{color:#3b82f6;text-decoration:none} a:hover{text-decoration:underline}'
    'ul{line-height:1.9}'
    'details>summary{list-style:none} details>summary::-webkit-details-marker{display:none}'
    '@media(max-width:600px){body{padding:12px}.wrap{padding:0 4px}}'
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
        html.replace(MARKER, MARKER + "\n" + section, 1),
        encoding="utf-8"
    )

# ─── ENVÍO ────────────────────────────────────────────────────────────────────

def send_email(html_body: str, plain_body: str, fecha_str: str) -> None:
    mensaje = Mail(
        from_email=Email("noreply@frmendez.com", "News Personales"),
        to_emails=DESTINATARIO,
        subject=f"[News Personales] {fecha_str}",
        html_content=html_body,
        plain_text_content=plain_body,
    )
    mensaje.header = Header("List-Unsubscribe", "<mailto:unsubscribe@frmendez.com>")
    mensaje.header = Header("Precedence", "bulk")
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    sg.send(mensaje)

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

    print("  Generando resúmenes con IA...")
    resumenes = {topic: get_ai_summary(topic, items) for topic, items in noticias.items()}

    tips = [
        ("💡 DAX del día",    get_tip(DAX_FILE)),
        ("🐍 Python del día", get_tip(PYTHON_FILE)),
        ("🗄️ SQL del día",    get_tip(SQL_FILE)),
    ]
    for titulo, tip in tips:
        print(f"  {titulo}: {tip['nombre']}")

    update_history(fecha_str, noticias, tips)
    send_email(
        build_email(fecha_str, noticias, tips, resumenes),
        build_plain_text(fecha_str, noticias, tips, resumenes),
        fecha_str,
    )

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"news_history_{date.today().isoformat()}.html"
    shutil.copy2(HISTORY_FILE, backup_file)

    total = sum(len(v) for v in noticias.values())
    print(f"\n  ✓ {total} noticias enviadas a {DESTINATARIO}")
    print(f"  ✓ Historial actualizado: news_history.html")
    print(f"  ✓ Backup guardado: {backup_file.name}")
    print(f"{'─'*50}\n")


if __name__ == "__main__":
    main()
