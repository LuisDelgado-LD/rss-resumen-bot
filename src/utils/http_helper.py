"""
Helper para llamadas HTTP con logging estandarizado.
Captura errores de APIs externas y loggea toda la información relevante.
"""
import logging
import json
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
import requests


logger = logging.getLogger(__name__)


class HTTPRequestHelper:
    """
    Helper para hacer requests HTTP con logging automático según guidelines.
    """
    
    @staticmethod
    def post(
        url: str,
        json_data: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
        parse_mode: str = 'json',
        context: str = "API request"
    ) -> requests.Response:
        """
        POST con logging automático.
        
        Args:
            url: URL destino
            json_data: Payload JSON
            data: Form data
            headers: Headers HTTP
            timeout: Timeout en segundos
            parse_mode: Cómo parsear response ('json', 'text', 'raw')
            context: Descripción de la operación (para logs)
            
        Returns:
            Response object
            
        Raises:
            requests.exceptions.HTTPError: Si la request falla
        """
        # Log de entrada
        logger.debug(f"→ POST {url}")
        if headers:
            safe_headers = {k: v[:20] + '...' if 'token' in k.lower() or 'auth' in k.lower() else v 
                          for k, v in headers.items()}
            logger.debug(f"→ Headers: {safe_headers}")
        
        if json_data:
            payload_str = json.dumps(json_data, indent=2, ensure_ascii=False)
            logger.debug(f"→ Payload: {payload_str[:500]}{'...' if len(payload_str) > 500 else ''}")
        
        # Hacer request
        start_time = time.time()
        
        try:
            response = requests.post(
                url=url,
                json=json_data,
                data=data,
                headers=headers,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            # Log de respuesta exitosa
            logger.debug(f"← Status: {response.status_code} ({elapsed:.2f}s)")
            
            # Si hay error, loggear el body antes de raise
            if not response.ok:
                error_body = None
                try:
                    error_body = response.json() if response.text else {}
                except:
                    error_body = response.text[:500] if response.text else "No response body"
                
                logger.error(f"❌ {context} failed: HTTP {response.status_code}")
                logger.error(f"❌ Error detail: {error_body}")
                logger.debug(f"← Response headers: {dict(response.headers)}")
                
                # Loggear el payload que causó el error
                if json_data:
                    logger.debug(f"→ Failed request payload: {json.dumps(json_data, indent=2, ensure_ascii=False)[:1000]}")
                
                response.raise_for_status()
            
            # Log de response body (solo en DEBUG y si no es muy grande)
            if parse_mode == 'json':
                try:
                    body = response.json()
                    body_str = json.dumps(body, indent=2, ensure_ascii=False)
                    logger.debug(f"← Response: {body_str[:500]}{'...' if len(body_str) > 500 else ''}")
                except:
                    logger.debug(f"← Response (not JSON): {response.text[:500]}")
            else:
                logger.debug(f"← Response: {response.text[:500]}{'...' if len(response.text) > 500 else ''}")
            
            logger.info(f"✅ {context} completed ({elapsed:.2f}s)")
            
            return response
            
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            logger.error(f"❌ {context} timeout after {elapsed:.1f}s")
            raise
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {context} failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    def get(
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
        context: str = "API request"
    ) -> requests.Response:
        """
        GET con logging automático.
        
        Args:
            url: URL destino
            params: Query parameters
            headers: Headers HTTP
            timeout: Timeout en segundos
            context: Descripción de la operación (para logs)
            
        Returns:
            Response object
        """
        # Log de entrada
        logger.debug(f"→ GET {url}")
        if params:
            logger.debug(f"→ Params: {params}")
        if headers:
            safe_headers = {k: v[:20] + '...' if 'token' in k.lower() or 'auth' in k.lower() else v 
                          for k, v in headers.items()}
            logger.debug(f"→ Headers: {safe_headers}")
        
        # Hacer request
        start_time = time.time()
        
        try:
            response = requests.get(
                url=url,
                params=params,
                headers=headers,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            logger.debug(f"← Status: {response.status_code} ({elapsed:.2f}s)")
            
            # Si hay error, loggear el body
            if not response.ok:
                error_body = None
                try:
                    error_body = response.json() if response.text else {}
                except:
                    error_body = response.text[:500] if response.text else "No response body"
                
                logger.error(f"❌ {context} failed: HTTP {response.status_code}")
                logger.error(f"❌ Error detail: {error_body}")
                
                response.raise_for_status()
            
            logger.info(f"✅ {context} completed ({elapsed:.2f}s)")
            
            return response
            
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            logger.error(f"❌ {context} timeout after {elapsed:.1f}s")
            raise
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {context} failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
            raise


def log_http_errors(context: str = "API call"):
    """
    Decorator para funciones que hacen HTTP requests.
    Captura excepciones y loggea con contexto.
    
    Args:
        context: Descripción de la operación
        
    Example:
        @log_http_errors(context="Telegram sendMessage")
        def send_message(self, text):
            response = requests.post(url, json={'text': text})
            return response
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"→ {context}()")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.debug(f"← {context}() completed ({elapsed:.2f}s)")
                return result
                
            except requests.exceptions.HTTPError as e:
                elapsed = time.time() - start_time
                
                # Intentar extraer más info del error
                response = getattr(e, 'response', None)
                if response is not None:
                    try:
                        error_body = response.json()
                    except:
                        error_body = response.text[:500] if response.text else "No body"
                    
                    logger.error(f"❌ {context} HTTP error: {response.status_code}")
                    logger.error(f"❌ Error detail: {error_body}")
                else:
                    logger.error(f"❌ {context} HTTP error: {e}")
                
                raise
                
            except requests.exceptions.Timeout:
                elapsed = time.time() - start_time
                logger.error(f"❌ {context} timeout after {elapsed:.1f}s")
                raise
                
            except requests.exceptions.RequestException as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ {context} failed: {type(e).__name__}: {e}")
                raise
                
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ {context} unexpected error: {type(e).__name__}: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator
