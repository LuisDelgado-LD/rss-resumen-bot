# Directrices de Logging

## Filosofía

El sistema de logging debe permitir **diagnosticar problemas en producción sin necesidad de agregar más prints o reintentar**.

Cada nivel tiene un propósito específico y debe proporcionar información suficiente para su contexto de uso.

---

## Niveles de Log

### DEBUG (10)
**Propósito**: Información técnica detallada para debugging profundo

**Cuándo usar**:
- Requests HTTP completos (método, URL, headers, payload)
- Responses HTTP (status code, headers, body parcial)
- Tiempos de respuesta
- Parámetros de entrada a funciones
- Datos intermedios en procesamiento
- Estado de variables importantes
- Primeros N elementos de listas grandes
- Estructura de objetos complejos

**Qué incluir**:
```python
# ✅ BUENO
logger.debug(f"→ POST {url}")
logger.debug(f"→ Headers: {dict(headers)}")
logger.debug(f"→ Payload: {json.dumps(payload, indent=2)}")
logger.debug(f"← Status: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
logger.debug(f"← Response: {response.text[:500]}...")
logger.debug(f"Artículos recibidos: {len(articles)}, primeros 3: {[a['id'] for a in articles[:3]]}")

# ❌ MALO
logger.debug("Making request")
logger.debug("Got response")
```

**Regla**: Si necesitas "agregar un print" para debuggear, es que falta un DEBUG log.

---

### INFO (20)
**Propósito**: Registro de flujo de negocio y resultados exitosos

**Cuándo usar**:
- Inicio/fin de operaciones importantes
- Resultados de operaciones (cuántos items procesados)
- Hitos del flujo de ejecución
- Cambios de estado del sistema
- Métricas de operación (tiempo total, throughput)

**Qué incluir**:
```python
# ✅ BUENO
logger.info("Autenticando con TT-RSS...")
logger.info(f"✅ Autenticación exitosa (session_id: {sid[:8]}...)")
logger.info(f"✅ {len(articles)} artículos obtenidos en {elapsed:.1f}s")
logger.info(f"✅ Procesados: {processed}/{total} artículos ({processed/total*100:.1f}%)")

# ❌ MALO
logger.info("Done")
logger.info(f"Articles: {articles}")  # Demasiado detalle
```

**Regla**: Debe ser leíble como una "historia" del flujo de ejecución.

---

### WARNING (30)
**Propósito**: Situaciones anómalas que NO impiden continuar la operación

**Cuándo usar**:
- Datos inesperados pero manejables
- Reintentos de operaciones
- Límites alcanzados (truncamiento)
- Configuraciones subóptimas
- Operaciones que toman más tiempo del esperado
- Datos faltantes con fallback

**Qué incluir**:
```python
# ✅ BUENO
logger.warning(f"⚠️  Timeout en request (intento {attempt}/{max_attempts})")
logger.warning(f"⚠️  Límite de {max_articles} artículos alcanzado, hay más disponibles")
logger.warning(f"⚠️  Feed {feed_id} sin categoría, usando 'Uncategorized'")
logger.warning(f"⚠️  Scraping falló para {url} (error: {error}), usando contenido RSS")
logger.warning(f"⚠️  Artículo {article_id} sin contenido, descartado")

# ❌ MALO
logger.warning("Something went wrong")
logger.warning("Retrying")  # Falta contexto
```

**Regla**: Debe indicar QUÉ está mal, POR QUÉ es un problema, y QUÉ se hizo al respecto.

---

### ERROR (40)
**Propósito**: Errores que impiden completar una operación específica

**Cuándo usar**:
- Operaciones fallidas después de reintentos
- Errores de API irrecuperables
- Datos inválidos que causan fallo
- Excepciones capturadas
- Recursos no disponibles

**Qué incluir**:
```python
# ✅ BUENO
logger.error(f"❌ Autenticación falló después de {attempts} intentos")
logger.error(f"❌ API error: {error_msg} | Payload: {payload}")
logger.error(f"❌ Scraping falló para {url}: {error_type}: {error_msg}")
logger.error(f"❌ No se pudo procesar artículo {article_id}: {exception}", exc_info=True)

# ❌ MALO
logger.error("Error")
logger.error(str(e))  # Sin contexto
```

**Regla**: Debe incluir suficiente información para reproducir el error. Usar `exc_info=True` para stack traces.

---

### CRITICAL (50)
**Propósito**: Errores fatales que impiden la ejecución del programa

**Cuándo usar**:
- Configuración crítica faltante/inválida
- Recursos esenciales no disponibles (base de datos, API)
- Errores que requieren intervención inmediata
- Estado corrupto del sistema

**Qué incluir**:
```python
# ✅ BUENO
logger.critical(f"❌ FATAL: No se puede conectar a TT-RSS en {url}")
logger.critical(f"❌ FATAL: Variable de entorno {var_name} no configurada")
logger.critical(f"❌ FATAL: Archivo de configuración corrupto: {path}")
logger.critical(f"❌ FATAL: Sin memoria disponible, terminando")

# ❌ MALO
logger.critical("Failed")
```

**Regla**: Solo para errores que requieren **detener la ejecución**. El programa debe terminar después.

---

## Directrices Adicionales

### 1. Sensibilidad de Datos
- **NUNCA** loggear passwords, tokens, API keys completos
- Enmascarar datos sensibles: `token[:8]}...`
- En DEBUG, OK mostrar primeros caracteres: `password: {pwd[:3]}***`

### 2. Formato de Mensajes
```python
# Estructura clara
logger.info(f"Operación: estado (detalles)")
logger.info(f"✅ Autenticación: exitosa (user: {user}, session: {sid[:8]}...)")

# Usar símbolos consistentes
# ✅ Éxito
# ❌ Error
# ⚠️  Advertencia
# 🔍 Debug/Info adicional
# → Request/Entrada
# ← Response/Salida
```

### 3. Contexto
Siempre incluir:
- **QUÉ** se está haciendo
- **DÓNDE** (función, recurso, URL)
- **CUÁNTO** (cantidad, tiempo)
- **POR QUÉ** falló (si aplica)

### 4. Volumetría
```python
# Para listas grandes, mostrar samples
logger.debug(f"Artículos: {len(articles)} total, primeros 5 IDs: {[a['id'] for a in articles[:5]]}")

# Para objetos, mostrar estructura
logger.debug(f"Feed: id={feed['id']}, title={feed['title']}, unread={feed.get('unread', 0)}")

# NO dumpear objetos completos
# ❌ logger.debug(f"Data: {data}")  # Si data es enorme
```

### 5. Timing
```python
import time

start = time.time()
# ... operación ...
elapsed = time.time() - start

logger.info(f"✅ Operación completada en {elapsed:.2f}s")
logger.debug(f"Tiempo de respuesta: {elapsed*1000:.0f}ms")
```

### 6. Entrada/Salida de Funciones
```python
# Entrada a función (DEBUG)
def get_articles(feed_id: int, limit: int, since_hours: Optional[int] = None):
    logger.debug(f"→ get_articles(feed_id={feed_id}, limit={limit}, since_hours={since_hours})")
    
    # ... procesamiento ...
    
    # Salida de función (DEBUG)
    logger.debug(f"← get_articles() → {len(articles)} artículos en {elapsed:.2f}s")
    return articles

# Para funciones críticas, agregar INFO al final
def login(self):
    logger.debug(f"→ login(user={self.username})")
    logger.info("Autenticando con TT-RSS...")
    
    # ... autenticación ...
    
    logger.debug(f"← login() → session_id={session_id[:8]}...")
    logger.info(f"✅ Autenticación exitosa")
    return session_id

# Para funciones simples, solo entrada si tiene parámetros complejos
def process_article(article: dict):
    logger.debug(f"→ process_article(id={article['id']}, feed={article['feed_id']})")
    # ... procesamiento ...
    logger.debug(f"← process_article() → {len(cleaned_content)} chars")
```

**Cuándo loggear entrada/salida:**
- **Entrada (→)**: Funciones con parámetros importantes o complejos
- **Salida (←)**: Cuando el resultado es relevante (cantidad, tiempo, estado)
- **Ambos**: Funciones que pueden fallar o tomar tiempo
- **Ninguno**: Funciones triviales o llamadas muy frecuentes (getters simples)

### 7. Estructura HTTP
```python
# Request
logger.debug(f"→ {method} {url}")
logger.debug(f"→ Headers: {dict(headers)}")
logger.debug(f"→ Payload: {json.dumps(payload, indent=2)}")

# Response
logger.debug(f"← Status: {response.status_code}")
logger.debug(f"← Elapsed: {response.elapsed.total_seconds():.3f}s")
logger.debug(f"← Headers: {dict(response.headers)}")
logger.debug(f"← Body: {response.text[:500]}{'...' if len(response.text) > 500 else ''}")
```
### 8. APIs Externas con Errores

Cuando llamas a APIs de terceros (Telegram, Google, etc.):

**Siempre:**
```python
response = requests.post(url, json=payload, timeout=30)

# ANTES de raise_for_status(), loggear el error
if not response.ok:
    error_body = response.json() if response.text else {}
    logger.error(f"❌ API error: {error_body}")
    logger.debug(f"→ Request payload: {json.dumps(payload, indent=2)[:500]}")
    response.raise_for_status()
```

**Por qué:** APIs externas devuelven errores descriptivos en el body (ej: "invalid character at position 42"). Sin esto, solo ves "400 Bad Request" que no dice nada.

#### Ejemplo 1: Telegram API

```python
def send_message(self, text: str, parse_mode: str = "MarkdownV2"):
    """Envía un mensaje a Telegram."""
    url = f"{self.api_url}/sendMessage"
    
    payload = {
        'chat_id': self.chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    
    logger.debug(f"→ POST {url}")
    logger.debug(f"→ Payload: chat_id={self.chat_id[:8]}..., parse_mode={parse_mode}, text_length={len(text)}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        # ✅ IMPORTANTE: Loggear error ANTES de raise_for_status
        if not response.ok:
            error_data = response.json() if response.text else {}
            error_description = error_data.get('description', 'Sin descripción')
            
            logger.error(f"❌ Telegram API error: {error_description}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Error completo: {error_data}")
            logger.debug(f"→ Mensaje enviado: {text[:200]}...")
            
            # Ahora sí, lanzar excepción
            response.raise_for_status()
        
        result = response.json()
        message_id = result['result']['message_id']
        
        logger.debug(f"← Status: 200, message_id={message_id}")
        logger.info(f"✅ Mensaje enviado a Telegram (id: {message_id})")
        
        return message_id
        
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout enviando mensaje a Telegram (>30s)")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error de red con Telegram API: {e}", exc_info=True)
        raise
```

**Salida en logs con error:**
```
ERROR - ❌ Telegram API error: Bad Request: can't parse entities: Character '\' is reserved and must be escaped with the preceding '\'
ERROR -    Status: 400
ERROR -    Error completo: {'ok': False, 'error_code': 400, 'description': "Bad Request: can't parse entities: Character '\\' is reserved..."}
DEBUG - → Mensaje enviado: 📰 *Resumen de Seguridad*\nNuevas vulnerabilidades...
```

#### Ejemplo 2: Google Gemini API

```python
def generate_summary(self, articles: list, category: str):
    """Genera resumen usando Gemini."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    prompt = self._build_prompt(articles, category)
    
    payload = {
        'contents': [{
            'parts': [{'text': prompt}]
        }],
        'generationConfig': {
            'temperature': 0.7,
            'maxOutputTokens': 2048
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': self.api_key
    }
    
    logger.debug(f"→ POST {url}")
    logger.debug(f"→ Prompt: {len(prompt)} chars, {len(articles)} artículos")
    logger.debug(f"→ Config: temp=0.7, max_tokens=2048")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        # ✅ IMPORTANTE: Loggear error ANTES de raise_for_status
        if not response.ok:
            error_data = response.json() if response.text else {}
            
            # Gemini devuelve errores en formato específico
            error_message = error_data.get('error', {}).get('message', 'Sin mensaje')
            error_code = error_data.get('error', {}).get('code', response.status_code)
            
            logger.error(f"❌ Google Gemini API error: {error_message}")
            logger.error(f"   Error code: {error_code}")
            logger.error(f"   Categoría: {category}")
            logger.error(f"   Artículos: {len(articles)}")
            logger.debug(f"→ Prompt enviado: {prompt[:300]}...")
            logger.debug(f"   Error completo: {error_data}")
            
            response.raise_for_status()
        
        result = response.json()
        summary_text = result['candidates'][0]['content']['parts'][0]['text']
        
        logger.debug(f"← Status: 200, respuesta: {len(summary_text)} chars")
        logger.info(f"✅ Resumen generado para {category} ({len(summary_text)} chars)")
        
        return summary_text
        
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout en Gemini API (>60s) para categoría {category}")
        raise
    except KeyError as e:
        logger.error(f"❌ Respuesta inesperada de Gemini API: {e}")
        logger.debug(f"   Response: {response.text[:500]}")
        raise
```

**Salida en logs con error:**
```
ERROR - ❌ Google Gemini API error: The model `gemini-pro` does not support the requested operation
ERROR -    Error code: 400
ERROR -    Categoría: Seguridad
ERROR -    Artículos: 15
DEBUG - → Prompt enviado: Eres un analista de ciberseguridad...
DEBUG -    Error completo: {'error': {'code': 400, 'message': 'The model `gemini-pro` does not support...', 'status': 'INVALID_ARGUMENT'}}
```

#### Ejemplo 3: TT-RSS API

```python
def _call_api(self, operation: str, **additional_params):
    """Llama a la API de TT-RSS."""
    payload = {
        'op': operation,
        'sid': self.session_id,
        **additional_params
    }
    
    logger.debug(f"→ POST {self.url}")
    logger.debug(f"→ Operation: {operation}")
    logger.debug(f"→ Params: {json.dumps(additional_params, indent=2)}")
    
    try:
        response = requests.post(self.url, json=payload, timeout=30)
        
        # ✅ IMPORTANTE: Loggear error ANTES de raise_for_status
        if not response.ok:
            logger.error(f"❌ TT-RSS HTTP error: {response.status_code}")
            logger.error(f"   Operation: {operation}")
            logger.error(f"   Parámetros: {additional_params}")
            logger.debug(f"   Response body: {response.text[:500]}")
            
            response.raise_for_status()
        
        result = response.json()
        
        # TT-RSS devuelve status en el JSON incluso con HTTP 200
        if result.get('status') == 1:
            # Error de API (autenticación, operación inválida, etc.)
            error_type = result.get('content', {}).get('error', 'UNKNOWN_ERROR')
            
            logger.error(f"❌ TT-RSS API error: {error_type}")
            logger.error(f"   Operation: {operation}")
            logger.error(f"   Session ID: {self.session_id[:8] if self.session_id else 'None'}...")
            logger.debug(f"   Respuesta completa: {result}")
            
            raise TTRSSAPIError(f"API error: {error_type}")
        
        logger.debug(f"← Status: 200, seq={result.get('seq', 'N/A')}")
        logger.debug(f"← Content type: {type(result.get('content')).__name__}")
        
        return result['content']
        
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout en TT-RSS (>30s) para operación: {operation}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error de red con TT-RSS: {e}", exc_info=True)
        raise
```

**Salida en logs con error:**
```
ERROR - ❌ TT-RSS API error: NOT_LOGGED_IN
ERROR -    Operation: getHeadlines
ERROR -    Session ID: a1b2c3d4...
DEBUG -    Respuesta completa: {'status': 1, 'content': {'error': 'NOT_LOGGED_IN'}, 'seq': 0}
```

#### Resumen de Mejores Prácticas

**✅ Hacer:**
- Loggear error ANTES de `raise_for_status()`
- Extraer mensaje descriptivo del body de respuesta
- Incluir contexto: operación, parámetros relevantes, categoría
- Usar DEBUG para payload/respuesta completa (puede ser largo)
- Usar ERROR para mensajes de error específicos
- Capturar timeouts por separado (son comunes y esperables)

**❌ Evitar:**
```python
# ❌ MALO: Solo lanza excepción sin context
response.raise_for_status()

# ❌ MALO: Log genérico
logger.error(f"Error en API: {e}")

# ❌ MALO: No se ve el error real de la API
logger.error(f"Status {response.status_code}")
# Sin loggear response.json() pierdes el mensaje descriptivo

# ❌ MALO: Exponer datos sensibles
logger.error(f"Error con API key: {api_key}")
```

---

## Ejemplos por Módulo

### Cliente HTTP (ttrss_client.py)
```python
# DEBUG: Request/Response completos
logger.debug(f"→ POST {self.url}")
logger.debug(f"→ Operation: {operation}")
logger.debug(f"→ Params: {json.dumps(additional_params, indent=2)}")

# INFO: Resultados de operaciones
logger.info(f"✅ {len(categories)} categorías obtenidas")

# WARNING: Reintentos
logger.warning(f"⚠️  Timeout en {operation} (intento {attempt}/{max_attempts}, reintentando en {delay}s)")

# ERROR: Fallo después de reintentos
logger.error(f"❌ {operation} falló después de {attempts} intentos: {last_error}")
```

### Servicios (scraper.py, article_service.py)
```python
# DEBUG: Procesamiento detallado
logger.debug(f"Scraping {url}")
logger.debug(f"Contenido extraído: {len(content)} chars, primeros 100: {content[:100]}")

# INFO: Resumen de procesamiento
logger.info(f"✅ Scraping exitoso: {successful}/{total} artículos")

# WARNING: Contenido insuficiente
logger.warning(f"⚠️  Artículo {article['id']} con contenido insuficiente ({len(content)} chars < {min_length})")

# ERROR: Scraping falló
logger.error(f"❌ Scraping falló para {url}: {error_type}: {error_msg}")
```

---

## Checklist de Implementación

Para cada función que modifiques, verifica:

- [ ] INFO al inicio de operaciones importantes
- [ ] DEBUG con parámetros de entrada
- [ ] DEBUG con requests HTTP (método, URL, payload)
- [ ] DEBUG con responses HTTP (status, tiempo, body parcial)
- [ ] INFO con resultados exitosos (cantidad, tiempo)
- [ ] WARNING para situaciones anómalas recuperables
- [ ] ERROR con contexto completo para fallos
- [ ] CRITICAL solo para fallos fatales
- [ ] No exponer datos sensibles
- [ ] Usar `exc_info=True` en errores con exceptions

---

## Anti-patrones a Evitar

```python
# ❌ Mensajes genéricos
logger.debug("Processing")
logger.info("Done")
logger.error("Error")

# ❌ Sin contexto
logger.warning("Timeout")  # Timeout de QUÉ?
logger.error(str(e))  # Error en QUÉ operación?

# ❌ Demasiado verboso en INFO
logger.info(f"Articles: {articles}")  # 1000 líneas de output

# ❌ Datos sensibles
logger.debug(f"Password: {password}")
logger.info(f"API Key: {api_key}")

# ❌ Nivel incorrecto
logger.info(f"Request payload: {huge_payload}")  # Debería ser DEBUG
logger.debug(f"Authentication failed")  # Debería ser ERROR
```

---

## Uso en Testing

Los tests usan un handler personalizado que intercepta logs:

```python
# Los logs de servicios aparecen con prefijo
[TEST] Mensaje del test
[TEST:ttrss_client] Cliente TT-RSS inicializado
[TEST:article_service] Procesando artículos
[TEST:scraper] Scraping exitoso

# Configurar nivel DEBUG en tests para ver todo
article_logger.setLevel(logging.DEBUG)
```

Beneficios:
- Distinguir logs del test vs logs de servicios
- Ver flujo completo con todos los detalles
- Debugging sin modificar código fuente
