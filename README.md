# News Personales — Daily Email Digest

Envía un email diario con las noticias del día según tus intereses, obtenidas desde feeds RSS. Incluye resúmenes generados con Groq, tips rotativos de DAX/Python/SQL y, para perfiles habilitados, una sección especial con una “Herramienta del día”.

## Qué hace el proyecto

- Recorre los perfiles definidos en `profiles/*.json`.
- Obtiene noticias desde feeds RSS/Atom.
- Genera un resumen por temática con Groq.
- Añade una sección de “Herramienta del día” usando Groq, con historial persistente para no repetir herramientas.
- Envía un email HTML y texto plano con el resumen diario, las noticias y los tips.
- Guarda un historial web por perfil y crea backups del mismo.

## Flujo de ejecución

1. Lee todos los archivos `profiles/*.json` (excluye `*.example.json`).
2. Por cada perfil, obtiene las últimas noticias de cada feed (timeout de 10 s; los feeds que fallen se omiten y el script continúa).
3. Genera resúmenes en español por temática con Groq. Si falla la llamada, el resumen se deja vacío y el script sigue.
4. Genera una “Herramienta del día” para los perfiles donde `tips` sea `true` o no exista, usando Groq y un historial local en `historial_herramientas.json`.
5. Selecciona un tip del día de `dax_formulas.json`, `python_tips.json` y `sql_tips.json` (compartido entre todos los perfiles).
6. Genera un email multipart (HTML responsive + texto plano) personalizado con el nombre del perfil, el bloque de resúmenes, la herramienta del día y la lista de noticias con links.
7. Guarda el día en `news_history_{perfil}.html` (secciones colapsables, el más reciente siempre primero) sin incluir la herramienta del día.
8. Envía el email vía SendGrid desde `noreply@frmendez.com` al destinatario del perfil.
9. Copia el historial a `backups/news_history_{perfil}_YYYY-MM-DD.html`.

## Archivos importantes

- `news_diarias.py`: lógica principal del proceso.
- `profiles/*.json`: definiciones de perfiles y sus intereses.
- `dax_formulas.json`, `python_tips.json`, `sql_tips.json`: tips rotativos.
- `historial_herramientas.json`: historial local de herramientas ya mostradas. Se crea automáticamente y se ignora por git.
- `news_history_{perfil}.html`: historial web por perfil.
- `backups/`: copias de seguridad del historial.

## Agregar un nuevo usuario

Crear un archivo `profiles/nombre.json` en el servidor (nunca en el repo — está en `.gitignore`):

```json
{
    "email": "usuario@gmail.com",
    "name": "Nombre",
    "tips": true,
    "interests": {
        "Tema 1": [
            "https://feed1.rss",
            "https://feed2.rss"
        ]
    }
}
```

- `tips` es opcional. Si falta, se asume `true`.
- Si `tips` es `false`, no se muestran los tips ni la sección de “Herramienta del día”.

Ver `profiles/fabian.example.json` como referencia de estructura. El script detecta automáticamente el nuevo archivo en la próxima ejecución.

## Instalación

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp /dev/null .env
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy NUL .env
```

Luego edita `.env` con tus credenciales.

## Variables de entorno (`.env`)

| Variable | Descripción |
|----------|-------------|
| `SENDGRID_API_KEY` | API key de SendGrid (Restricted Access → Mail Send → Full Access) |
| `GROQ_API_KEY` | API key de Groq para resúmenes de IA y herramienta del día (opcional; si no está, esas secciones se omiten) |
| `MAX_ITEMS` | Noticias máximas por feed (por defecto `5`) |

> El email de cada destinatario vive en su archivo `profiles/nombre.json`, no en `.env`.
>
> El remitente está fijado en el código como `noreply@frmendez.com` (nombre visible: "News Personales"). Para cambiarlo, editar `send_email` en `news_diarias.py`.
>
> **Seguridad:** usar siempre **Restricted Access** en SendGrid. Si la key se compromete, el atacante solo puede enviar emails pero no acceder a configuración ni billing.

## Ejecución

```bash
source venv/bin/activate
python news_diarias.py
```

En Windows:

```bash
venv\Scripts\activate
python news_diarias.py
```

## Automatización diaria

### Windows

1. Abrir **Programador de tareas**.
2. Crear una tarea con acción: ejecutar `ejecutar_news.bat`.
3. Configurar el disparador: diariamente a las 08:00.

### Linux / cron

```bash
crontab -e
```

Ejemplo diario a las 08:00:

```cron
0 8 * * * /home/usuario/news-personales/venv/bin/python /home/usuario/news-personales/news_diarias.py
```

## Dependencias

| Librería | Uso |
|----------|-----|
| `feedparser` | Lectura de feeds RSS/Atom |
| `groq` | Resúmenes de IA y generación de la herramienta del día |
| `sendgrid` | Envío de emails vía API |
| `python-dotenv` | Variables de entorno desde `.env` |

## Deliverability (anti-spam)

El código ya incluye:
- Email multipart: HTML + texto plano en el mismo envío.
- Asunto sin emoji al inicio (`[News Personales] fecha`).
- Header `List-Unsubscribe` apuntando a `unsubscribe@frmendez.com`.
- Header `Precedence: bulk`.

Para que estos cambios sean suficientes, el dominio `frmendez.com` debe tener los registros DNS activos y verificados en **SendGrid → Settings → Sender Authentication**:

| Registro | Tipo | Descripción |
|----------|------|-------------|
| SPF | TXT | Autoriza a SendGrid a enviar desde el dominio |
| DKIM | CNAME (×2) | Firma criptográfica de cada email |
| DMARC | TXT en `_dmarc.frmendez.com` | Política de rechazo para emails no firmados |

Sin los tres en verde en SendGrid, los cambios de código solos no son suficientes.

## Archivos ignorados por git

El proyecto ignora archivos locales y generados automáticamente, como:

- `historial_herramientas.json`
- `news_history*.html`
- `logs/`
- `backups/`
- `.env`

## Licencia

MIT
