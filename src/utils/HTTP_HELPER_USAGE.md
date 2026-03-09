# EJEMPLO DE USO DEL HTTPRequestHelper

## Opción A: Usar el helper directamente (recomendado)

```python
from src.utils.http_helper import HTTPRequestHelper

# En lugar de:
response = requests.post(url, json=payload, timeout=30)
response.raise_for_status()

# Usar:
response = HTTPRequestHelper.post(
    url=url,
    json_data=payload,
    timeout=30,
    context="Telegram sendMessage"  # Descripción para logs
)
# Ya no necesitas raise_for_status(), el helper lo hace automáticamente
# Y loggea TODO según el guideline
```

## Opción B: Usar el decorator

```python
from src.utils.http_helper import log_http_errors
import requests

class TelegramClient:
    
    @log_http_errors(context="Telegram sendMessage")
    def send_message(self, text: str):
        url = f"{self.api_url}/sendMessage"
        payload = {'chat_id': self.chat_id, 'text': text}
        
        response = requests.post(url, json=payload, timeout=30)
        
        # Si falla, el decorator loggea TODO automáticamente
        if not response.ok:
            error_detail = response.json() if response.text else {}
            logger.error(f"❌ Telegram API error: {error_detail}")
            response.raise_for_status()
        
        return response.json()
```

## Logs que genera automáticamente:

```
# Request:
→ POST https://api.telegram.org/bot.../sendMessage
→ Headers: {'Content-Type': 'application/json'}
→ Payload: {"chat_id": 123456, "text": "Hello"}

# Response exitosa:
← Status: 200 (0.45s)
← Response: {"ok": true, "result": {...}}
✅ Telegram sendMessage completed (0.45s)

# Response con error:
← Status: 400 (0.32s)
❌ Telegram sendMessage failed: HTTP 400
❌ Error detail: {'ok': False, 'error_code': 400, 'description': 'Bad Request: can't parse entities'}
→ Failed request payload: {"chat_id": 123456, "text": "Bad [markdown"}
```

## Ventajas:

1. ✅ Logging consistente en TODO el proyecto
2. ✅ Sigue el guideline automáticamente
3. ✅ No necesitas recordar qué loggear
4. ✅ Enmascara tokens/passwords automáticamente
5. ✅ Timing automático
6. ✅ Manejo de errores estandarizado

## Cuándo usarlo:

✅ Llamadas a APIs externas (Telegram, Google, TT-RSS)
✅ Cualquier HTTP request que pueda fallar
❌ Requests internos triviales (health checks, etc.)
