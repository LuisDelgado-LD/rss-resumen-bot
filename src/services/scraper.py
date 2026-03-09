"""
Módulo de scraping para obtener contenido completo de artículos.
Maneja paralelismo por dominio, caché de URLs fallidas, y timeouts.
"""
import requests
import time
import logging
from typing import Optional, Dict, List
from urllib.parse import urlparse
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import trafilatura

from src.config import settings


logger = logging.getLogger(__name__)


class URLCache:
    """Caché persistente de URLs fallidas."""
    
    def __init__(self, cache_file: Optional[Path] = None):
        """
        Inicializa el caché.
        
        Args:
            cache_file: Ruta al archivo de caché (default: ./cache/failed_urls.json)
        """
        if cache_file is None:
            cache_file = Path.cwd() / "cache" / "failed_urls.json"
        
        self.cache_file = cache_file
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Carga el caché desde disco."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    content = f.read().strip()
                    # Archivo vacío = caché vacío (sin error)
                    if not content:
                        logger.debug(f"Archivo de caché vacío, inicializando nuevo caché")
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Caché corrupto (JSON inválido): {e}, reiniciando caché")
                return {}
            except Exception as e:
                logger.error(f"❌ Error inesperado cargando caché: {e}", exc_info=True)
                return {}
        
        logger.debug(f"Archivo de caché no existe, creando nuevo")
        return {}
    
    def _save_cache(self):
        """Guarda el caché a disco."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando caché: {e}")
    
    def should_retry(self, url: str) -> bool:
        """
        Determina si se debe reintentar una URL fallida.
        
        Args:
            url: URL a verificar
            
        Returns:
            True si se debe reintentar, False si saltarla
        """
        if not settings.SCRAPING_CACHE_ENABLED:
            return True
        
        if url not in self.cache:
            return True
        
        entry = self.cache[url]
        first_failed = datetime.fromisoformat(entry['first_failed'])
        days_since_fail = (datetime.now() - first_failed).days
        
        # Si pasó suficiente tiempo, resetear y reintentar
        if days_since_fail >= settings.SCRAPING_CACHE_RETRY_AFTER_DAYS:
            logger.debug(f"Reseteando caché para {url} (pasaron {days_since_fail} días)")
            del self.cache[url]
            self._save_cache()
            return True
        
        # Si no pasó suficiente tiempo, verificar reintentos
        if entry['attempts'] >= settings.SCRAPING_CACHE_MAX_RETRIES:
            logger.debug(f"Saltando {url} (max reintentos alcanzado)")
            return False
        
        logger.debug(f"Reintentando {url} (intento {entry['attempts'] + 1}/{settings.SCRAPING_CACHE_MAX_RETRIES})")
        return True
    
    def mark_failed(self, url: str, error: str):
        """
        Marca una URL como fallida en el caché.
        
        Args:
            url: URL que falló
            error: Descripción del error
        """
        if not settings.SCRAPING_CACHE_ENABLED:
            return
        
        now = datetime.now().isoformat()
        
        if url in self.cache:
            self.cache[url]['last_attempt'] = now
            self.cache[url]['attempts'] += 1
            self.cache[url]['error'] = error
        else:
            self.cache[url] = {
                'first_failed': now,
                'last_attempt': now,
                'attempts': 1,
                'error': error
            }
        
        self._save_cache()
    
    def mark_success(self, url: str):
        """
        Elimina una URL del caché (éxito).
        
        Args:
            url: URL que tuvo éxito
        """
        if url in self.cache:
            del self.cache[url]
            self._save_cache()


class DomainRateLimiter:
    """Rate limiter por dominio."""
    
    def __init__(self, delay_seconds: int):
        """
        Inicializa el rate limiter.
        
        Args:
            delay_seconds: Segundos de delay entre requests al mismo dominio
        """
        self.delay = delay_seconds
        self.last_request: Dict[str, float] = {}
    
    def wait_if_needed(self, domain: str):
        """
        Espera si es necesario antes de hacer request al dominio.
        
        Args:
            domain: Dominio a consultar
        """
        if domain in self.last_request:
            elapsed = time.time() - self.last_request[domain]
            if elapsed < self.delay:
                sleep_time = self.delay - elapsed
                logger.debug(f"Esperando {sleep_time:.2f}s antes de consultar {domain}")
                time.sleep(sleep_time)
        
        self.last_request[domain] = time.time()


def fetch_article_content(url: str, cache: URLCache, rate_limiter: DomainRateLimiter) -> Optional[str]:
    """
    Obtiene el contenido completo de un artículo desde su URL.
    
    Intenta primero con User-Agent de bot (ético).
    Si detecta bloqueo, reintenta automáticamente con User-Agent de navegador.
    
    Args:
        url: URL del artículo
        cache: Caché de URLs fallidas
        rate_limiter: Rate limiter por dominio
        
    Returns:
        Contenido HTML extraído o None si falla
    """
    # Verificar caché
    if not cache.should_retry(url):
        return None
    
    # Parsear dominio para rate limiting
    domain = urlparse(url).netloc
    
    # Intentar con User-Agent de bot primero (ético)
    result = _fetch_with_user_agent(
        url=url,
        user_agent=settings.SCRAPING_USER_AGENT_BOT,
        domain=domain,
        rate_limiter=rate_limiter,
        ua_type="bot"
    )
    
    # Si fue exitoso o no habilitó fallback, retornar
    if result['success'] or not settings.SCRAPING_UA_FALLBACK_ENABLED:
        if result['success']:
            cache.mark_success(url)
        else:
            cache.mark_failed(url, result['error'])
        return result['content']
    
    # Si detectó bloqueo por UA, reintentar con navegador
    if result['is_ua_block']:
        logger.warning(f"⚠️  Bloqueo detectado en {url}, reintentando con UA de navegador...")
        
        result = _fetch_with_user_agent(
            url=url,
            user_agent=settings.SCRAPING_USER_AGENT_BROWSER,
            domain=domain,
            rate_limiter=rate_limiter,
            ua_type="browser"
        )
        
        if result['success']:
            logger.info(f"✅ Scraping exitoso con UA de navegador: {url}")
            cache.mark_success(url)
        else:
            cache.mark_failed(url, result['error'])
        
        return result['content']
    
    # Error no relacionado con UA
    cache.mark_failed(url, result['error'])
    return result['content']


def _fetch_with_user_agent(
    url: str,
    user_agent: str,
    domain: str,
    rate_limiter: DomainRateLimiter,
    ua_type: str = "bot"
) -> dict:
    """
    Intenta obtener contenido con un User-Agent específico.
    
    Args:
        url: URL del artículo
        user_agent: User-Agent a usar
        domain: Dominio (para rate limiting)
        rate_limiter: Rate limiter
        ua_type: Tipo de UA ("bot" o "browser") para logging
        
    Returns:
        Dict con keys: success (bool), content (str|None), error (str), is_ua_block (bool)
    """
    
    try:
        # Parsear dominio
        domain = urlparse(url).netloc
        
        # Rate limiting por dominio
        rate_limiter.wait_if_needed(domain)
        
        # Hacer request
        logger.debug(f"→ Scraping {url} (UA: {ua_type})")
        response = requests.get(
            url,
            timeout=settings.SCRAPING_TIMEOUT_SECONDS,
            headers={'User-Agent': user_agent}
        )
        
        # Verificar si es bloqueo por User-Agent
        is_ua_block = False
        if response.status_code in [401, 403]:
            is_ua_block = True
            logger.debug(f"Posible bloqueo por UA: HTTP {response.status_code}")
        
        response.raise_for_status()
        
        # Extraer contenido con trafilatura
        extracted = trafilatura.extract(
            response.content,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        
        if extracted:
            logger.debug(f"✅ Scraping exitoso: {url} ({len(extracted)} chars)")
            return {
                'success': True,
                'content': extracted,
                'error': '',
                'is_ua_block': False
            }
        else:
            error_msg = "extraction_failed"
            logger.warning(f"⚠️  Extracción falló (contenido vacío): {url}")
            return {
                'success': False,
                'content': None,
                'error': error_msg,
                'is_ua_block': False
            }
            
    except requests.exceptions.Timeout as e:
        error_msg = f"timeout_{settings.SCRAPING_TIMEOUT_SECONDS}s"
        logger.warning(f"⚠️  Timeout ({settings.SCRAPING_TIMEOUT_SECONDS}s) scraping {url}")
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': False
        }
        
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = f"http_{status_code}"
        
        # Detectar bloqueos por User-Agent
        is_ua_block = status_code in [401, 403]
        
        if is_ua_block and ua_type == "bot":
            logger.debug(f"Bloqueo HTTP {status_code} detectado (probablemente UA)")
        else:
            logger.warning(f"❌ HTTP {status_code} scraping {url}")
        
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': is_ua_block
        }
        
    except requests.exceptions.SSLError as e:
        error_msg = f"ssl_error: {str(e)[:100]}"
        logger.warning(f"❌ SSL error scraping {url}: {e}")
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': False
        }
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"connection_error: {str(e)[:100]}"
        logger.warning(f"❌ Connection error scraping {url}: {e}")
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': False
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"request_error: {type(e).__name__} - {str(e)[:100]}"
        logger.warning(f"❌ Request error scraping {url}: {type(e).__name__} - {e}")
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': False
        }
        
    except Exception as e:
        error_msg = f"unknown: {type(e).__name__} - {str(e)[:100]}"
        logger.error(f"❌ Error inesperado scraping {url}: {type(e).__name__} - {e}")
        return {
            'success': False,
            'content': None,
            'error': error_msg,
            'is_ua_block': False
        }


def scrape_articles_parallel(articles: List[Dict]) -> Dict[str, Optional[str]]:
    """
    Scrape múltiples artículos en paralelo, agrupados por dominio.
    
    Args:
        articles: Lista de artículos con campo 'link'
        
    Returns:
        Dict con url → contenido_extraído
    """
    if not settings.SCRAPING_ENABLED:
        return {}
    
    # Inicializar caché y rate limiter
    cache = URLCache()
    rate_limiter = DomainRateLimiter(settings.SCRAPING_DELAY_SAME_DOMAIN_SECONDS)
    
    # Agrupar artículos por dominio
    by_domain: Dict[str, List[str]] = {}
    for article in articles:
        url = article.get('link')
        if not url:
            continue
        
        domain = urlparse(url).netloc
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(url)
    
    logger.info(f"Scraping {len(articles)} artículos desde {len(by_domain)} dominios")
    
    results = {}
    
    # Procesar dominios en paralelo
    with ThreadPoolExecutor(max_workers=settings.SCRAPING_MAX_PARALLEL_DOMAINS) as executor:
        # Crear futures por dominio
        domain_futures = {}
        
        for domain, urls in by_domain.items():
            # Para cada dominio, procesar URLs secuencialmente (con rate limit)
            def process_domain(d, u_list):
                domain_results = {}
                for u in u_list:
                    content = fetch_article_content(u, cache, rate_limiter)
                    domain_results[u] = content
                return domain_results
            
            future = executor.submit(process_domain, domain, urls)
            domain_futures[future] = domain
        
        # Recolectar resultados
        for future in as_completed(domain_futures):
            domain = domain_futures[future]
            try:
                domain_results = future.result()
                results.update(domain_results)
                logger.debug(f"Completado scraping de dominio: {domain}")
            except Exception as e:
                logger.error(f"Error procesando dominio {domain}: {e}")
    
    successful = sum(1 for v in results.values() if v is not None)
    failed = len(results) - successful
    
    logger.info(f"Scraping completado: {successful}/{len(results)} exitosos")
    
    if failed > 0:
        logger.warning(f"{failed} URLs fallaron en scraping:")
        for url, content in results.items():
            if content is None:
                # Buscar el error en caché
                error_msg = "desconocido"
                if url in cache.cache:
                    error_msg = cache.cache[url].get('error', 'desconocido')
                logger.warning(f"  ❌ {url} (error: {error_msg})")
    
    return results
