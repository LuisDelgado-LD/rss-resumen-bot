# Guía de Contribución

¡Gracias por tu interés en contribuir a RSS News Digest Bot! 🎉

## 📋 Antes de Empezar

1. Lee [README.md](README.md) para entender qué hace el proyecto
2. Revisa [Architecture.md](Architecture.md) para arquitectura técnica

## 🐛 Reportar Bugs

Si encuentras un bug:

1. **Verifica que no exista**: Busca en [Issues](https://github.com/LuisDelgado-LD/rss-resumen-bot/issues)
2. **Crea un Issue** con:
   - Título claro (ej: "Error al conectar a TT-RSS con contraseñas especiales")
   - Descripción del problema
   - Pasos para reproducir
   - Logs relevantes (sin credenciales!)
   - Tu configuración (versión Python, SO, etc.)

### Template de Bug Report

```markdown
## Descripción
[Describe el problema aquí]

## Pasos para Reproducir
1. ...
2. ...
3. ...

## Comportamiento Esperado
[Qué debería pasar]

## Comportamiento Actual
[Qué pasa realmente]

## Logs/Errores
```
[Pega logs aquí]
```

## Tu Entorno
- OS: 
- Python: 3.14
- Versión del Bot: 1.0.0
```

## 🎨 Sugerir Features

¿Tienes una idea? ¡Nos encanta!

1. Abre un [Issue](https://github.com/LuisDelgado-LD/rss-resumen-bot/issues)
2. Título: "Feature Request: [Tu idea]"
3. Descripción:
   - Problema que resuelve
   - Propuesta de solución
   - Alternativas consideradas
   - Impacto estimado

---

## 💻 Desarrollo

### Setup Local

```bash
# Clonar tu fork
git clone https://github.com/TU_USUARIO/rss-resumen-bot.git
cd rss-resumen-bot

# Crear rama
git checkout -b fix/bug-nombre
# o
git checkout -b feature/nueva-feature

# Setup
./setup.sh
source venv/bin/activate

# Instalar dev dependencies
pip install pytest pytest-asyncio black flake8 mypy

# Copiar .env.example
cp .env.example .env
# Completar variables necesarias
```

### Workflow

1. **Crea una rama** desde `main`:
   ```bash
   git checkout -b feature/descripcion
   ```

2. **Haz cambios** en tu rama

3. **Prueba** localmente:
   ```bash
   # Validar configuración
   python -m src.cli validate
   
   # Probar sin enviar a Telegram
   python -m src.cli digest --dry-run
   
   # Ver logs en caso de error
   grep ERROR tests/logs/*.log
   ```

4. **Commit** con mensajes claros:
   ```bash
   git commit -m "Agrega validación de contraseña en TT-RSS"
   # o
   git commit -m "Fix: Error en scraping de URLs con acentos (Fix #123)"
   ```

5. **Push** a tu fork:
   ```bash
   git push origin feature/descripcion
   ```

6. **Abre Pull Request** en GitHub

### Convenciones de Código

#### Python Style

- **Formatter**: Black (configurado en `setup.sh`)
- **Linter**: flake8 (max 100 chars per line)
- **Type Hints**: Usar en funciones principales

```python
# ✅ BIEN
from typing import Optional
from src.clients.ttrss_client import TTRSSClient

def get_articles(
    client: TTRSSClient,
    hours: int = 24,
    dry_run: bool = False
) -> List[Article]:
    """Obtiene artículos de TT-RSS.
    
    Args:
        client: Cliente TT-RSS inicializado
        hours: Horas hacia atrás
        dry_run: Si True, no envía a Telegram
    
    Returns:
        Lista de artículos procesados
    """
    pass
```

#### Logging

- **Usa**: `logger.info()`, `logger.debug()`, `logger.error()`
- **Nunca loggees**: Passwords, tokens secretos, datos sensibles
- **Ubicación**: `tests/logs/` para desarrollo

```python
# ✅ BIEN
logger.info(f"Procesando {len(articles)} artículos")
logger.debug(f"Body size: {len(response.text)} bytes")

# ❌ MAL
logger.info(f"Password: {password}")
logger.debug(f"Token: {GOOGLE_API_KEY}")
```

#### Documentación

- Docstrings en funciones principales
- Comentarios para lógica compleja
- README.md si cambias interfaz pública

```python
def mark_as_read(
    self,
    article_id: int,
    comment_id: Optional[int] = None
) -> bool:
    """Marca un artículo como leído en TT-RSS.
    
    Soporta dos modos:
    - Si comment_id es None: marca el artículo principal
    - Si comment_id es given: marca específicamente ese comment
    
    Args:
        article_id: ID del artículo
        comment_id: ID del comentario (opcional)
    
    Returns:
        True si fue exitoso, False si falló
    
    Raises:
        TTRSSConnectionError: Si no hay conexión
        TTRSSAuthError: Si las credenciales expiraron
    """
```

### Testing

**Importante**: Verifica que tu cambio funciona

```bash
# Validar configuración
python -m src.cli validate

# Test dry-run: simular sin enviar a Telegram
python -m src.cli digest --dry-run

# Chequear logs en caso de error
grep ERROR tests/logs/*.log
```

### Commits

- **Mensaje claro**: Especifica qué cambió y por qué
- **Referencia issues**: Usa `Fix #123` o `Relate #456`
- **Atómico**: Un cambio lógico por commit

```
# ✅ Buen mensaje
Agrega timeouts a scraper por dominio

- Timeout configurable en SCRAPING_TIMEOUT_SECONDS
- Fallback a RSS si scraping falla
- Tests nuevos para timeout edge cases
Fix #89

# ❌ Malo
fixed stuff
updated code
asdf qwerty
```

---

## 📝 Pull Request

### Before Opening PR

1. **Asegúrate de**:
   - [ ] Tu rama está actualizada con `main`
   - [ ] El cambio funciona: `python -m src.cli validate`
   - [ ] Testeado con dry-run: `python -m src.cli digest --dry-run`
   - [ ] No hay credenciales en el código (solo variables de .env)

2. **Commits buenos**:
   - [ ] Mensajes claros
   - [ ] Cambios lógicos atomizados
   - [ ] Sin commits "WIP" o "fix typo"

### PR Description

```markdown
## Descripción
[Qué cambió y por qué]

## Tipo de Cambio
- [ ] Bug fix
- [ ] Nueva feature
- [ ] Mejora de documentación
- [ ] Refactor

## Relacionado a
Fix #123

## Testing
- [ ] Tests unitarios agregados
- [ ] Tests de integración pasaron
- [ ] Testeado manualmente con `.env` real

## Checklist
- [ ] Mi código sigue el style guide
- [ ] He actualizado la documentación
- [ ] No hay breaking changes
- [ ] Los logs están limpios (sin credenciales)
```

---

## 🎯 Donde Contribuir


### Pequeñas Contribuciones

Si no sabes por dónde empezar:

- Mejora documentación (typos, claridad)
- Agrega más tests
- Mejora robustez de error handling

---

## 🚀 Proceso de Review

1. **Automático**: Tests y lint checks corren en GitHub Actions
2. **Manual**: Maintainer revisa el código
3. **Feedback**: Comenta si hay cambios necesarios
4. **Aprobación**: Los reviewers aprueban
5. **Merge**: Se integra a `main`

### Esperado en Review

- Claridad del código
- Tests coverage adecuado
- Documentación actualizada
- Mensajes de commit limpios
- Sin breaking changes no documentados

---

## 💡 Tips

### Debug Effectivo Sí, procede

```bash
# Verbose logging
export LOG_LEVEL=DEBUG
python -m src.cli digest

# Ver qué se enviaría sin enviar
python -m src.cli digest --dry-run

# Validar config
python -m src.cli validate

# Ipython interactivo
ipython
 >>> from src.clients.ttrss_client import TTRSSClient
 >>> client = TTRSSClient(...)
 >>> client.get_feeds()
```

### Common Issues

**ImportError: No module named 'src'**
```bash
# Asegúrate de estar en root del proyecto
cd /path/to/rss-resumen-bot
source venv/bin/activate
```

**Tests fallan aleatoriamente**
→ Problemas de sincronización/fixtures. Agrega `--tb=short` para traceback:
```bash
pytest tests/integration/ --tb=short -v
```

**Performance lento en scraping**
→ Reduce `SCRAPING_MAX_PARALLEL_DOMAINS` en `.env`

---

## 🎓 Aprendiendo del Código

### Entrypoints principales

```
src/
├── cli.py              ← Punto de entrada (CLI)
├── orchestrator.py     ← Flujo principal
├── bot/terraform_bot.py    ← Bot Telegram
└── clients/            ← Clientes de APIs
```

### Flujo típico

1. CLI → orchestrator.py
2. orchestrator → clients (TT-RSS, Gemini)
3. Services (scraping, prompt)
4. telegram_dispatcher → Telegram
5. state_manager persiste resultado

---

## 🙌 Después de Contribuir

1. ¡Gracias por tu PR! 😊
2. Tu nombre aparecerá en [README](#)
3. Podrás collaborar en futuras features

---

## 📞 Preguntas?

- Abre un [Discussion](https://github.com/LuisDelgado-LD/rss-resumen-bot/discussions)
- Revisa [Issues abiertos](https://github.com/LuisDelgado-LD/rss-resumen-bot/issues) para contexto

---

**¡Feliz contribuyendo!** 🚀
