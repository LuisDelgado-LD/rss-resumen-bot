"""
Cliente para interactuar con Wallabag API v2.
Permite guardar artículos con tags automáticos.
"""
import time
from typing import Optional, List, Dict, Any
from src.config import settings
from src.utils import logger
from src.utils.http_helper import HTTPRequestHelper


class WallabagClient:
    """Cliente para interactuar con la API de Wallabag."""
    
    def __init__(self):
        """Inicializa el cliente de Wallabag."""
        logger.debug("→ WallabagClient.__init__()")
        
        self.base_url = settings.WALLABAG_URL.rstrip('/')
        self.client_id = settings.WALLABAG_CLIENT_ID
        self.client_secret = settings.WALLABAG_CLIENT_SECRET
        self.username = settings.WALLABAG_USERNAME
        self.password = settings.WALLABAG_PASSWORD
        self.default_tag = settings.WALLABAG_DEFAULT_TAG
        
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        
        logger.debug(f"Wallabag URL: {self.base_url}")
        logger.debug(f"Default tag: '{self.default_tag}' (vacío={not self.default_tag})")
        logger.debug("← WallabagClient.__init__()")
    
    def _get_access_token(self) -> bool:
        """
        Obtiene un access token usando OAuth2.
        
        Returns:
            True si se obtuvo el token exitosamente, False en caso contrario
        """
        logger.debug("→ _get_access_token()")
        
        # Si ya tenemos un token válido, no hacer nada
        if self.access_token and time.time() < self.token_expires_at:
            logger.debug(f"Token válido hasta {self.token_expires_at}")
            logger.debug("← _get_access_token() → True (cached)")
            return True
        
        url = f"{self.base_url}/oauth/v2/token"
        
        data = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password
        }
        
        try:
            response = HTTPRequestHelper.post(
                url=url,
                data=data,
                timeout=10,
                context="Wallabag OAuth token"
            )
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            
            # Guardar cuándo expira (con margen de 5 minutos)
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = time.time() + expires_in - 300
            
            logger.debug(f"Token obtenido, expira en {expires_in}s")
            logger.debug("← _get_access_token() → True")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obteniendo token de Wallabag: {e}")
            logger.debug("← _get_access_token() → False")
            return False
    
    def add_entry(
        self,
        url: str,
        title: str,
        tags: Optional[List[str]] = None,
        starred: bool = False,
        archived: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Añade un artículo a Wallabag.
        
        Args:
            url: URL del artículo
            title: Título del artículo
            tags: Lista de tags (se añade default_tag si existe)
            starred: Si marcar como favorito
            archived: Si marcar como archivado
            
        Returns:
            Dict con datos del entry creado, o None si falla
        """
        logger.debug(f"→ add_entry(url={url[:50]}..., title={title[:30]}...)")
        
        # Obtener token
        if not self._get_access_token():
            logger.error("No se pudo obtener access token")
            logger.debug("← add_entry() → None")
            return None
        
        # Preparar tags
        final_tags = tags[:] if tags else []
        
        # Añadir default tag si está configurado
        if self.default_tag and self.default_tag not in final_tags:
            final_tags.append(self.default_tag)
        
        # API endpoint
        api_url = f"{self.base_url}/api/entries.json"
        
        # Headers
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Payload
        payload = {
            'url': url,
            'title': title,
            'starred': 1 if starred else 0,
            'archive': 1 if archived else 0
        }
        
        # Añadir tags si existen
        if final_tags:
            payload['tags'] = ','.join(final_tags)
            logger.debug(f"Tags a aplicar: {final_tags}")
        
        try:
            logger.info(f"Guardando en Wallabag: {title}")
            logger.debug(f"Payload: {payload}")
            
            response = HTTPRequestHelper.post(
                url=api_url,
                json_data=payload,
                headers=headers,
                timeout=15,
                context=f"Wallabag add entry: {title[:50]}"
            )
            
            entry_data = response.json()
            
            entry_id = entry_data.get('id')
            created_at = entry_data.get('created_at')
            updated_at = entry_data.get('updated_at')
            
            # Detectar si el artículo ya existía
            # Wallabag retorna el artículo existente si la URL ya está guardada
            is_duplicate = created_at and updated_at and created_at != updated_at
            
            if is_duplicate:
                logger.info(f"ℹ️  Artículo ya existía en Wallabag (ID: {entry_id})")
                entry_data['_is_duplicate'] = True
            else:
                logger.info(f"✅ Artículo guardado en Wallabag (ID: {entry_id})")
                entry_data['_is_duplicate'] = False
            
            logger.debug(f"← add_entry() → entry_id={entry_id}")
            
            return entry_data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limit en Wallabag: {e}")
            else:
                logger.error(f"Error HTTP guardando en Wallabag: {e}")
                logger.debug(f"Response: {e.response.text if e.response else 'N/A'}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red guardando en Wallabag: {e}")
        except Exception as e:
            logger.error(f"Error inesperado guardando en Wallabag: {e}")
        
        logger.debug("← add_entry() → None")
        return None
    
    def add_tags_to_entry(self, entry_id: int, tags: List[str]) -> bool:
        """
        Añade tags a un entry existente.
        
        Args:
            entry_id: ID del entry en Wallabag
            tags: Lista de tags a añadir
            
        Returns:
            True si se añadieron los tags, False en caso contrario
        """
        logger.debug(f"→ add_tags_to_entry(entry_id={entry_id}, tags={tags})")
        
        if not tags:
            logger.debug("No hay tags para añadir")
            logger.debug("← add_tags_to_entry() → True")
            return True
        
        # Obtener token
        if not self._get_access_token():
            logger.error("No se pudo obtener access token")
            logger.debug("← add_tags_to_entry() → False")
            return False
        
        # API endpoint
        api_url = f"{self.base_url}/api/entries/{entry_id}/tags.json"
        
        # Headers
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Payload
        payload = {
            'tags': ','.join(tags)
        }
        
        try:
            logger.debug(f"Tags: {tags}")
            
            response = HTTPRequestHelper.post(
                url=api_url,
                json_data=payload,
                headers=headers,
                timeout=10,
                context=f"Wallabag add tags: entry {entry_id}"
            )
            
            logger.info(f"✅ Tags añadidos al entry {entry_id}: {tags}")
            logger.debug("← add_tags_to_entry() → True")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error añadiendo tags: {e}")
            logger.debug("← add_tags_to_entry() → False")
            return False
    
    def get_entry_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Busca un entry por URL.
        
        Args:
            url: URL a buscar
            
        Returns:
            Dict con datos del entry si existe, None si no
        """
        logger.debug(f"→ get_entry_by_url(url={url[:50]}...)")
        
        # Obtener token
        if not self._get_access_token():
            logger.error("No se pudo obtener access token")
            logger.debug("← get_entry_by_url() → None")
            return None
        
        # API endpoint
        api_url = f"{self.base_url}/api/entries/exists.json"
        
        # Headers
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        # Params
        params = {
            'url': url
        }
        
        try:
            response = HTTPRequestHelper.get(
                url=api_url,
                params=params,
                headers=headers,
                timeout=10,
                context="Wallabag check entry exists"
            )
            
            data = response.json()
            
            exists = data.get('exists', False)
            
            if exists:
                logger.debug(f"Entry existe en Wallabag")
                logger.debug("← get_entry_by_url() → entry_data")
                return data
            else:
                logger.debug("Entry no existe en Wallabag")
                logger.debug("← get_entry_by_url() → None")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error buscando entry: {e}")
            logger.debug("← get_entry_by_url() → None")
            return None
    
    def is_configured(self) -> bool:
        """
        Verifica si Wallabag está configurado correctamente.
        
        Returns:
            True si está configurado, False en caso contrario
        """
        return all([
            self.base_url != "https://tu-instancia-wallabag.com",
            self.client_id != "tu_client_id",
            self.client_secret != "tu_client_secret",
            self.username != "tu_usuario",
            self.password != "tu_password"
        ])
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión con Wallabag.
        
        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        logger.debug("→ test_connection()")
        logger.info("Probando conexión con Wallabag...")
        
        if not self.is_configured():
            logger.warning("Wallabag no está configurado (credenciales por defecto)")
            logger.debug("← test_connection() → False")
            return False
        
        # Intentar obtener token
        if self._get_access_token():
            logger.info("✅ Conexión con Wallabag exitosa")
            logger.debug("← test_connection() → True")
            return True
        else:
            logger.error("❌ No se pudo conectar con Wallabag")
            logger.debug("← test_connection() → False")
            return False
