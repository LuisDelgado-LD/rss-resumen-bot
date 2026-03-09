"""
Configuración central de la aplicación.
Maneja todas las variables de entorno y validaciones.
"""
import os 
import json
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Buscar .env en el directorio raíz del proyecto
# Este archivo está en src/config/settings.py
# Subimos 2 niveles: src/config/ -> src/ -> raíz/
project_root = Path(__file__).parent.parent.parent
dotenv_path = project_root / '.env'

# Cargar variables de entorno desde .env
load_dotenv(dotenv_path)


def _clean_env_value(key: str, default: str = "") -> str:
    """
    Obtiene una variable de entorno y limpia comentarios inline y espacios.
    
    Args:
        key: Nombre de la variable de entorno
        default: Valor por defecto si no existe o queda vacía
        
    Returns:
        Valor limpio o default
        
    Examples:
        WALLABAG_DEFAULT_TAG=  # comentario  -> ""
        WALLABAG_DEFAULT_TAG=rss  # comentario -> "rss"
        WALLABAG_DEFAULT_TAG=rss -> "rss"
    """
    value = os.getenv(key, default)
    
    # Eliminar comentarios inline (todo después de #)
    if '#' in value:
        value = value.split('#')[0]
    
    # Limpiar espacios
    value = value.strip()
    
    # Si quedó vacío, usar default
    if not value:
        return default
    
    return value


class Settings:
    """Clase para gestionar todas las configuraciones de la aplicación."""

    def __init__(self):
        """Inicializa y carga configuración dinámica."""
        self._topics_map: Optional[dict] = None

    # TT-RSS
    TTRSS_URL: str = _clean_env_value("TTRSS_URL", "")
    TTRSS_USER: str = _clean_env_value("TTRSS_USER", "")
    TTRSS_PASSWORD: str = _clean_env_value("TTRSS_PASSWORD", "")

    # Google AI Studio
    GOOGLE_API_KEY: str = _clean_env_value("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = _clean_env_value("GOOGLE_MODEL", "gemini-1.5-flash")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = _clean_env_value("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = _clean_env_value("TELEGRAM_CHAT_ID", "")
    TELEGRAM_MODE: str = _clean_env_value("TELEGRAM_MODE", "chat")  # "chat" o "supergroup"
    
    # Telegram Rate Limiting
    TELEGRAM_MESSAGE_DELAY: float = float(_clean_env_value("TELEGRAM_MESSAGE_DELAY", "1.5"))
    TELEGRAM_CATEGORY_DELAY: float = float(_clean_env_value("TELEGRAM_CATEGORY_DELAY", "2.0"))

    # Wallabag
    WALLABAG_URL: str = _clean_env_value("WALLABAG_URL", "")
    WALLABAG_CLIENT_ID: str = _clean_env_value("WALLABAG_CLIENT_ID", "")
    WALLABAG_CLIENT_SECRET: str = _clean_env_value("WALLABAG_CLIENT_SECRET", "")
    WALLABAG_USERNAME: str = _clean_env_value("WALLABAG_USERNAME", "")
    WALLABAG_PASSWORD: str = _clean_env_value("WALLABAG_PASSWORD", "")
    WALLABAG_DEFAULT_TAG: str = _clean_env_value("WALLABAG_DEFAULT_TAG", "")

    # Configuración General
    ARTICLES_MAX_AGE_HOURS: int = int(_clean_env_value("ARTICLES_MAX_AGE_HOURS", "24"))
    LOG_LEVEL: str = _clean_env_value("LOG_LEVEL", "INFO")
    TIMEZONE: str = _clean_env_value("TIMEZONE", "UTC")
    MAX_ARTICLES_PER_RUN: int = int(_clean_env_value("MAX_ARTICLES_PER_RUN", "500"))
    
    # API retry configuration
    API_RETRY_ATTEMPTS: int = int(_clean_env_value("API_RETRY_ATTEMPTS", "3"))
    API_RETRY_DELAY_SECONDS: int = int(_clean_env_value("API_RETRY_DELAY_SECONDS", "5"))
    TTRSS_TIMEOUT_SECONDS: int = int(_clean_env_value("TTRSS_TIMEOUT_SECONDS", "60"))
    
    # Scraping configuration
    SCRAPING_ENABLED: bool = _clean_env_value("SCRAPING_ENABLED", "true").lower() == "true"
    SCRAPING_TIMEOUT_SECONDS: int = int(_clean_env_value("SCRAPING_TIMEOUT_SECONDS", "5"))
    SCRAPING_DELAY_SAME_DOMAIN_SECONDS: int = int(_clean_env_value("SCRAPING_DELAY_SAME_DOMAIN_SECONDS", "2"))
    SCRAPING_MAX_PARALLEL_DOMAINS: int = int(_clean_env_value("SCRAPING_MAX_PARALLEL_DOMAINS", "10"))
    SCRAPING_MIN_WORDS: int = int(_clean_env_value("SCRAPING_MIN_WORDS", "100"))
    SCRAPING_CACHE_ENABLED: bool = _clean_env_value("SCRAPING_CACHE_ENABLED", "true").lower() == "true"
    SCRAPING_CACHE_RETRY_AFTER_DAYS: int = int(_clean_env_value("SCRAPING_CACHE_RETRY_AFTER_DAYS", "7"))
    SCRAPING_CACHE_MAX_RETRIES: int = int(_clean_env_value("SCRAPING_CACHE_MAX_RETRIES", "1"))
    
    # User-Agent configuration (fallback si detecta bloqueo)
    SCRAPING_USER_AGENT_BOT: str = _clean_env_value(
        "SCRAPING_USER_AGENT_BOT",
        "Mozilla/5.0 (compatible; RSS-Digest-Bot/1.0)"
    )
    SCRAPING_USER_AGENT_BROWSER: str = _clean_env_value(
        "SCRAPING_USER_AGENT_BROWSER",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    SCRAPING_UA_FALLBACK_ENABLED: bool = _clean_env_value("SCRAPING_UA_FALLBACK_ENABLED", "true").lower() == "true"

    # Configuración de Resumen
    MAX_SUMMARY_TOKENS: int = int(_clean_env_value("MAX_SUMMARY_TOKENS", "2000"))
    LLM_TEMPERATURE: float = float(_clean_env_value("LLM_TEMPERATURE", "0.3"))

    def validate(self) -> tuple[bool, list[str]]:
        """
        Valida que todas las configuraciones requeridas estén presentes.

        Returns:
            Tupla con (es_válido, lista_de_errores)
        """
        errors = []

        # Validar TT-RSS
        if not self.TTRSS_URL:
            errors.append("TTRSS_URL no está configurada")
        if not self.TTRSS_USER:
            errors.append("TTRSS_USER no está configurado")
        if not self.TTRSS_PASSWORD:
            errors.append("TTRSS_PASSWORD no está configurada")

        # Validar Google AI
        if not self.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY no está configurada")

        # Validar Telegram
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN no está configurado")
        if not self.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID no está configurado")
        
        # Validar modo de Telegram
        if self.TELEGRAM_MODE not in ["chat", "supergroup"]:
            errors.append(f"TELEGRAM_MODE debe ser 'chat' o 'supergroup', actual: {self.TELEGRAM_MODE}")
        
        # Si es supergroup, validar topics.json
        if self.TELEGRAM_MODE == "supergroup":
            topics_validation = self._validate_topics_file()
            if not topics_validation[0]:
                errors.extend(topics_validation[1])

        # Validar Wallabag
        if not self.WALLABAG_URL:
            errors.append("WALLABAG_URL no está configurada")
        if not self.WALLABAG_CLIENT_ID:
            errors.append("WALLABAG_CLIENT_ID no está configurado")
        if not self.WALLABAG_CLIENT_SECRET:
            errors.append("WALLABAG_CLIENT_SECRET no está configurado")
        if not self.WALLABAG_USERNAME:
            errors.append("WALLABAG_USERNAME no está configurado")
        if not self.WALLABAG_PASSWORD:
            errors.append("WALLABAG_PASSWORD no está configurada")

        # Validar rangos
        if self.ARTICLES_MAX_AGE_HOURS <= 0:
            errors.append("ARTICLES_MAX_AGE_HOURS debe ser mayor a 0")
        if self.MAX_ARTICLES_PER_RUN <= 0:
            errors.append("MAX_ARTICLES_PER_RUN debe ser mayor a 0")
        if self.API_RETRY_ATTEMPTS < 0:
            errors.append("API_RETRY_ATTEMPTS debe ser mayor o igual a 0")
        if self.API_RETRY_DELAY_SECONDS < 0:
            errors.append("API_RETRY_DELAY_SECONDS debe ser mayor o igual a 0")
        if self.TTRSS_TIMEOUT_SECONDS <= 0:
            errors.append("TTRSS_TIMEOUT_SECONDS debe ser mayor a 0")
        if self.TELEGRAM_MESSAGE_DELAY < 0:
            errors.append("TELEGRAM_MESSAGE_DELAY debe ser mayor o igual a 0")
        if self.TELEGRAM_CATEGORY_DELAY < 0:
            errors.append("TELEGRAM_CATEGORY_DELAY debe ser mayor o igual a 0")
        if self.SCRAPING_TIMEOUT_SECONDS <= 0:
            errors.append("SCRAPING_TIMEOUT_SECONDS debe ser mayor a 0")
        if self.SCRAPING_DELAY_SAME_DOMAIN_SECONDS < 0:
            errors.append("SCRAPING_DELAY_SAME_DOMAIN_SECONDS debe ser mayor o igual a 0")
        if self.SCRAPING_MAX_PARALLEL_DOMAINS <= 0:
            errors.append("SCRAPING_MAX_PARALLEL_DOMAINS debe ser mayor a 0")
        if self.SCRAPING_MIN_WORDS <= 0:
            errors.append("SCRAPING_MIN_WORDS debe ser mayor a 0")
        if self.SCRAPING_CACHE_RETRY_AFTER_DAYS < 0:
            errors.append("SCRAPING_CACHE_RETRY_AFTER_DAYS debe ser mayor o igual a 0")
        if self.SCRAPING_CACHE_MAX_RETRIES < 0:
            errors.append("SCRAPING_CACHE_MAX_RETRIES debe ser mayor o igual a 0")
        if not 0.0 <= self.LLM_TEMPERATURE <= 1.0:
            errors.append("LLM_TEMPERATURE debe estar entre 0.0 y 1.0")

        return len(errors) == 0, errors

    def _validate_topics_file(self) -> tuple[bool, list[str]]:
        """
        Valida que el archivo topics.json exista y sea válido.
        
        Returns:
            Tupla con (es_válido, lista_de_errores)
        """
        errors = []
        topics_path = project_root / "utils" / "topics.json"
        
        if not topics_path.exists():
            errors.append(f"Archivo topics.json no encontrado en: {topics_path}")
            return False, errors
        
        try:
            with open(topics_path, 'r', encoding='utf-8') as f:
                topics_data = json.load(f)
            
            # Validar estructura
            if "categories" not in topics_data:
                errors.append("topics.json debe contener la clave 'categories'")
                return False, errors
            
            categories = topics_data["categories"]
            
            if not isinstance(categories, dict):
                errors.append("'categories' en topics.json debe ser un diccionario")
                return False, errors
            
            if len(categories) == 0:
                errors.append("'categories' en topics.json está vacío")
                return False, errors
            
            # Validar que todos los topic_id sean enteros
            for category, topic_id in categories.items():
                if not isinstance(topic_id, int):
                    errors.append(f"topic_id para '{category}' debe ser un entero, actual: {type(topic_id).__name__}")
            
            if errors:
                return False, errors
            
            # Cachear el mapeo
            self._topics_map = categories
            return True, []
            
        except json.JSONDecodeError as e:
            errors.append(f"topics.json tiene JSON inválido: {e}")
            return False, errors
        except Exception as e:
            errors.append(f"Error leyendo topics.json: {e}")
            return False, errors

    def get_topics_map(self) -> dict[str, int]:
        """
        Retorna el mapeo de categorías a topic_id.
        Solo disponible si TELEGRAM_MODE es 'supergroup'.
        
        Returns:
            Dict con categoría -> topic_id
        
        Raises:
            RuntimeError: Si no está en modo supergroup o el archivo no es válido
        """
        if self.TELEGRAM_MODE != "supergroup":
            raise RuntimeError(f"get_topics_map() solo disponible en modo 'supergroup', modo actual: {self.TELEGRAM_MODE}")
        
        # Si ya está cacheado, retornar
        if self._topics_map is not None:
            return self._topics_map
        
        # Cargar y validar
        is_valid, errors = self._validate_topics_file()
        if not is_valid:
            raise RuntimeError(f"topics.json inválido: {', '.join(errors)}")
        
        return self._topics_map

    def get_masked_config(self) -> dict:
        """
        Retorna la configuración con valores sensibles enmascarados.
        Útil para logging seguro.
        """
        return {
            "TTRSS_URL": self.TTRSS_URL,
            "TTRSS_USER": self.TTRSS_USER,
            "TTRSS_PASSWORD": "***" if self.TTRSS_PASSWORD else "",
            "GOOGLE_API_KEY": "***" if self.GOOGLE_API_KEY else "",
            "GOOGLE_MODEL": self.GOOGLE_MODEL,
            "TELEGRAM_BOT_TOKEN": "***" if self.TELEGRAM_BOT_TOKEN else "",
            "TELEGRAM_CHAT_ID": self.TELEGRAM_CHAT_ID,
            "TELEGRAM_MODE": self.TELEGRAM_MODE,
            "WALLABAG_URL": self.WALLABAG_URL,
            "WALLABAG_USERNAME": self.WALLABAG_USERNAME,
            "ARTICLES_MAX_AGE_HOURS": self.ARTICLES_MAX_AGE_HOURS,
            "LOG_LEVEL": self.LOG_LEVEL,
            "TIMEZONE": self.TIMEZONE,
            "MAX_ARTICLES_PER_RUN": self.MAX_ARTICLES_PER_RUN,
            "API_RETRY_ATTEMPTS": self.API_RETRY_ATTEMPTS,
            "API_RETRY_DELAY_SECONDS": self.API_RETRY_DELAY_SECONDS,
            "TTRSS_TIMEOUT_SECONDS": self.TTRSS_TIMEOUT_SECONDS,
            "MAX_SUMMARY_TOKENS": self.MAX_SUMMARY_TOKENS,
            "LLM_TEMPERATURE": self.LLM_TEMPERATURE,
            "SCRAPING_ENABLED": self.SCRAPING_ENABLED,
            "SCRAPING_USER_AGENT_BOT": self.SCRAPING_USER_AGENT_BOT,
            "SCRAPING_USER_AGENT_BROWSER": self.SCRAPING_USER_AGENT_BROWSER[:50] + "...",
            "SCRAPING_UA_FALLBACK_ENABLED": self.SCRAPING_UA_FALLBACK_ENABLED,
        }


# Instancia global de configuración
settings = Settings()
