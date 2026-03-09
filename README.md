# RSS News Digest Bot 🤖📰

> **Transforma tus feeds RSS en resúmenes inteligentes entregados automáticamente en Telegram**

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-green)
![Status: Beta](https://img.shields.io/badge/Status-Beta-yellow)

## 🎯 ¿Qué es?

Un bot automatizado que:

1. **Lee** tus feeds RSS desde TT-RSS (~100 artículos/día)
2. **Agrupa** artículos por categoría
3. **Resumen** usando Google Gemini IA
4. **Envía** a Telegram con botones interactivos
5. **Guarda** artículos en Wallabag para leer después

### Problema que resuelve

> Tienes +1400 artículos sin leer en TT-RSS. Es imposible leerlos todos manualmente.

**Solución**: El bot lee automáticamente y envía solo resúmenes inteligentes a tu Telegram. Tú decides cuáles leer completo.

---

## ✨ Características Principales

### 📚 Múltiples Fuentes
- **TT-RSS**: Tu instancia personal de Tiny Tiny RSS
- **Extensible**: Fácil agregar nuevas fuentes (Feedly, Inoreader, etc.)

### 🤖 Resúmenes Inteligentes
- Generados con **Google Gemini** (IA gratis)
- Agrupados por **categoría**
- Llamada única al LLM (eficiente)
- Referencias `[ID]` para rastrear artículos

### 💬 Telegram Interactivo
- **Dos modos**: Chat 1:1 o Supergrupo con tópicos
- **Botones**: Ver artículo, Marcar leído, Guardar a Wallabag
- **Comandos**: `/url`, `/guardar`, `/ayuda`
- **Rate limiting**: Evita bloqueos de Telegram

### 📚 Wallabag Integration
- Guarda artículos con un click
- Tags automáticos por categoría
- OAuth seguro

### ⚙️ Automatización
- **Systemd**: Timer automático (recomendado)
- **Cron**: Ejecución programada
- **Docker**: Fácil deployment
- **CLI**: Control manual

### 🔐 Seguridad & Privacidad
- Credenciales en variables de entorno
- Logs sin información sensible
- Usuario non-root en Docker
- Código abierto (GPL v3)

---

## 🚀 Instalación Rápida

### 1. Requisitos Previos

```bash
# Linux/Mac
- Python 3.14+
- TT-RSS instancia activa
- Bot de Telegram (crea uno con @BotFather)
- API Key de Google AI Studio (gratis)
- (Opcional) Instancia de Wallabag
```

### 2. Clonar y Setup

```bash
# Clonar el repositorio
git clone https://github.com/LuisDelgado-LD/rss-resumen-bot.git
cd rss-resumen-bot

# Ejecutar setup (crea venv, instala dependencias)
./setup.sh

# Editar configuración
nano .env

# Verificar que todo funciona
source venv/bin/activate
python -m src.cli validate
```

### 3. Configuración (.env)

Copia `.env.example` a `.env` y completa con tus valores:

```env
# TT-RSS
TTRSS_URL=https://tu-instancia-ttrss.com
TTRSS_USER=tu_usuario
TTRSS_PASSWORD=tu_password

# Google Gemini
GOOGLE_API_KEY=tu_api_key
GOOGLE_MODEL=gemini-1.5-flash

# Telegram Bot
TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
TELEGRAM_MODE=chat  # o "supergroup"

# Wallabag (opcional)
WALLABAG_URL=https://tu-instancia-wallabag.com
WALLABAG_CLIENT_ID=...
WALLABAG_CLIENT_SECRET=...
WALLABAG_USERNAME=...
WALLABAG_PASSWORD=...

# Otras opciones
ARTICLES_MAX_AGE_HOURS=24
TELEGRAM_MESSAGE_DELAY=1.5
SCRAPING_ENABLED=true
```

Ver `.env.example` para **todas las opciones**.

---

## 💻 Uso

### Manual - Ejecutar Digest

```bash
source venv/bin/activate

# Últimas 24 horas (default)
python -m src.cli digest

# Personalizadas
python -m src.cli digest --hours 48
python -m src.cli digest --hours 168  # Una semana

# Sin enviar a Telegram (dry-run)
python -m src.cli digest --dry-run

# Ver estadísticas
python -m src.cli stats

# Validar configuración
python -m src.cli validate
```

### Automático - Systemd (Recomendado)

```bash
# Setup
sudo cp deployment/rss-digest-bot.service /etc/systemd/system/
sudo cp deployment/rss-digest-bot.timer /etc/systemd/system/

# Editar rutas (reemplaza /path/to/bot)
sudo nano /etc/systemd/system/rss-digest-bot.service

# Habilitar y ejecutar
sudo systemctl daemon-reload
sudo systemctl enable rss-digest-bot.timer
sudo systemctl start rss-digest-bot.timer

# Verificar estado
sudo systemctl status rss-digest-bot.timer
sudo systemctl list-timers

# Ver logs
sudo journalctl -u rss-digest-bot.service -f
```

Ver [deployment/README_SYSTEMD.md](deployment/README_SYSTEMD.md) para detalles.

### Automático - Cron

```bash
crontab -e

# Agregar línea (8:00 AM cada día)
0 8 * * * cd /path/to/rss-resumen-bot && source venv/bin/activate && python -m src.cli digest >> /var/log/rss-digest-bot/cron.log 2>&1
```

Ver [deployment/README_CRON.md](deployment/README_CRON.md) para detalles.

### Bot Interactivo (Testing)

```bash
source venv/bin/activate
python tests/integration/test_etapa6_handlers.py

# En Telegram:
# /url [ID]            → Obtener URL de un artículo
# /guardar [ID...]     → Guardar artículos en Wallabag
# /ayuda               → Ver comandos disponibles
```

---

## 🏗️ Arquitectura

```
TT-RSS (feeds)
    ↓
[Article Service] ← Web scraping (trafilatura)
    ↓
[Google Gemini] ← LLM call (llamada única)
    ↓
[Telegram Bot] ← Envío con rate limiting
    ↓
[Wallabag] + TT-RSS (marcar leídos)
```

### Componentes Principales

| Módulo | Función |
|--------|---------|
| `orchestrator.py` | Anema el flujo completo |
| `cli.py` | Interfaz de línea de comandos |
| `ttrss_client.py` | Comunicación con TT-RSS |
| `llm_client.py` | Google Gemini para resúmenes |
| `telegram_bot.py` | Handlers interactivos |
| `article_service.py` | Prep de artículos |
| `scraper.py` | Web scraping paralelo |
| `telegram_dispatcher.py` | Envío a Telegram |
| `wallabag_client.py` | Integración Wallabag |
| `state_manager.py` | Persistencia de estado |

Ver [Architecture.md](Architecture.md) para detalles técnicos.

---

## 📖 Documentación

### Para Usuarios
- **[README.md](README.md)** ← Tú estás aquí (guía de instalación y uso)
- **[.env.example](.env.example)** - Todas las variables de configuración
- **[deployment/README_SYSTEMD.md](deployment/README_SYSTEMD.md)** - Deployment automático
- **[deployment/README_CRON.md](deployment/README_CRON.md)** - Alternativa con cron

### Para Desarrolladores
- **[Architecture.md](Architecture.md)** - Arquitectura técnica
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guía de contribución


---

## 🐛 Solución de Problemas

### "No hay URLs persistidas. Ejecuta el digest primero"

El bot necesita persistencia para resolver IDs. Ejecuta digest al menos una vez:

```bash
python -m src.cli digest
```

### Error de conexión a TT-RSS

Verifica variables de entorno:

```bash
python -m src.cli validate
# Mostrará qué falta o está mal
```

### Telegram retorna error 429 (Too Many Requests)

Aumenta los delays en `.env`:

```env
TELEGRAM_MESSAGE_DELAY=2.0      # De 1.5 a 2.0
TELEGRAM_CATEGORY_DELAY=3.0      # De 2.0 a 3.0
```

### Logs oscuros, no entiendo qué pasa

Aumenta nivel de detalle:

```env
LOG_LEVEL=DEBUG
```

Luego revisa logs en `tests/logs/` o `journalctl`.

### Google Gemini devuelve JSON inválido

Reduce `MAX_SUMMARY_TOKENS` en `.env`:

```env
MAX_SUMMARY_TOKENS=1500  # En lugar de 2000
```

---

## 📊 Características Avanzadas

### Prompt Custom

Edita prompts en `utils/prompts/`:

```bash
utils/prompts/
├── all_categories_summary.txt   # Prompt genérico
├── category_summary.txt         # Por categoría
└── README.md
```

### Scraping Avanzado

Controla scraping en `.env`:

```env
SCRAPING_ENABLED=true
SCRAPING_TIMEOUT_SECONDS=5
SCRAPING_DELAY_SAME_DOMAIN_SECONDS=2
SCRAPING_MAX_PARALLEL_DOMAINS=10
SCRAPING_MIN_WORDS=100
SCRAPING_CACHE_ENABLED=true
SCRAPING_CACHE_RETRY_AFTER_DAYS=7
```

### Rate Limiting

Ajusta según necesidad:

```env
TELEGRAM_MESSAGE_DELAY=1.5
TELEGRAM_CATEGORY_DELAY=2.0
API_RETRY_ATTEMPTS=3
API_RETRY_DELAY_SECONDS=5
```

---

## 🤝 Contribuir

¿Quieres agregar features o reportar bugs?

1. Lee [CONTRIBUTING.md](CONTRIBUTING.md)
2. Fork el repo
3. Crea una branch: `git checkout -b feature/tu-feature`
4. Commit: `git commit -am 'Agrega tu-feature'`
5. Push: `git push origin feature/tu-feature`
6. Abre un Pull Request

---

## 📜 Licencia

Este proyecto está bajo la **Licencia GPL v3**. Ver [LICENSE](LICENSE) para detalles.

**Significa**: Puedes usar, modificar y distribuir libremente, pero debes mantener la licencia GPL. 🎉

---

## 🙏 Agradecimientos

- **TT-RSS**: Por existir y tener una API excelente
- **Google Gemini**: Por los resúmenes inteligentes (gratis)
- **python-telegram-bot**: Librería maravillosa
- **Wallabag**: Para "leer para después"

---

## 📞 Contacto y Soporte

- **Issues**: [GitHub Issues](https://github.com/LuisDelgado-LD/rss-resumen-bot/issues)

---


*Última actualización: 8 de marzo de 2026*
