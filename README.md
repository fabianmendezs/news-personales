# News Personales — Daily Email Digest

Envía un email diario con las noticias del día según tus intereses, obtenidas desde feeds RSS confiables. Acumula el historial de noticias en un archivo HTML local consultable por fecha.

## Cómo funciona

1. Lee `interests.json` con los temas de interés y sus feeds RSS
2. Obtiene las últimas noticias de cada feed
3. Genera un email HTML con los títulos y links del día
4. Guarda el día en `news_history.html` (secciones colapsables por fecha)
5. Envía el email vía Gmail SMTP

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
| `python-dotenv` | Variables de entorno desde `.env` |

## Licencia

MIT
