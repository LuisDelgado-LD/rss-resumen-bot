"""
Cliente para interactuar con la API de TT-RSS (Tiny Tiny RSS).
Maneja autenticación, obtención de artículos, y marcado como leídos.

Nota: Este cliente NO usa HTTPRequestHelper porque:
1. Implementa lógica de reintentos personalizada con delays configurables
2. Ya tiene logging completo según guidelines (request/response/timing/errores)
3. Enmascara datos sensibles específicos (password, sid)
4. Valida errores específicos de la API TT-RSS (status != 0)
"""
import requests
import time
import json
from datetime import datetime, timedelta
from typing import Optional
import logging

from src.config import settings


logger = logging.getLogger(__name__)


class TTRSSClientError(Exception):
    """Excepción base para errores del cliente TT-RSS."""
    pass


class TTRSSAuthError(TTRSSClientError):
    """Error de autenticación con TT-RSS."""
    pass


class TTRSSClient:
    """Cliente para interactuar con la API de TT-RSS."""
    
    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Inicializa el cliente TT-RSS.
        
        Args:
            url: URL de la API de TT-RSS (si no se proporciona, usa settings)
            username: Usuario de TT-RSS (si no se proporciona, usa settings)
            password: Password de TT-RSS (si no se proporciona, usa settings)
        """
        self.url = url or settings.TTRSS_URL
        self.username = username or settings.TTRSS_USER
        self.password = password or settings.TTRSS_PASSWORD
        self.session_id: Optional[str] = None
        
        logger.debug(f"→ TTRSSClient.__init__(url={self.url}, username={self.username})")
        logger.info(f"Cliente TT-RSS inicializado para {self.url}")
    
    def _make_request(
        self,
        operation: str,
        additional_params: Optional[dict] = None,
        retry: bool = True
    ) -> dict:
        """
        Hace una petición a la API de TT-RSS.
        
        Args:
            operation: Operación a ejecutar (ej: "login", "getHeadlines")
            additional_params: Parámetros adicionales para la petición
            retry: Si debe reintentar en caso de error
            
        Returns:
            Respuesta de la API como dict
            
        Raises:
            TTRSSClientError: Si hay error en la petición
        """
        payload = {"op": operation}
        
        # Agregar session_id si está disponible y no es login
        if self.session_id and operation != "login":
            payload["sid"] = self.session_id
        
        # Agregar parámetros adicionales
        if additional_params:
            payload.update(additional_params)
        
        attempts = settings.API_RETRY_ATTEMPTS if retry else 1
        last_error = None
        
        for attempt in range(1, attempts + 1):
            try:
                # Log de request completo (DEBUG)
                logger.debug(f"→ POST {self.url}")
                logger.debug(f"→ Operation: {operation}")
                
                # Enmascarar datos sensibles en el payload
                log_payload = payload.copy()
                if "password" in log_payload:
                    log_payload["password"] = log_payload["password"][:3] + "***"
                if "sid" in log_payload:
                    log_payload["sid"] = log_payload["sid"][:8] + "..."
                logger.debug(f"→ Payload: {json.dumps(log_payload, indent=2)}")
                
                # Hacer request
                start_time = time.time()
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=settings.TTRSS_TIMEOUT_SECONDS
                )
                elapsed = time.time() - start_time
                
                # Log de response (DEBUG)
                logger.debug(f"← Status: {response.status_code} ({elapsed:.3f}s)")
                logger.debug(f"← Body preview: {response.text[:500]}{'...' if len(response.text) > 500 else ''}")
                
                response.raise_for_status()
                
                data = response.json()
                
                # Verificar si la API devolvió error
                if data.get("status") != 0:
                    error_msg = data.get("content", {}).get("error", "Error desconocido")
                    logger.error(f"❌ API error en {operation}: {error_msg}")

                    # Relogin automático cuando la sesión expiró o el bot arrancó sin login
                    if error_msg == "NOT_LOGGED_IN" and operation != "login":
                        logger.warning(
                            f"⚠️  Sesión expirada/ausente en {operation}. "
                            f"Relogueando automáticamente..."
                        )
                        try:
                            new_sid = self._reauthenticate()
                            payload["sid"] = new_sid
                            logger.info(f"✅ Relogin exitoso — reintentando {operation}")
                            continue  # Repetir el intento con la nueva sesión
                        except Exception as reauth_err:
                            logger.error(f"❌ Relogin fallido: {reauth_err}")
                            raise TTRSSClientError(f"API error: {error_msg}")

                    raise TTRSSClientError(f"API error: {error_msg}")
                
                logger.debug(f"← {operation} completado exitosamente en {elapsed:.3f}s")
                return data
                
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < attempts:
                    logger.warning(
                        f"⚠️  Timeout en {operation} (intento {attempt}/{attempts}, "
                        f"reintentando en {settings.API_RETRY_DELAY_SECONDS}s)"
                    )
                else:
                    logger.error(f"❌ Timeout en {operation} después de {attempts} intentos")
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < attempts:
                    logger.warning(
                        f"⚠️  Error de red en {operation}: {e} "
                        f"(intento {attempt}/{attempts}, reintentando en {settings.API_RETRY_DELAY_SECONDS}s)"
                    )
                else:
                    logger.error(f"❌ Error de red en {operation} después de {attempts} intentos: {e}")
                
            except TTRSSClientError as e:
                # Errores de la API no se reintentan
                logger.error(f"❌ Error de API en {operation}: {e}")
                raise
                
            except Exception as e:
                last_error = e
                logger.error(f"❌ Error inesperado en {operation}: {e}", exc_info=True)
                raise TTRSSClientError(f"Error inesperado: {e}")
            
            # Esperar antes del próximo intento
            if attempt < attempts:
                time.sleep(settings.API_RETRY_DELAY_SECONDS)
        
        # Si llegamos aquí, todos los intentos fallaron
        logger.error(f"❌ {operation} falló después de {attempts} intentos: {last_error}")
        raise TTRSSClientError(
            f"Falló después de {attempts} intentos: {last_error}"
        )
    
    def login(self) -> str:
        """
        Autentica con TT-RSS y obtiene un session_id.
        
        Returns:
            Session ID
            
        Raises:
            TTRSSAuthError: Si falla la autenticación
        """
        logger.debug(f"→ login(user={self.username})")
        logger.info("Autenticando con TT-RSS...")
        
        start_time = time.time()
        try:
            data = self._make_request(
                "login",
                {
                    "user": self.username,
                    "password": self.password
                }
            )
            
            self.session_id = data["content"]["session_id"]
            elapsed = time.time() - start_time
            
            logger.debug(f"← login() → session_id={self.session_id[:8]}... ({elapsed:.2f}s)")
            logger.info(f"✅ Autenticación exitosa (session_id: {self.session_id[:8]}...)")
            return self.session_id
            
        except TTRSSClientError as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Autenticación falló después de {elapsed:.2f}s: {e}")
            raise TTRSSAuthError(f"Fallo de autenticación: {e}")
    
    def _reauthenticate(self) -> str:
        """
        Realiza un relogin transparente y actualiza self.session_id.

        Llamado automáticamente por _make_request cuando la API devuelve
        NOT_LOGGED_IN (sesión expirada o bot arrancado sin login previo).

        Returns:
            Nuevo session_id

        Raises:
            TTRSSAuthError: Si el relogin también falla
        """
        logger.debug("→ _reauthenticate()")
        self.session_id = None  # Forzar que _make_request no adjunte sid expirado
        new_sid = self.login()
        logger.debug(f"← _reauthenticate() → session_id={new_sid[:8]}...")
        return new_sid

    def logout(self) -> None:
        """Cierra la sesión con TT-RSS."""
        if not self.session_id:
            logger.debug("→ logout() - sin sesión activa, saltando")
            return
        
        logger.debug(f"→ logout(session_id={self.session_id[:8]}...)")
        
        try:
            self._make_request("logout", retry=False)
            logger.info(f"✅ Sesión cerrada (session_id: {self.session_id[:8]}...)")
        except Exception as e:
            logger.warning(f"⚠️  Error al cerrar sesión: {e}")
        finally:
            self.session_id = None
    
    def get_categories(self) -> list[dict]:
        """
        Obtiene la lista de categorías.
        
        Returns:
            Lista de categorías con sus metadatos
        """
        logger.debug("→ get_categories()")
        logger.info("Obteniendo categorías...")
        
        start_time = time.time()
        data = self._make_request(
            "getCategories",
            {"unread_only": False}
        )
        
        categories = data["content"]
        elapsed = time.time() - start_time
        
        logger.debug(f"← get_categories() → {len(categories)} categorías ({elapsed:.2f}s)")
        logger.debug(f"Primeras 5 categorías: {[c.get('title', 'Sin título') for c in categories[:5]]}")
        logger.info(f"✅ {len(categories)} categorías obtenidas en {elapsed:.2f}s")
        
        return categories
    
    def get_feeds(self) -> list[dict]:
        """
        Obtiene la lista de feeds con información de categoría.
        
        Returns:
            Lista de feeds con metadatos
        """
        logger.debug("→ get_feeds(cat_id=-3)")
        logger.info("Obteniendo feeds...")
        
        start_time = time.time()
        data = self._make_request(
            "getFeeds",
            {
                "cat_id": -3,  # -3 = All feeds
                "unread_only": False
            }
        )
        
        feeds = data["content"]
        elapsed = time.time() - start_time
        
        logger.debug(f"← get_feeds() → {len(feeds)} feeds ({elapsed:.2f}s)")
        logger.debug(f"Primeros 5 feeds: {[f.get('title', 'Sin título')[:40] for f in feeds[:5]]}")
        logger.info(f"✅ {len(feeds)} feeds obtenidos en {elapsed:.2f}s")
        
        return feeds
    
    def build_feed_to_category_map(
        self,
        feeds: list[dict],
        categories: list[dict]
    ) -> dict:
        """
        Construye un mapeo de feed_id → información de categoría.
        
        Args:
            feeds: Lista de feeds
            categories: Lista de categorías
            
        Returns:
            Dict con mapeo feed_id → {cat_id, cat_name, feed_title}
        """
        logger.debug(f"→ build_feed_to_category_map(feeds={len(feeds)}, categories={len(categories)})")
        
        # Crear dict de categorías para lookup rápido
        cat_dict = {cat['id']: cat['title'] for cat in categories}
        logger.debug(f"Categorías en dict: {len(cat_dict)}")
        
        # Construir mapeo
        feed_map = {}
        for feed in feeds:
            feed_id = feed.get('id')
            cat_id = feed.get('cat_id')
            
            if feed_id and cat_id is not None:
                cat_name = cat_dict.get(cat_id, f"Categoría desconocida ({cat_id})")
                feed_map[feed_id] = {
                    'cat_id': cat_id,
                    'cat_name': cat_name,
                    'feed_title': feed.get('title', 'Sin título')
                }
        
        logger.debug(f"← build_feed_to_category_map() → {len(feed_map)} feeds mapeados")
        logger.info(f"✅ Mapeados {len(feed_map)} feeds a categorías")
        return feed_map
    
    def get_headlines(
        self,
        feed_id: int = -4,
        view_mode: str = "unread",
        show_content: bool = True,
        limit: int = 200,
        skip: int = 0,
        since_hours: Optional[int] = None
    ) -> list[dict]:
        """
        Obtiene artículos (headlines) de TT-RSS.
        
        Args:
            feed_id: ID del feed (-4 = todos los artículos)
            view_mode: "unread", "all", etc.
            show_content: Si incluir el contenido completo
            limit: Número máximo de artículos a obtener
            skip: Número de artículos a saltar (para paginación)
            since_hours: Filtrar artículos de las últimas X horas
            
        Returns:
            Lista de artículos
        """
        logger.debug(
            f"→ get_headlines(feed_id={feed_id}, view_mode={view_mode}, "
            f"limit={limit}, skip={skip}, since_hours={since_hours})"
        )
        
        params = {
            "feed_id": feed_id,
            "view_mode": view_mode,
            "show_content": show_content,
            "limit": limit,
            "skip": skip
        }
        
        # Agregar filtro de fecha si se especifica
        if since_hours:
            since_timestamp = int(
                (datetime.now() - timedelta(hours=since_hours)).timestamp()
            )
            params["since_id"] = 0  # Necesario para que funcione el filtro
            params["since_timestamp"] = since_timestamp
            logger.debug(f"Filtro de fecha: desde {datetime.fromtimestamp(since_timestamp)}")
        
        start_time = time.time()
        data = self._make_request("getHeadlines", params)
        articles = data["content"]
        elapsed = time.time() - start_time
        
        logger.debug(f"← get_headlines() → {len(articles)} artículos ({elapsed:.2f}s)")
        if articles:
            logger.debug(f"Primeros 3 IDs: {[a.get('id') for a in articles[:3]]}")
        
        return articles
    
    def get_all_unread_articles(
        self,
        max_articles: Optional[int] = None,
        since_hours: Optional[int] = None
    ) -> tuple[list[dict], bool]:
        """
        Obtiene TODOS los artículos no leídos con paginación.
        
        Args:
            max_articles: Límite máximo de artículos (None = sin límite)
            since_hours: Filtrar artículos de las últimas X horas
            
        Returns:
            Tupla (lista_artículos, truncado)
            - lista_artículos: Artículos obtenidos
            - truncado: True si se alcanzó el límite máximo
        """
        logger.debug(
            f"→ get_all_unread_articles(max_articles={max_articles}, since_hours={since_hours})"
        )
        logger.info(
            f"Obteniendo artículos no leídos "
            f"(límite: {max_articles or 'sin límite'}, "
            f"últimas {since_hours or 'todas'}h)"
        )
        
        start_time = time.time()
        all_articles = []
        skip = 0
        batch_size = 200
        truncated = False
        
        # Calcular timestamp de corte si hay filtro
        cutoff_timestamp = None
        if since_hours:
            cutoff_timestamp = int(
                (datetime.now() - timedelta(hours=since_hours)).timestamp()
            )
            logger.debug(f"Filtro de fecha: artículos desde {datetime.fromtimestamp(cutoff_timestamp)}")
        
        while True:
            # Verificar si alcanzamos el límite
            if max_articles and len(all_articles) >= max_articles:
                truncated = True
                logger.warning(
                    f"⚠️  Límite de {max_articles} artículos alcanzado, "
                    f"puede haber más artículos disponibles"
                )
                break
            
            # Calcular cuántos artículos pedir en este lote
            if max_articles:
                remaining = max_articles - len(all_articles)
                current_batch_size = min(batch_size, remaining)
            else:
                current_batch_size = batch_size
            
            logger.debug(f"Solicitando lote: limit={current_batch_size}, skip={skip}")
            
            # Obtener lote (SIN filtro de fecha en la API)
            batch = self.get_headlines(
                feed_id=-4,
                view_mode="unread",
                show_content=True,
                limit=current_batch_size,
                skip=skip,
                since_hours=None  # NO usar el filtro de API (no funciona)
            )
            
            if len(batch) == 0:
                # No hay más artículos
                logger.debug("No hay más artículos disponibles")
                break
            
            # FILTRAR por fecha AQUÍ (post-procesamiento)
            if cutoff_timestamp:
                original_count = len(batch)
                filtered_batch = []
                for article in batch:
                    article_timestamp = article.get('updated', 0)
                    if article_timestamp >= cutoff_timestamp:
                        filtered_batch.append(article)
                
                discarded = original_count - len(filtered_batch)
                if discarded > 0:
                    logger.debug(
                        f"Lote filtrado por fecha: {len(filtered_batch)}/{original_count} artículos "
                        f"(descartados {discarded} más antiguos)"
                    )
                batch = filtered_batch
            
            all_articles.extend(batch)
            logger.info(f"   Lote de {len(batch)} artículos (total: {len(all_articles)})")
            
            # Si el lote original es menor que el tamaño solicitado, ya no hay más
            if len(batch) < current_batch_size:
                logger.debug("Lote incompleto, no hay más artículos")
                break
            
            skip += batch_size  # Incrementar skip por el tamaño original, no el filtrado
        
        elapsed = time.time() - start_time
        logger.debug(f"← get_all_unread_articles() → {len(all_articles)} artículos ({elapsed:.2f}s)")
        logger.info(
            f"✅ Total: {len(all_articles)} artículos obtenidos en {elapsed:.2f}s "
            f"{'(TRUNCADO)' if truncated else ''}"
        )
        
        return all_articles, truncated
    
    def get_article_by_id(self, article_id: int) -> Optional[dict]:
        """
        Obtiene un artículo específico por su ID.
        
        Args:
            article_id: ID del artículo
            
        Returns:
            Dict con datos del artículo o None si no existe
        """
        logger.debug(f"→ get_article_by_id(id={article_id})")
        
        try:
            # Usar getHeadlines con limite 1 y view_mode=all
            articles = self.get_headlines(
                feed_id=-4,  # Todos los feeds
                view_mode="all",  # Incluir leídos y no leídos
                show_content=True,
                limit=1,
                skip=0
            )
            
            # Buscar el artículo específico
            for article in articles:
                if article.get('id') == article_id:
                    logger.debug(f"← get_article_by_id() → artículo encontrado")
                    return article
            
            # Si no se encontró, intentar con API directa
            data = self._make_request(
                "getArticle",
                {"article_id": article_id}
            )
            
            articles = data.get("content", [])
            if articles:
                logger.debug(f"← get_article_by_id() → artículo encontrado (API directa)")
                return articles[0]
            
            logger.warning(f"Artículo {article_id} no encontrado")
            logger.debug(f"← get_article_by_id() → None")
            return None
            
        except TTRSSClientError as e:
            logger.error(f"Error obteniendo artículo {article_id}: {e}")
            logger.debug(f"← get_article_by_id() → None (error)")
            return None
    
    def mark_articles_as_read(self, article_ids: list[int]) -> None:
        """
        Marca artículos como leídos en TT-RSS.
        
        Args:
            article_ids: Lista de IDs de artículos a marcar
        """
        if not article_ids:
            logger.debug("→ mark_articles_as_read([]) - lista vacía, saltando")
            logger.info("No hay artículos para marcar como leídos")
            return
        
        logger.debug(f"→ mark_articles_as_read({len(article_ids)} IDs)")
        logger.debug(f"Primeros 10 IDs: {article_ids[:10]}")
        logger.info(f"Marcando {len(article_ids)} artículos como leídos...")
        
        # TT-RSS acepta IDs como string separado por comas
        ids_str = ",".join(str(id) for id in article_ids)
        
        try:
            start_time = time.time()
            self._make_request(
                "updateArticle",
                {
                    "article_ids": ids_str,
                    "mode": 0,  # 0 = marcar como leído
                    "field": 2  # 2 = campo "unread"
                }
            )
            elapsed = time.time() - start_time
            
            logger.debug(f"← mark_articles_as_read() completado en {elapsed:.2f}s")
            logger.info(f"✅ {len(article_ids)} artículos marcados como leídos")
            
        except TTRSSClientError as e:
            logger.error(f"❌ Error marcando artículos como leídos: {e}", exc_info=True)
            raise
    
    def __enter__(self):
        """Context manager: login automático."""
        logger.debug("→ __enter__() - iniciando context manager")
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: logout automático."""
        logger.debug(f"→ __exit__(exc_type={exc_type})")
        if exc_type:
            logger.warning(f"⚠️  Saliendo del context manager con excepción: {exc_type.__name__}")
        self.logout()