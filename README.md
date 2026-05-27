# News Personales — Daily Email Digest

Envía un email diario con las noticias del día según tus intereses, obtenidas desde feeds RSS. Incluye un tip rotativo de DAX, Python y SQL. Acumula el historial en `news_history.html` con el día más reciente primero.

## Cómo funciona

1. Lee `interests.json` con los temas de interés y sus feeds RSS
2. Obtiene las últimas noticias de cada feed (timeout 10 s; si un feed falla, se omite y continúa)
3. Selecciona un tip del día de `dax_formulas.json`, `python_tips.json` y `sql_tips.json`
4. Genera un email multipart (HTML responsive + texto plano) con títulos, links y tips del día
5. Guarda el día en `news_history.html` (secciones colapsables, el más reciente siempre primero)
6. Envía el email vía SendGrid desde `noreply@frmendez.com` con headers de deliverability
7. Copia el historial a `backups/news_history_YYYY-MM-DD.html` (la carpeta se crea automáticamente; excluida de git)

## Agregar nuevos intereses

Editar `interests.json` agregando el tema y sus feeds RSS:

```json
{
  "Final Fantasy XIV": [
    "https://www.reddit.com/r/ffxiv.rss",
    "https://na.finalfantasyxiv.com/lodestone/topics/rss/"
  ],
  "Python": [
    "https://www.reddit.com/r/Python.rss",
    "https://realpython.com/atom.xml"
  ]
}
```

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Editar .env con tus credenciales
```

## Variables de entorno (`.env`)

| Variable | Descripción |
|----------|-------------|
| `SENDGRID_API_KEY` | API key de SendGrid (Restricted Access → Mail Send → Full Access) |
| `DESTINATARIO` | Email destinatario del digest diario |
| `MAX_ITEMS` | Noticias máximas por feed (por defecto `5`) |

> El remitente está fijado en el código como `noreply@frmendez.com` (nombre visible: "News Personales"). Para cambiarlo, editar `send_email` en `news_diarias.py`.

> **Seguridad:** Usar siempre **Restricted Access** en SendGrid. Si la key se compromete, el atacante solo puede enviar emails pero no acceder a configuración ni billing.

## Ejecución

```bash
venv\Scripts\activate
python news_diarias.py
```

## Automatización diaria (Windows)

1. Abrir **Programador de tareas**
2. Crear tarea → acción: ejecutar `ejecutar_news.bat`
3. Gatillo: diariamente a las 08:00

## Dependencias

| Librería | Uso |
|----------|-----|
| `feedparser` | Lectura de feeds RSS/Atom |
| `sendgrid` | Envío de emails vía API |
| `python-dotenv` | Variables de entorno desde `.env` |

## Deliverability (anti-spam)

El código ya incluye:
- Email multipart: HTML + texto plano en el mismo envío
- Asunto sin emoji al inicio (`[News Personales] fecha`)
- Header `List-Unsubscribe` apuntando a `unsubscribe@frmendez.com`
- Header `Precedence: bulk`

Para que estos cambios sean suficientes, el dominio `frmendez.com` debe tener los registros DNS activos y verificados en **SendGrid → Settings → Sender Authentication**:

| Registro | Tipo | Descripción |
|----------|------|-------------|
| SPF | TXT | Autoriza a SendGrid a enviar desde el dominio |
| DKIM | CNAME (×2) | Firma criptográfica de cada email |
| DMARC | TXT en `_dmarc.frmendez.com` | Política de rechazo para emails no firmados |

Sin los tres en verde en SendGrid, los cambios de código solos no son suficientes.

## Licencia

MIT
