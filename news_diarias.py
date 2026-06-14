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

BASE_DIR     = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
DAX_FILE     = BASE_DIR / "dax_formulas.json"
PYTHON_FILE  = BASE_DIR / "python_tips.json"
SQL_FILE     = BASE_DIR / "sql_tips.json"
LOGS_DIR     = BASE_DIR / "logs"
HISTORIAL_HERRAMIENTAS_FILE = BASE_DIR / "historial_herramientas.json"
MAX_ITEMS    = int(os.getenv("MAX_ITEMS", 5))

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

def load_tool_history(history_file: Path) -> list[str]:
    if not history_file.exists():
        history_file.write_text("[]", encoding="utf-8")
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
    except Exception:
        history_file.write_text("[]", encoding="utf-8")
        return []
    if isinstance(data, list):
        return [str(item) for item in data if isinstance(item, str)]
    return []


def save_tool_history(history_file: Path, tool_name: str) -> None:
    if not tool_name:
        return
    history = load_tool_history(history_file)
    if tool_name not in history:
        history.append(tool_name)
        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_tool_of_the_day(history_file: Path) -> tuple[str | None, str | None]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None, None
    try:
        from groq import Groq
        history = load_tool_history(history_file)
        shown_tools = ", ".join(history) if history else "ninguna"
        prompt = (
            f"Estas son las herramientas ya mostradas previamente: {shown_tools}\n\n"
            f"Elige UNA herramienta, tecnología, plataforma o concepto del mundo del análisis de datos, "
            f"ciencia de datos o inteligencia artificial que NO esté en esa lista. "
            f"Debe pertenecer a una categoría diferente a las últimas 3 herramientas mostradas. "
            f"Las categorías posibles son: lenguajes de programación, plataformas cloud, herramientas de visualización, "
            f"bases de datos, frameworks de ML/IA, herramientas de automatización, plataformas de BI, "
            f"conceptos estadísticos, herramientas de ingeniería de datos, modelos de IA, entornos de desarrollo. "
            f"Devuelve la respuesta con este formato exacto:\n"
            f"Nombre: <nombre de la herramienta>\n"
            f"Qué es: <2 a 3 oraciones>\n"
            f"Cómo se usa: <2 a 3 oraciones prácticas>\n"
            f"Caso de uso: <2 a 3 oraciones concretas>\n\n"
            f"Escribe todo en español, sin listas ni bullets, con un tono claro y práctico."
        )
        client = Groq(api_key=api_key)
        for _ in range(2):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400,
            )
            content = response.choices[0].message.content.strip()
            if not content:
                continue
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            name = None
            for line in lines:
                if line.lower().startswith("nombre:"):
                    name = line.split(":", 1)[1].strip()
                    break
            if not name and lines:
                name = lines[0].replace("Nombre:", "", 1).strip()
            if name and name not in history:
                save_tool_history(history_file, name)
                return name, content
        return None, None
    except Exception as ex:
        print(f"  ⚠ Groq tool error: {ex}")
        return None, None


def get_ai_summary(topic: str, items: list) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not items:
        return ""
    try:
        from groq import Groq
        titulos = "\n".join(f"- {it['title']}" for it in items)
        prompt = (
            f"Estos títulos son los temas del día sobre '{topic}':\n{titulos}\n\n"
            f"Actúa como un analista experto en {topic}. Explica el contexto, la relevancia y el fondo "
            f"de estos temas usando tu conocimiento propio para enriquecer el análisis más allá de los títulos. "
            f"Escribe un único párrafo de 4 a 5 oraciones en español, sin listas ni bullets, en tono analítico e informativo."
        )
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
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

def render_tool_block(tool_name: str | None, content: str | None) -> str:
    if not tool_name or not content:
        return ""
    content_html = content.replace("\n", "<br>")
    for label in ("Qué es:", "Cómo se usa:", "Caso de uso:"):
        content_html = content_html.replace(label, f"<strong>{label}</strong>")
    return (
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
        'padding:14px 16px;margin:12px 0 10px">'
        '<p style="font-weight:bold;margin:0 0 8px;color:#0f172a">🛠️ Herramienta del día</p>'
        f'<p style="font-weight:600;margin:0 0 8px;color:#2563eb">{tool_name}</p>'
        f'<div style="margin:0;color:#334155;font-size:13px;line-height:1.6">{content_html}</div>'
        '</div>'
    )


def render_section(fecha_str: str, noticias: dict, is_open: bool = False,
                   tips: list = None, tool_block: str = "") -> str:
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
    if tool_block:
        body += tool_block
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

def build_email(fecha_str: str, noticias: dict, tips: list, resumenes: dict = None, name: str = "",
                tool_name: str = "", tool_content: str = "") -> str:
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

    section = render_section(
        fecha_str,
        noticias,
        is_open=True,
        tips=tips,
        tool_block=render_tool_block(tool_name, tool_content),
    )
    return (
        '<!DOCTYPE html><html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>@media(max-width:600px){body{padding:12px!important}.wrap{padding:0 4px!important}}</style>'
        '</head>'
        '<body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0;font-size:14px">'
        '<div class="wrap" style="max-width:600px;width:100%;margin:auto;box-sizing:border-box">'
        f'<h2 style="color:#0f172a;margin-bottom:16px">🗞 News Personales — {name}</h2>'
        f'{ai_block}'
        f'{section}'
        f'<p style="font-size:11px;color:#94a3b8;margin-top:16px">'
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>'
        '</div></body></html>'
    )

def build_plain_text(fecha_str: str, noticias: dict, tips: list, resumenes: dict = None, name: str = "",
                     tool_name: str = "", tool_content: str = "") -> str:
    resumenes = resumenes or {}
    lines = [f"News Personales — {name} | {fecha_str}", "=" * 44, ""]

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
    if tool_name and tool_content:
        lines += ["HERRAMIENTA DEL DÍA", "------------------", "", tool_name, "", tool_content, ""]

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

def update_history(fecha_str: str, noticias: dict, tips: list, history_file: Path) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    if not history_file.exists():
        history_file.write_text(HISTORY_SHELL, encoding="utf-8")

    html = history_file.read_text(encoding="utf-8")
    if f"📅 {fecha_str}" in html:
        return  # ya guardado hoy

    section = render_section(fecha_str, noticias, tips=tips)
    history_file.write_text(
        html.replace(MARKER, MARKER + "\n" + section, 1),
        encoding="utf-8"
    )

# ─── ENVÍO ────────────────────────────────────────────────────────────────────

def send_email(html_body: str, plain_body: str, fecha_str: str, to_email: str | list) -> None:
    mensaje = Mail(
        from_email=Email("noreply@frmendez.com", "News Personales"),
        to_emails=to_email,
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
    fecha_str = fecha_es()
    print(f"\n{'─'*50}")
    print(f"  News Personales — {fecha_str}")
    print(f"{'─'*50}")

    tips = [
        ("💡 DAX del día",    get_tip(DAX_FILE)),
        ("🐍 Python del día", get_tip(PYTHON_FILE)),
        ("🗄️ SQL del día",    get_tip(SQL_FILE)),
    ]
    for titulo, tip in tips:
        print(f"  {titulo}: {tip['nombre']}")

    profiles = sorted(
        p for p in PROFILES_DIR.glob("*.json")
        if not p.name.endswith(".example.json")
    )
    if not profiles:
        print("  ⚠ No se encontraron perfiles en profiles/")
        return

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    for profile_path in profiles:
        with open(profile_path, encoding="utf-8") as f:
            profile = json.load(f)

        name         = profile["name"]
        to_email     = profile["email"]
        interests    = profile["interests"]
        profile_id   = profile_path.stem
        history_file = BASE_DIR / f"news_history_{profile_id}.html"
        profile_tips = tips if profile.get("tips", True) else []
        tool_name, tool_content = "", ""
        if profile_tips and not tool_name and not tool_content:
            tool_name, tool_content = get_tool_of_the_day(HISTORIAL_HERRAMIENTAS_FILE)

        print(f"\n  [{profile_id}] {name} → {to_email}")

        noticias = {}
        for topic, feeds in interests.items():
            items = fetch_interest(feeds, MAX_ITEMS)
            noticias[topic] = items
            print(f"    {topic}: {len(items)} noticias")

        print(f"    Generando resúmenes con IA...")
        resumenes = {topic: get_ai_summary(topic, items) for topic, items in noticias.items()}

        update_history(fecha_str, noticias, profile_tips, history_file)
        send_email(
            build_email(fecha_str, noticias, profile_tips, resumenes, name, tool_name, tool_content),
            build_plain_text(fecha_str, noticias, profile_tips, resumenes, name, tool_name, tool_content),
            fecha_str,
            to_email,
        )

        backup_file = backup_dir / f"news_history_{profile_id}_{date.today().isoformat()}.html"
        shutil.copy2(history_file, backup_file)

        total = sum(len(v) for v in noticias.values())
        print(f"    ✓ {total} noticias enviadas a {to_email}")
        print(f"    ✓ Historial: news_history_{profile_id}.html")
        print(f"    ✓ Backup: {backup_file.name}")

    print(f"\n{'─'*50}\n")


if __name__ == "__main__":
    main()
