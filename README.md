# News Personales — Daily Email Digest

Envía un email diario con las noticias del día según tus intereses, obtenidas desde feeds RSS. Incluye un tip rotativo de DAX, Python y SQL. Acumula el historial en `news_history.html` con el día más reciente primero.

## Cómo funciona

1. Lee todos los archivos `profiles/*.json` (excluye `*.example.json`); por cada perfil ejecuta los pasos siguientes
2. Obtiene las últimas noticias de cada feed del perfil (timeout 10 s; si un feed falla, se omite y continúa), ordenadas de más reciente a más antigua usando `published_parsed` o `updated_parsed`; noticias sin fecha van al final
3. Llama a Groq (llama-3.3-70b-versatile) para generar un resumen en español de 2-3 oraciones por temática; si la llamada falla, continúa sin resumen
4. Selecciona un tip del día de `dax_formulas.json`, `python_tips.json` y `sql_tips.json` (compartido entre todos los perfiles)
5. Genera un email multipart (HTML responsive + texto plano) personalizado con el nombre del perfil, bloque "🤖 Resumen del día" y la lista de noticias con links
6. Guarda el día en `news_history_{perfil}.html` (secciones colapsables, el más reciente siempre primero; sin resúmenes de IA)
7. Envía el email vía SendGrid desde `noreply@frmendez.com` al email del perfil
8. Copia el historial a `backups/news_history_{perfil}_YYYY-MM-DD.html` (la carpeta se crea automáticamente; excluida de git)

## Agregar un nuevo usuario

Crear un archivo `profiles/nombre.json` en el servidor (nunca en el repo — está en `.gitignore`):

```json
{
    "email": "usuario@gmail.com",
    "name": "Nombre",
    "interests": {
        "Tema 1": [
            "https://feed1.rss",
            "https://feed2.rss"
        ]
    }
}
```

Ver `profiles/fabian.example.json` como referencia de estructura. El script detecta automáticamente el nuevo archivo en la próxima ejecución.

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
| `GROQ_API_KEY` | API key de Groq para resúmenes de IA (opcional; si no está, se omiten los resúmenes) |
| `MAX_ITEMS` | Noticias máximas por feed (por defecto `5`) |

> El email de cada destinatario vive en su archivo `profiles/nombre.json`, no en `.env`.

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
| `groq` | Resúmenes de IA por temática (Llama 3.3 70B) |
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
