# Telegram Supergroup con Topics - Guía de Configuración Completa

## 📋 Resumen

El sistema ahora soporta dos modos de envío:
- **chat**: Envío a chat 1:1 con índice + botones (comportamiento original)
- **supergroup**: Envío a Supergrupo con Topics, 1 resumen por topic

**Características del modo supergroup:**
- ✅ Reacciones individuales (❤️ 👍 🔥) marcan artículos específicos
- ✅ Botones por categoría para marcado masivo
- ✅ Botones globales para marcar todo
- ✅ Division automática de resúmenes en párrafos
- ✅ Mapeo preciso de artículos por mensaje

---

## ⚙️ PARTE 1: Configurar Permisos del Bot

### 🔐 Requisitos Críticos

Para que el bot pueda recibir reacciones (emojis) en el supergrupo, necesita:

1. **Privacy Mode deshabilitado** en BotFather
2. **Ser administrador** del supergrupo

### Paso 1: Deshabilitar Privacy Mode

**⚠️ CRÍTICO:** El Privacy Mode evita que el bot reciba reacciones.

1. Abre Telegram y busca **@BotFather**
2. Envía el comando: `/mybots`
3. Selecciona tu bot
4. Selecciona: **Bot Settings**
5. Selecciona: **Group Privacy**
6. Selecciona: **Turn OFF** (debe quedar en **OFF**)

**Resultado esperado:**
```
Group Privacy is disabled
Your bot can see all messages in groups
```

**¿Por qué es necesario?**

Con Privacy Mode **ON**, el bot solo ve:
- ✅ Comandos que empiezan con `/`
- ✅ Menciones con `@bot`
- ✅ Callbacks (botones inline)
- ❌ **Reacciones (emojis)** ← ¡No funciona!
- ❌ Mensajes normales del grupo

Con Privacy Mode **OFF**, el bot puede:
- ✅ Ver todos los mensajes del grupo
- ✅ **Recibir reacciones (emojis)** ← ¡Esto es lo que necesitamos!

### Paso 2: Hacer al Bot Administrador

1. Abre el supergrupo en Telegram
2. Toca el nombre del grupo → **Administradores**
3. **Agregar administrador** → Busca tu bot
4. Habilita estos permisos mínimos:
   - ✅ **Eliminar mensajes**
   - ✅ **Gestionar topics** (si usas topics)
   - ✅ **Anclar mensajes** (opcional)

### 🧪 Verificar Configuración del Bot

Usa el script de diagnóstico para verificar que todo está bien:

```bash
source venv/bin/activate
python scripts/diagnose_bot_permissions.py
```

**Durante los 10 segundos de espera, prueba:**
- Envía un mensaje → Debe aparecer `MESSAGE`
- Haz click en un botón → Debe aparecer `CALLBACK_QUERY`
- **Reacciona a un mensaje → Debe aparecer `MESSAGE_REACTION`** ⭐

Si ves `MESSAGE_REACTION`, ¡perfecto! Tu bot está listo para recibir reacciones.

---

## 🏗️ PARTE 2: Configurar Supergrupo con Topics

### 1. Crear Supergrupo en Telegram

1. Abre Telegram
2. Crea un nuevo grupo
3. Añade al menos 1 miembro (además de ti)
4. Ve a configuración del grupo → "Convertir a Supergrupo"

### 2. Habilitar Topics

1. En el Supergrupo, ve a configuración
2. Activa "Topics" (hilos/temas)
3. Crea un topic por cada categoría de TT-RSS:
   - Linux
   - Seguridad
   - DevOps
   - Noticias Linux
   - Opinion
   - Random
   - Noticias general
   - etc.

### 3. Obtener IDs

#### 🚀 Método Automático (Recomendado):

Usa el script incluido para obtener automáticamente todos los IDs:

```bash
# Opción 1: Usar configuración de .env
python scripts/get_supergroup_topics.py

# Opción 2: Especificar token y chat_id manualmente
python scripts/get_supergroup_topics.py --token TU_BOT_TOKEN --chat-id -1001234567890

# Opción 3: Guardar en archivo personalizado
python scripts/get_supergroup_topics.py --output mi_topics.json
```

El script:
- ✅ Detecta automáticamente todos los topics del supergrupo
- ✅ Obtiene sus IDs y nombres
- ✅ Genera el archivo `topics.json` con el formato correcto
- ✅ Puede enviar mensajes de prueba para confirmar nombres

**Requisitos:**
- El bot debe estar agregado al supergrupo como administrador
- Debe haber al menos un mensaje en cada topic

#### 📝 Método Manual:

Si prefieres obtener los IDs manualmente:

**Chat ID del Supergrupo:**

Opción A - Con @userinfobot:
```
1. Reenvía un mensaje del supergrupo a @userinfobot
2. Te responderá con el chat_id (será negativo, ej: -1001234567890)
```

Opción B - Con la API de Telegram:
```bash
curl https://api.telegram.org/bot<TOKEN>/getUpdates
# Busca "chat":{"id": -1001234567890}
```

**Topic ID de cada topic:**

1. Envía un mensaje al topic específico
2. Usa @userinfobot o inspecciona la API:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Busca `"message_thread_id": 123` en el mensaje

### 4. Configurar `utils/topics.json`

Edita el archivo `utils/topics.json`:

```json
{
  "categories": {
    "Linux": 123,
    "Seguridad": 456,
    "DevOps": 789,
    "Noticias Linux": 101,
    "Opinion": 102,
    "Random": 103,
    "Noticias general": 104
  }
}
```

**Importante:**
- Los nombres de categoría deben coincidir **EXACTAMENTE** con los de TT-RSS
- Usa el topic_id numérico (sin comillas)
- Si una categoría no tiene topic configurado, se saltará

### 5. Configurar `.env`

```env
# Modo de Telegram
TELEGRAM_MODE=supergroup  # o "chat"

# Chat ID del Supergrupo (negativo)
TELEGRAM_CHAT_ID=-1001234567890

# Token del bot (igual que antes)
TELEGRAM_BOT_TOKEN=123456:ABCdef...
```

## 🧪 Probar la Configuración

### Validar configuración:

```bash
python -c "from src.config import settings; print(settings.get_topics_map())"
```

Debería mostrar el mapeo de categorías → topic_id sin errores.

### Test de envío:

```bash
python tests/integration/test_etapa5_supergroup_send.py --fixture editado
```

Esto:
1. Cargará resúmenes de Etapa 3
2. Enviará cada resumen a su topic correspondiente
3. Enviará mensaje final con estadísticas y botones
4. Guardará mapeo en `state/`

## 📊 Flujo de Uso

### Envío automático:
1. Bot divide el resumen de Gemini en párrafos (separados por líneas en blanco)
2. Envía cada párrafo como mensaje individual al topic correspondiente
3. Extrae los IDs `[123]` mencionados en cada párrafo para mapeo preciso
4. Bot envía botones de gestión en cada topic:
   - ✅ "Marcar [Categoría] como leído"
   - 🚫 "Excluir de marcado masivo"
5. Al final envía mensaje con estadísticas al **chat principal** (fuera de topics)
6. Incluye botones globales para marcado masivo

**Ejemplo deReacciones en mensajes individuales**
- ❤️ en un párrafo → marca solo los artículos mencionados en ese párrafo
- 🚫 en un párrafo → excluye esos artículos del marcado masivo
- Cada mensaje tiene mapeo preciso de los artículos que menciona por sus IDs `[123]`

**Opción 2: Por topic individual**
- Click en botones del topic → marca todos los artículos de esa categoría

**Opción 3afo 3: Ubuntu 24.04[126] nueva versión...
└─ 🔘 [Marcar Linux] [Excluir]

Topic: Seguridad
├─ 📰 Párrafo 1: CVE-2026-1234[200] en OpenSSL...
├─ 📰 Párrafo 2: Microsoft[201][202] parches...
└─ 🔘 [Marcar Seguridad] [Excluir]
```

### Gestión de lecturas:

**Opción 1: Por topic individual**
- Click en botones del topic → marca solo artículos de esa categoría
- ❤️ en un resumen → marca esos artículos como leídos en TT-RSS
- 🚫 en un resumen → excluye esos artículos del marcado masivo

**Opción 2: Batch marking global**
- Click en "Marcar TODOS" → marca todos los artículos del día
- Click en "Solo no reaccionados" → marca solo los pendientes

## 🔄 Volver a modo chat

Simplemente cambia en `.env`:

```env
TELEGRAM_MODE=chat
```

El sistema volverá al comportamiento original (índice + botones).

## 📁 Estructura de Archivos

```
utils/
  └── topics.json           # Mapeo categoría → topic_id

src/
  ├── config/
  │   └── settings.py       # Carga y valida topics.json
  ├── db/
  │   └── state_manager.py  # Tracking de mensajes y artículos
  ├── services/
  │   └── telegram_dispatcher.py  # Lógica de envío según modo
  └── clients/
      └── telegram_client.py      # Envío a topics

state/                      # Estado persistente (JSON)
  ├── message_map.json      # message_id → article_ids
  ├── excluded_articles.json
  └── marked_articles.json
```

## ⚠️ Troubleshooting

### "El bot NO recibe reacciones" (0 reacciones en estadísticas)

**Causa más común:** Privacy Mode está activado.

**Solución:**
1. Ve a @BotFather → `/mybots` → tu bot → Bot Settings → Group Privacy
2. Verifica que diga "Privacy mode is **disabled**"
3. Si está enabled, cámbialo a disabled
4. **Reinicia el bot completamente** (Ctrl+C y volver a ejecutar)
5. Ejecuta `python scripts/diagnose_bot_permissions.py` y reacciona durante el test
6. Debe aparecer `MESSAGE_REACTION` en los updates

**Otras causas:**
- El bot no es administrador del grupo → Agrégalo como admin
- Estás reaccionando en el chat incorrecto → Verifica el TELEGRAM_CHAT_ID
- El grupo no es un supergrupo → Conviértelo a supergrupo

### "Sigo sin recibir reacciones después de deshabilitar Privacy Mode"

1. **Verifica el cambio:**
   ```bash
   python scripts/diagnose_bot_permissions.py
   ```
   En la sección "PERMISOS DEL BOT" debe decir:
   ```
   ✅ Estado del bot en el chat: administrator
   ```

2. **Reinicia completamente:**
   - Detén el bot con Ctrl+C
   - Espera 5-10 segundos
   - Vuelve a ejecutar

3. **Prueba con mensaje nuevo:**
   - Envía un mensaje nuevo al grupo
   - Reacciona a ese mensaje (no a mensajes viejos)
   - Verifica que aparezca en los logs

### Error: "topics.json no encontrado"
- Verifica que existe `utils/topics.json`
- Path correcto desde raíz del proyecto

### Error: "Categoría no tiene topic configurado"
- Verifica nombres de categoría en topics.json
- Deben coincidir exactamente con TT-RSS

### Error: "Chat not found" en Telegram API
- Verifica que el TELEGRAM_CHAT_ID es correcto y negativo
- Asegúrate de que el bot es admin del supergrupo

### Error: "Message thread not found"
- Verifica que los topic_id son correctos
- Los topics deben estar activos (no archivados)

## 🛠️ Scripts de Ayuda

### 1. Script de Diagnóstico de Permisos

**`scripts/diagnose_bot_permissions.py`**

Verifica que el bot esté correctamente configurado para recibir reacciones.

**Uso:**
```bash
source venv/bin/activate
python scripts/diagnose_bot_permissions.py
```

**Qué hace:**
- ✅ Verifica conexión con el bot
- ✅ Verifica que el chat sea un supergrupo
- ✅ Verifica permisos de administrador
- ✅ Muestra todos los permisos del bot
- ✅ **Prueba recepción de updates en vivo (10 segundos)**

**Durante el test de 10 segundos:**
- Envía un mensaje → Aparece `MESSAGE`
- Haz click en un botón → Aparece `CALLBACK_QUERY`
- **Reacciona a un mensaje → Aparece `MESSAGE_REACTION`** ⭐

Si ves `MESSAGE_REACTION`, el bot puede recibir reacciones. Si no aparece, revisa Privacy Mode.

---

### 2. Script de Configuración de Topics

**`scripts/get_supergroup_topics.py`**

Script independiente que facilita la configuración inicial del supergrupo.

**Uso básico:**
```bash
# Usar configuración de .env
python scripts/get_supergroup_topics.py

# Especificar parámetros
python scripts/get_supergroup_topics.py \
  --token 123456:ABC-DEF... \
  --chat-id -1001234567890

# Ver ayuda
python scripts/get_supergroup_topics.py --help
```

**Opciones:**
- `--token`: Token del bot (opcional si está en .env)
- `--chat-id`: ID del supergrupo (opcional si está en .env)
- `--output`: Archivo de salida (default: `utils/topics.json`)
- `--no-save`: Solo mostrar sin guardar archivo
- `--no-test`: No enviar mensajes de prueba

**Flujo de trabajo:**
1. Conecta con el supergrupo usando la API de Telegram
2. Verifica que Topics esté habilitado
3. Detecta todos los topics desde mensajes recientes
4. Opcionalmente envía mensajes de prueba para confirmar nombres
5. Genera `utils/topics.json` con el formato correcto

**Notas:**
- El bot debe ser **administrador** del supergrupo
- Debe haber **al menos un mensaje** en cada topic para detectarlo
- Los mensajes de prueba se borran automáticamente
- El script NO modifica nada en `src/`

## ⚙️ Configuración de Rate Limiting

Para evitar errores 429 "Too Many Requests", el sistema incluye delays configurables:

```env
# En .env
TELEGRAM_MESSAGE_DELAY=1.5  # Segundos entre mensajes individuales
TELEGRAM_CATEGORY_DELAY=2.0  # Segundos entre cada categoría completa
```

**Valores recomendados:**
- **Predeterminado** (1.5s / 2.0s): Balance entre velocidad y seguridad
- **Más rápido** (0.5s / 1.0s): Puede causar errores 429, pero hay retry automático
- **Conservador** (3.0s / 5.0s): Muy seguro pero más lento

El sistema incluye **retry automático** que detecta errores 429 y espera el tiempo indicado por Telegram antes de reintentar.

## 📝 Notas Importantes

### Permisos del Bot
- **Privacy Mode DEBE estar deshabilitado** en BotFather para recibir reacciones
- El bot DEBE ser **administrador** del supergrupo
- Usa `scripts/diagnose_bot_permissions.py` para verificar configuración

### Estado y Persistencia
- StateManager usa JSON por ahora, migración a SQLite planeada
- Cleanup automático de mapeos >7 días
- Logs detallados en `tests/logs/etapa5_supergroup_*/`

### Scripts de Ayuda
- `scripts/diagnose_bot_permissions.py` - Verifica permisos y Privacy Mode
- `scripts/get_supergroup_topics.py` - Configuración automática de topics

### Comportamiento del Sistema
- Los resúmenes se dividen automáticamente por párrafos
- Solo párrafos con IDs `[123]` específicos se mapean para reacciones individuales
- Párrafos sin IDs (introductorios) no se pueden marcar individualmente
- Usa botones de categoría para marcar grupos completos

### Comparación: Privacy Mode ON vs OFF

| Funcionalidad | Privacy ON | Privacy OFF |
|---------------|------------|-------------|
| Comandos (`/start`) | ✅ | ✅ |
| Menciones (`@bot`) | ✅ | ✅ |
| Callbacks (botones) | ✅ | ✅ |
| Mensajes normales | ❌ | ✅ |
| **Reacciones (emojis)** | ❌ | ✅ |

---

**Última actualización:** 21 de febrero de 2026  
**Versión:** 2.0 - Guía combinada con configuración de permisos
