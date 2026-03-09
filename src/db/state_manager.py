"""
Gestor de estado persistente para el bot de Telegram.
Maneja el mapeo de mensajes a artículos y tracking de acciones del usuario.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class StateManager:
    """
    Gestiona el estado persistente del bot usando archivos JSON.
    
    Tracks:
    - message_id → article_ids: Mapeo de mensajes enviados a artículos
    - excluded_articles: Artículos marcados con 🚫 (excluir del batch)
    - marked_articles: Artículos marcados con ❤️ (ya leídos individualmente)
    """
    
    def __init__(self, state_dir: Optional[Path] = None):
        """
        Inicializa el gestor de estado.
        
        Args:
            state_dir: Directorio donde guardar archivos de estado (default: ./state/)
        """
        logger.debug(f"→ StateManager.__init__(state_dir={state_dir})")
        
        if state_dir is None:
            state_dir = Path.cwd() / "state"
        
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Rutas de archivos
        self.message_map_file = self.state_dir / "message_map.json"
        self.excluded_file = self.state_dir / "excluded_articles.json"
        self.marked_file = self.state_dir / "marked_articles.json"
        self.article_urls_file = self.state_dir / "article_urls.json"
        logger.info(f"StateManager inicializado en: {self.state_dir}")

    def reload_from_disk(self):
        # El método `reload_from_disk` ha sido eliminado: cada operación
        # ahora lee/escribe directamente desde/hacia disco.
        raise NotImplementedError("reload_from_disk() was removed; StateManager reads from disk per-call")

    def _load_json(self, file_path: Path, default: any) -> any:
        """
        Carga un archivo JSON.
        
        Args:
            file_path: Ruta al archivo
            default: Valor por defecto si el archivo no existe
            
        Returns:
            Datos cargados o default
        """
        logger.debug(f"→ _load_json(file={file_path.name})")
        start_time = time.time()
        
        if not file_path.exists():
            logger.debug(f"Archivo {file_path.name} no existe, usando default")
            logger.debug(f"← _load_json() → default ({time.time() - start_time:.3f}s)")
            return default
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logger.debug(f"Archivo {file_path.name} vacío, usando default")
                    return default
                
                data = json.loads(content)
                elapsed = time.time() - start_time
                
                logger.debug(f"← _load_json() → {len(data)} items ({elapsed:.3f}s)")
                logger.info(f"✅ Cargado {file_path.name}: {len(data)} items")
                return data
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON inválido en {file_path.name}: {e}")
            logger.warning(f"⚠️  Usando default para {file_path.name}")
            return default
        except Exception as e:
            logger.error(f"❌ Error cargando {file_path.name}: {type(e).__name__}: {e}", exc_info=True)
            logger.warning(f"⚠️  Usando default para {file_path.name}")
            return default
    
    def _save_json(self, file_path: Path, data: any):
        """
        Guarda datos en un archivo JSON.
        
        Args:
            file_path: Ruta al archivo
            data: Datos a guardar
        """
        logger.debug(f"→ _save_json(file={file_path.name}, items={len(data) if isinstance(data, (list, dict)) else '?'})")
        start_time = time.time()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            elapsed = time.time() - start_time
            logger.debug(f"← _save_json() → guardado ({elapsed:.3f}s)")
            logger.info(f"✅ Guardado {file_path.name}: {len(data) if isinstance(data, (list, dict)) else '?'} items")
            
        except Exception as e:
            logger.error(f"❌ Error guardando {file_path.name}: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    def save_message_mapping(
        self,
        message_id: int,
        article_ids: list[int],
        category: str,
        timestamp: Optional[datetime] = None
    ):
        """
        Guarda el mapeo de un mensaje a sus artículos.
        
        Args:
            message_id: ID del mensaje de Telegram
            article_ids: Lista de IDs de artículos en el mensaje
            category: Categoría de los artículos
            timestamp: Timestamp del mensaje (default: ahora)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        logger.debug(f"→ save_message_mapping(msg={message_id}, articles={len(article_ids)}, cat={category})")

        # Cargar el mapa actual desde disco
        message_map = self._load_json(self.message_map_file, {})

        # Convertir a string para JSON (JSON keys deben ser strings)
        key = str(message_id)

        message_map[key] = {
            "article_ids": article_ids,
            "category": category,
            "timestamp": timestamp.isoformat()
        }

        self._save_json(self.message_map_file, message_map)

        logger.debug(f"← save_message_mapping() → guardado")
        logger.info(f"✅ Mapeo guardado: msg {message_id} → {len(article_ids)} artículos ({category})")
    
    def get_articles_by_message(self, message_id: int) -> Optional[list[int]]:
        """
        Obtiene los IDs de artículos asociados a un mensaje.
        
        Args:
            message_id: ID del mensaje de Telegram
            
        Returns:
            Lista de IDs de artículos o None si no existe
        """
        logger.debug(f"→ get_articles_by_message(msg={message_id})")

        key = str(message_id)

        message_map = self._load_json(self.message_map_file, {})

        if key not in message_map:
            logger.debug(f"← get_articles_by_message() → None (no encontrado)")
            return None

        article_ids = message_map[key]["article_ids"]

        logger.debug(f"← get_articles_by_message() → {len(article_ids)} artículos")
        return article_ids
    
    def mark_excluded(self, article_ids: list[int]):
        """
        Marca artículos como excluidos (reacción 🚫).
        
        Args:
            article_ids: Lista de IDs de artículos a excluir
        """
        logger.debug(f"→ mark_excluded(articles={len(article_ids)})")

        excluded = self._load_json(self.excluded_file, [])

        # Agregar sin duplicados
        for article_id in article_ids:
            if article_id not in excluded:
                excluded.append(article_id)

        self._save_json(self.excluded_file, excluded)

        logger.debug(f"← mark_excluded() → total excluidos: {len(excluded)}")
        logger.info(f"✅ Excluidos: {len(article_ids)} artículos (total: {len(excluded)})")
    
    def mark_read(self, article_ids: list[int]):
        """
        Marca artículos como leídos individualmente (reacción ❤️).
        
        Args:
            article_ids: Lista de IDs de artículos a marcar
        """
        logger.debug(f"→ mark_read(articles={len(article_ids)})")

        marked = self._load_json(self.marked_file, [])

        # Agregar sin duplicados
        for article_id in article_ids:
            if article_id not in marked:
                marked.append(article_id)

        self._save_json(self.marked_file, marked)

        logger.debug(f"← mark_read() → total marcados: {len(marked)}")
        logger.info(f"✅ Marcados: {len(article_ids)} artículos (total: {len(marked)})")
    
    def is_excluded(self, article_id: int) -> bool:
        """Verifica si un artículo está excluido."""
        excluded = self._load_json(self.excluded_file, [])
        return article_id in excluded
    
    def is_marked(self, article_id: int) -> bool:
        """Verifica si un artículo ya fue marcado individualmente."""
        marked = self._load_json(self.marked_file, [])
        return article_id in marked
    
    def get_pending_articles(self, all_article_ids: list[int]) -> list[int]:
        """
        Obtiene artículos pendientes (no excluidos ni marcados).
        
        Args:
            all_article_ids: Lista de todos los IDs de artículos
            
        Returns:
            Lista de IDs pendientes
        """
        logger.debug(f"→ get_pending_articles(total={len(all_article_ids)})")

        excluded = self._load_json(self.excluded_file, [])
        marked = self._load_json(self.marked_file, [])

        pending = [
            article_id for article_id in all_article_ids
            if (article_id not in excluded) and (article_id not in marked)
        ]

        logger.debug(f"← get_pending_articles() → {len(pending)} pendientes")
        logger.info(f"📊 Artículos: {len(all_article_ids)} total, {len(pending)} pendientes, "
                   f"{len(marked)} marcados, {len(excluded)} excluidos")

        return pending
    
    def save_article_urls(self, articles: list) -> int:
        """
        Persiste los metadatos de artículos (id → {link, title}) necesarios
        para que el bot pueda resolver /url y /guardar entre ejecuciones,
        sin consultar TT-RSS.

        Args:
            articles: Lista de artículos con campos 'id', 'link' y 'title'

        Returns:
            Número de entradas guardadas
        """
        logger.debug(f"→ save_article_urls(articles={len(articles)})")

        # Formato: {"id": {"link": url, "title": título}}
        # Las claves JSON deben ser strings
        meta_map = {}
        for article in articles:
            article_id = article.get('id')
            url = article.get('link')
            if article_id and url:
                meta_map[str(article_id)] = {
                    "link":  url,
                    "title": article.get('title', ''),
                }

        self._save_json(self.article_urls_file, meta_map)

        logger.debug(f"← save_article_urls() → {len(meta_map)} entradas persistidas")
        logger.info(f"✅ Metadatos de artículos guardados: {len(meta_map)} en {self.article_urls_file.name}")
        return len(meta_map)

    def load_article_urls(self) -> dict:
        """
        Carga el mapa ID → URL para el lookup rápido de /url.

        Returns:
            Dict {int(article_id): url_str} — vacío si no existe el archivo
        """
        logger.debug("→ load_article_urls()")

        raw = self._load_json(self.article_urls_file, {})

        # Soporte de formato antiguo {id: url_str} y nuevo {id: {link, title}}
        url_map = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                url_map[int(k)] = v.get("link", "")
            else:
                url_map[int(k)] = v  # compatibilidad con formato antiguo

        logger.debug(f"← load_article_urls() → {len(url_map)} URLs")
        logger.info(f"✅ URLs de artículos cargadas: {len(url_map)} entradas")
        return url_map

    def load_article_metadata(self) -> dict:
        """
        Carga los metadatos completos (link + title) de los artículos.

        Returns:
            Dict {int(article_id): {"link": str, "title": str}}
        """
        logger.debug("→ load_article_metadata()")

        raw = self._load_json(self.article_urls_file, {})

        meta = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                meta[int(k)] = v
            else:
                # Formato antiguo: solo URL, sin título
                meta[int(k)] = {"link": v, "title": ""}

        logger.debug(f"← load_article_metadata() → {len(meta)} entradas")
        return meta

    def load_message_map(self) -> dict:
        """
        Carga y devuelve el mapa message_id -> metadata desde disco.

        Returns:
            Dict con los mapeos (claves como strings)
        """
        logger.debug("→ load_message_map()")
        message_map = self._load_json(self.message_map_file, {})
        logger.debug(f"← load_message_map() → {len(message_map)} entradas")
        return message_map

    def cleanup_old_mappings(self, days: int = 7):
        """
        Limpia mapeos antiguos para evitar que el archivo crezca indefinidamente.
        
        Args:
            days: Limpiar mapeos más antiguos de N días
        """
        logger.debug(f"→ cleanup_old_mappings(days={days})")
        logger.info(f"Limpiando mapeos antiguos (>{days} días)...")
        
        cutoff = datetime.now() - timedelta(days=days)

        message_map = self._load_json(self.message_map_file, {})
        original_count = len(message_map)

        # Filtrar mapeos antiguos
        cleaned_map = {}
        for message_id, data in message_map.items():
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
                if timestamp > cutoff:
                    cleaned_map[message_id] = data
            except (KeyError, ValueError) as e:
                logger.warning(f"⚠️  Mapeo inválido para mensaje {message_id}: {e}")
                # Conservar por seguridad si no tiene timestamp válido
                cleaned_map[message_id] = data

        removed_count = original_count - len(cleaned_map)

        if removed_count > 0:
            self._save_json(self.message_map_file, cleaned_map)

            logger.debug(f"← cleanup_old_mappings() → {removed_count} eliminados")
            logger.info(f"✅ Limpieza completada: {removed_count} mapeos eliminados, {len(cleaned_map)} conservados")
        else:
            logger.debug(f"← cleanup_old_mappings() → sin cambios")
            logger.info(f"✅ Limpieza completada: sin mapeos antiguos")
    
    def reset_session(self):
        """
        Limpia el estado de la sesión actual (excluidos y marcados).
        Útil al inicio de una nueva ejecución diaria.
        """
        logger.debug("→ reset_session()")
        logger.info("Reseteando estado de sesión...")
        
        excluded = []
        marked = []

        self._save_json(self.excluded_file, excluded)
        self._save_json(self.marked_file, marked)
        
        logger.debug("← reset_session() → limpiado")
        logger.info("✅ Estado de sesión reseteado")
    
    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del estado actual.
        
        Returns:
            Dict con estadísticas
        """
        logger.debug("→ get_stats()")

        message_map = self._load_json(self.message_map_file, {})
        excluded = self._load_json(self.excluded_file, [])
        marked = self._load_json(self.marked_file, [])

        stats = {
            "total_messages": len(message_map),
            "excluded_articles": len(excluded),
            "marked_articles": len(marked),
            "state_dir": str(self.state_dir)
        }

        logger.debug(f"← get_stats() → {stats}")
        return stats
