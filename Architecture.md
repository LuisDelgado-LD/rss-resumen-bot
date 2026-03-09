# Arquitectura Técnica

## Visión General

Sistema modular que automatiza la recopilación de artículos RSS, genera resúmenes con IA y proporciona una interfaz interactiva en Telegram.

## Estructura

```
src/
├── orchestrator.py       # Orquestador principal
├── cli.py                # Interfaz de línea de comandos
├── config/settings.py    # Configuración
├── clients/
│   ├── ttrss_client.py   # TT-RSS API
│   ├── llm_client.py     # Google Gemini
│   ├── telegram_client.py
│   └── wallabag_client.py
├── bot/telegram_bot.py   # Manejadores del bot
├── services/
│   ├── article_service.py
│   ├── scraper.py
│   ├── prompt_manager.py
│   └── telegram_dispatcher.py
├── db/state_manager.py   # Persistencia
└── utils/                # Utilidades
```

## Flujo Principal

1. Orquestador (CLI o cron) inicia el proceso
2. TT-RSS: obtiene artículos no leídos
3. Article Service: filtra y ordena
4. Scraper: extrae contenido web
5. LLM (Gemini): genera resumen único
6. Telegram: envía con referencias `[ID]`
7. Wallabag: guarda si el usuario lo solicita

## Componentes Principales

- **CLI/Orchestrator**: Inicia el flujo de actualización
- **TT-RSS Client**: Acceso a feed reader
- **LLM Client**: Google Gemini para resúmenes
- **Telegram Bot**: Interfaz de usuario interactiva con `/url`, `/guardar`, `/ayuda`
- **Wallabag Client**: Guardado de artículos
- **Scraper**: Extracción de contenido web
- **State Manager**: Persistencia de estado en JSON

## Seguridad

- Todas las credenciales en variables de entorno (`.env`)
- Usuario no-root en Docker
- Información sensible filtrada en logs
- `.env` nunca en Git

## Tecnologías

- **Python 3.14+**: Lenguaje principal
- **python-telegram-bot 21.0.1**: API Telegram
- **google-generativeai 0.8.3**: Google Gemini
- **requests 2.31.0**: HTTP client
- **Click**: CLI framework
- **Docker**: Containerización

## Modos de Ejecución

- **Local**: `python -m src.cli digest`
- **Systemd** (recomendado): Ver [deployment/README_SYSTEMD.md](deployment/README_SYSTEMD.md)
- **Cron**: Ver [deployment/README_CRON.md](deployment/README_CRON.md)
- **Docker**: `docker-compose up`

## Características

- **Scraping inteligente**: Paralelización por dominio, rate limiting, caché de URLs fallidas
- **LLM eficiente**: Llamada única con respuesta JSON, referencias `[ID]`, rate limiting (15 RPM)
- **Telegram robusto**: Rate limiting, manejo automático, Markdown V2 seguro

## Documentación Adicional

- [README.md](README.md): Guía de usuario e instalación
- [CONTRIBUTING.md](CONTRIBUTING.md): Cómo contribuir
- [deployment/README_SYSTEMD.md](deployment/README_SYSTEMD.md): Deployment con systemd
- [deployment/README_CRON.md](deployment/README_CRON.md): Deployment con cron