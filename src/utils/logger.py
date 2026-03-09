"""
Sistema de logging configurado para la aplicación.
Proporciona logs estructurados sin exponer información sensible.
"""
import logging
import sys
import re
from typing import Optional
from pathlib import Path
from datetime import datetime


class SensitiveDataFilter(logging.Filter):
    """Filtro para evitar que información sensible aparezca en los logs."""

    # Palabras clave sensibles basadas en .env.example y APIs
    SENSITIVE_KEYS = [
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "auth",
        "credential",
        "session_id",
        "bot_token",
        "chat_id",
        "client_id",
        "client_secret",
    ]

    # Patrones regex para detectar y enmascarar datos sensibles
    # Formato: (patron, grupo_a_enmascarar)
    SENSITIVE_PATTERNS = [
        # Formato key=value o key: value (URL params, logs simples)
        (re.compile(r'(password|passwd|pwd)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(api[_-]?key|apikey)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(token|access[_-]?token|auth[_-]?token)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(secret|client[_-]?secret)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(session[_-]?id|sid)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(bot[_-]?token|telegram[_-]?token)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        (re.compile(r'(chat[_-]?id)[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
        
        # Formato JSON/dict: "key": "value" o 'key': 'value'
        (re.compile(r'["\']?(password|passwd|pwd)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        (re.compile(r'["\']?(api[_-]?key|apikey)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        (re.compile(r'["\']?(token|access[_-]?token|auth[_-]?token)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        (re.compile(r'["\']?(secret|client[_-]?secret)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        (re.compile(r'["\']?(session[_-]?id|sid)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        (re.compile(r'["\']?(bot[_-]?token|telegram[_-]?token)["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE), 2),
        
        # URLs con credenciales: https://user:pass@domain.com
        (re.compile(r'://([^:]+):([^@]+)@', re.IGNORECASE), 2),
        
        # Bearer tokens
        (re.compile(r'Bearer\s+([A-Za-z0-9\-._~+/]+=*)', re.IGNORECASE), 1),
        
        # Variables de entorno específicas del proyecto
        (re.compile(r'TTRSS_PASSWORD["\']?\s*[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 1),
        (re.compile(r'GOOGLE_API_KEY["\']?\s*[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 1),
        (re.compile(r'TELEGRAM_BOT_TOKEN["\']?\s*[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 1),
        (re.compile(r'WALLABAG_(PASSWORD|CLIENT_SECRET)["\']?\s*[:=]\s*["\']?([^&\s"\',}]+)', re.IGNORECASE), 2),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filtra el mensaje del log para remover datos sensibles."""
        # Obtener el mensaje original
        original_msg = record.getMessage()
        
        # Aplicar enmascaramiento
        masked_msg = self._mask_sensitive_data(original_msg)
        
        # Si el mensaje cambió, actualizar el record
        if masked_msg != original_msg:
            record.msg = masked_msg
            record.args = ()  # Limpiar args para evitar re-formateo
        
        return True

    def _mask_sensitive_data(self, message: str) -> str:
        """
        Enmascara datos sensibles en el mensaje usando regex.
        
        Mantiene los primeros 8 caracteres y enmascara el resto con ***
        """
        masked = message
        
        for pattern, group_idx in self.SENSITIVE_PATTERNS:
            def mask_match(match):
                # Obtener el valor sensible
                sensitive_value = match.group(group_idx)
                
                # Enmascarar: mostrar primeros 8 chars (o menos si es más corto)
                if len(sensitive_value) <= 3:
                    masked_value = "***"
                elif len(sensitive_value) <= 8:
                    masked_value = sensitive_value[:3] + "***"
                else:
                    masked_value = sensitive_value[:8] + "***"
                
                # Reconstruir el match reemplazando solo el grupo sensible
                result = match.group(0)
                result = result.replace(sensitive_value, masked_value)
                return result
            
            masked = pattern.sub(mask_match, masked)
        
        return masked


def setup_logger(
    name: str = "rss_digest_bot",
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Configura y retorna un logger para la aplicación.

    Args:
        name: Nombre del logger
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configurado
    """
    from src.config import settings

    # Usar nivel de configuración si no se especifica
    if level is None:
        level = settings.LOG_LEVEL

    # Crear logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Evitar duplicar handlers si ya existen
    if logger.handlers:
        return logger

    # Crear handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Crear formato
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Agregar filtro de datos sensibles
    console_handler.addFilter(SensitiveDataFilter())

    # Agregar handler al logger
    logger.addHandler(console_handler)

    return logger


# Logger principal de la aplicación
logger = setup_logger()


def setup_test_logger(
    test_name: str,
    base_dir: Optional[Path] = None,
    level: str = "DEBUG"
) -> tuple[logging.Logger, Path]:
    """
    Configura logger para tests con múltiples file handlers.
    
    Crea un directorio por ejecución y genera logs en múltiples niveles:
    - debug.log: Todo el detalle (DEBUG)
    - info.log: Flujo general (INFO)
    - warning.log: Solo advertencias (WARNING)
    - error.log: Solo errores (ERROR)
    
    Args:
        test_name: Nombre del test (se usa para crear directorio)
        base_dir: Directorio base donde crear logs (default: ./tests/logs/)
        level: Nivel mínimo de logging (default: DEBUG)
        
    Returns:
        Tupla (logger, log_directory)
    """
    # Directorio de logs con timestamp
    if base_dir is None:
        base_dir = Path.cwd() / "tests" / "logs"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = base_dir / test_name / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Obtener root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Formatos
    detailed_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Filtro de datos sensibles
    sensitive_filter = SensitiveDataFilter()
    
    # 1. Handler DEBUG - Todo
    debug_handler = logging.FileHandler(log_dir / "debug.log")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_format)
    debug_handler.addFilter(sensitive_filter)
    root_logger.addHandler(debug_handler)
    
    # 2. Handler INFO
    info_handler = logging.FileHandler(log_dir / "info.log")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(simple_format)
    info_handler.addFilter(sensitive_filter)
    root_logger.addHandler(info_handler)
    
    # 3. Handler WARNING
    warning_handler = logging.FileHandler(log_dir / "warning.log")
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(detailed_format)
    warning_handler.addFilter(sensitive_filter)
    root_logger.addHandler(warning_handler)
    
    # 4. Handler ERROR
    error_handler = logging.FileHandler(log_dir / "error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_format)
    error_handler.addFilter(sensitive_filter)
    root_logger.addHandler(error_handler)
    
    # 5. Handler CONSOLA
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_format)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    root_logger.info(f"📁 Logs guardados en: {log_dir}")
    
    return root_logger, log_dir

