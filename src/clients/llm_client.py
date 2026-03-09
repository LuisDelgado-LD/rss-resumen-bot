"""
Cliente para interactuar con Google Gemini API.
Genera resúmenes de artículos usando LLM.
"""
import time
import json
import re
import logging
from typing import Optional, Dict, List
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from src.config import settings
from src.services.prompt_manager import PromptManager


logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Excepción base para errores del cliente LLM."""
    pass


class LLMRateLimitError(LLMClientError):
    """Error de rate limit."""
    pass


class LLMClient:
    """Cliente para interactuar con Google Gemini API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Inicializa el cliente LLM.
        
        Args:
            api_key: API key de Google (si no se proporciona, usa settings)
            model: Modelo a usar (si no se proporciona, usa settings)
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model_name = model or settings.GOOGLE_MODEL
        
        # Configurar API
        genai.configure(api_key=self.api_key)
        
        # Configuración del modelo
        self.generation_config = {
            "temperature": settings.LLM_TEMPERATURE,
            "max_output_tokens": settings.MAX_SUMMARY_TOKENS,
        }
        
        # Safety settings (permisivo para noticias)
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Crear modelo
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 60 / 15  # 15 RPM = 4 segundos entre requests
        
        # Prompt manager
        self.prompt_manager = PromptManager()
        
        logger.info(f"Cliente LLM inicializado (modelo: {self.model_name})")
        logger.debug(f"→ Configuración: temp={settings.LLM_TEMPERATURE}, max_tokens={settings.MAX_SUMMARY_TOKENS}")
    
    def _wait_for_rate_limit(self):
        """Espera si es necesario para respetar rate limit."""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                wait_time = self.min_request_interval - elapsed
                logger.debug(f"Rate limit: esperando {wait_time:.1f}s")
                time.sleep(wait_time)
    
    def _generate_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        generation_config_override: Optional[Dict] = None
    ) -> str:
        """
        Genera contenido con reintentos.

        Args:
            prompt: Prompt para el LLM
            max_retries: Número máximo de reintentos
            generation_config_override: Config opcional que sobreescribe la del modelo

        Returns:
            Texto generado

        Raises:
            LLMClientError: Si falla después de reintentos
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Rate limiting
                self._wait_for_rate_limit()
                
                # Logging del request
                prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logger.debug(f"→ LLM request (intento {attempt}/{max_retries})")
                logger.debug(f"→ Prompt ({len(prompt)} chars): {prompt_preview}")
                
                # Hacer request
                start_time = time.time()
                if generation_config_override:
                    response = self.model.generate_content(
                        prompt,
                        generation_config=generation_config_override
                    )
                else:
                    response = self.model.generate_content(prompt)
                elapsed = time.time() - start_time
                
                # Actualizar timestamp para rate limiting
                self.last_request_time = time.time()
                
                # Verificar respuesta
                if not response.text:
                    raise LLMClientError("Respuesta vacía del LLM")
                
                # Logging de respuesta
                response_preview = response.text[:200] + "..." if len(response.text) > 200 else response.text
                logger.debug(f"← LLM response ({len(response.text)} chars, {elapsed:.2f}s)")
                logger.debug(f"← Response preview: {response_preview}")
                
                # Métricas
                if hasattr(response, 'usage_metadata'):
                    metadata = response.usage_metadata
                    logger.debug(
                        f"← Tokens: prompt={metadata.prompt_token_count}, "
                        f"response={metadata.candidates_token_count}, "
                        f"total={metadata.total_token_count}"
                    )
                
                logger.info(f"✅ LLM response recibida ({len(response.text)} chars en {elapsed:.2f}s)")
                
                return response.text
                
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Detectar rate limit
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning(f"⚠️ Rate limit alcanzado (intento {attempt}/{max_retries})")
                    if attempt < max_retries:
                        wait_time = settings.API_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                        logger.info(f"Esperando {wait_time}s antes de reintentar...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise LLMRateLimitError(f"Rate limit después de {max_retries} intentos")
                
                # Otros errores
                logger.warning(f"⚠️ Error en LLM request: {error_type}: {error_msg} (intento {attempt}/{max_retries})")
                
                if attempt < max_retries:
                    time.sleep(settings.API_RETRY_DELAY_SECONDS)
                else:
                    logger.error(f"❌ LLM request falló después de {max_retries} intentos: {error_type}: {error_msg}")
                    raise LLMClientError(f"LLM request falló: {error_msg}") from e
        
        # No debería llegar aquí
        raise LLMClientError(f"LLM request falló: {last_error}")
    
    def generate_category_summary(
        self,
        category_name: str,
        articles: list[dict]
    ) -> str:
        """
        Genera un resumen de artículos de una categoría.
        
        Args:
            category_name: Nombre de la categoría
            articles: Lista de artículos preparados
            
        Returns:
            Resumen generado
        """
        logger.info(f"Generando resumen para categoría: {category_name} ({len(articles)} artículos)")
        logger.debug(f"→ generate_category_summary(category={category_name}, articles={len(articles)})")
        
        if not articles:
            logger.warning(f"⚠️ No hay artículos para categoría {category_name}")
            return f"# {category_name}\n\nNo hay artículos nuevos en esta categoría."
        
        # Construir prompt
        prompt = self._build_category_prompt(category_name, articles)
        
        # Generar resumen
        try:
            summary = self._generate_with_retry(prompt)
            logger.debug(f"← generate_category_summary() → {len(summary)} chars")
            logger.info(f"✅ Resumen generado para {category_name}: {len(summary)} chars")
            return summary
            
        except LLMClientError as e:
            logger.error(f"❌ Error generando resumen para {category_name}: {e}")
            raise
    
    def _build_category_prompt(
        self,
        category_name: str,
        articles: list[dict]
    ) -> str:
        """
        Construye el prompt para generar resumen de una categoría.
        
        Args:
            category_name: Nombre de la categoría
            articles: Lista de artículos
            
        Returns:
            Prompt completo
        """
        prompt = self.prompt_manager.format_category_prompt(
            category_name=category_name,
            articles=articles,
            max_tokens=settings.MAX_SUMMARY_TOKENS
        )
        
        logger.debug(f"Prompt construido: {len(prompt)} chars, {len(articles)} artículos")
        
        return prompt
    
    def _build_all_categories_prompt(
        self,
        articles_by_category: Dict[str, List[dict]]
    ) -> str:
        """
        Construye el prompt unificado con todas las categorías.

        Args:
            articles_by_category: Dict con categoría → lista de artículos

        Returns:
            Prompt completo para una sola llamada LLM
        """
        logger.debug(
            f"→ _build_all_categories_prompt(categories={list(articles_by_category.keys())})"
        )

        prompt = self.prompt_manager.format_all_categories_prompt(
            articles_by_category=articles_by_category,
            max_tokens_per_category=settings.MAX_SUMMARY_TOKENS
        )

        logger.debug(
            f"← _build_all_categories_prompt() → {len(prompt)} chars, "
            f"{len(articles_by_category)} categorías"
        )

        return prompt

    def _parse_json_summaries(
        self,
        response_text: str,
        expected_categories: List[str]
    ) -> Dict[str, str]:
        """
        Parsea la respuesta JSON del LLM en un dict de resúmenes por categoría.

        Intenta varias estrategias si el JSON no es válido:
        1. Parse directo del texto.
        2. Extracción del bloque de código markdown (```json ... ```).
        3. Búsqueda del primer '{' al último '}'.

        Args:
            response_text: Texto completo devuelto por el LLM
            expected_categories: Lista de categorías esperadas en el JSON

        Returns:
            Dict con categoría → resumen (solo las categorías parseadas correctamente)
        """
        logger.debug(f"→ _parse_json_summaries(text={len(response_text)} chars)")

        text = response_text.strip()

        parsed = None

        # Estrategia 1: parse directo
        try:
            parsed = json.loads(text)
            logger.debug("JSON parseado directamente")
        except json.JSONDecodeError:
            pass

        # Estrategia 2: extraer de bloque markdown ```json ... ```
        if parsed is None:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    logger.debug("JSON extraído de bloque markdown")
                except json.JSONDecodeError:
                    pass

        # Estrategia 3: extraer desde primer '{' hasta último '}'
        if parsed is None:
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                candidate = text[first_brace:last_brace + 1]
                try:
                    parsed = json.loads(candidate)
                    logger.debug("JSON extraído entre llaves")
                except json.JSONDecodeError:
                    pass

        if parsed is None:
            logger.error("❌ No se pudo parsear el JSON de la respuesta LLM")
            logger.debug(f"Respuesta cruda: {text[:500]}")
            return {}

        if not isinstance(parsed, dict):
            logger.error(f"❌ El JSON parseado no es un dict: {type(parsed)}")
            return {}

        # Filtrar solo las categorías esperadas y con valor string
        summaries = {}
        for cat in expected_categories:
            if cat in parsed:
                value = parsed[cat]
                if isinstance(value, str) and value.strip():
                    summaries[cat] = value.strip()
                    logger.debug(f"✅ Categoría parseada: {cat} ({len(value)} chars)")
                else:
                    logger.warning(f"⚠️ Valor inválido para categoría '{cat}': {type(value)}")
            else:
                logger.warning(f"⚠️ Categoría '{cat}' no encontrada en el JSON")

        logger.debug(
            f"← _parse_json_summaries() → {len(summaries)}/{len(expected_categories)} categorías"
        )
        return summaries

    def _validate_article_ids(
        self,
        summary: str,
        articles: List[dict]
    ) -> List[int]:
        """
        Comprueba que todos los artículos de la lista tienen su [ID] referenciado
        en el texto del resumen.

        Args:
            summary: Texto del resumen generado por el LLM.
            articles: Lista de artículos con su campo 'id'.

        Returns:
            Lista de IDs de artículos que NO aparecen en el resumen.
            Lista vacía significa que el resumen es válido.
        """
        found_ids = set(int(m) for m in re.findall(r'\[(\d+)\]', summary))
        expected_ids = [article['id'] for article in articles]
        missing = [aid for aid in expected_ids if aid not in found_ids]

        if missing:
            logger.debug(
                f"_validate_article_ids: faltan {len(missing)}/{len(expected_ids)} IDs: {missing[:10]}"
            )
        else:
            logger.debug(
                f"_validate_article_ids: todos los {len(expected_ids)} IDs presentes ✅"
            )

        return missing

    def generate_summaries_by_category(
        self,
        grouped_articles: Dict[str, List[dict]]
    ) -> Dict[str, str]:
        """
        Genera resúmenes para todas las categorías en UNA SOLA llamada al LLM.

        El LLM devuelve un JSON con la forma:
            {"CATEGORIA_1": "resumen...", "CATEGORIA_2": "resumen...", ...}

        Si alguna categoría falla el parseo, se reintenta con una llamada
        individual solo para esa categoría.

        Args:
            grouped_articles: Dict con categoría → lista de artículos

        Returns:
            Dict con categoría → resumen
        """
        logger.info(f"Generando resúmenes para {len(grouped_articles)} categorías (llamada única al LLM)")
        logger.debug(f"→ generate_summaries_by_category(categories={list(grouped_articles.keys())})")

        start_time = time.time()
        total_articles = sum(len(a) for a in grouped_articles.values())

        # ── Llamada única al LLM ──────────────────────────────────────────
        prompt = self._build_all_categories_prompt(grouped_articles)
        num_categories = len(grouped_articles)

        # Ajustar max_output_tokens al número de categorías
        max_tokens_total = settings.MAX_SUMMARY_TOKENS * num_categories
        generation_config_override = {
            "temperature": settings.LLM_TEMPERATURE,
            "max_output_tokens": max_tokens_total,
        }

        logger.info(
            f"⏳ Enviando prompt único ({len(prompt)} chars, "
            f"max_tokens={max_tokens_total})..."
        )

        summaries: Dict[str, str] = {}

        try:
            raw_response = self._generate_with_retry(
                prompt,
                generation_config_override=generation_config_override
            )
            llm_elapsed = time.time() - start_time
            logger.info(f"✅ Respuesta LLM recibida en {llm_elapsed:.1f}s ({len(raw_response)} chars)")

            # Parsear JSON
            summaries = self._parse_json_summaries(
                raw_response,
                expected_categories=list(grouped_articles.keys())
            )
            logger.info(
                f"✅ JSON parseado: {len(summaries)}/{num_categories} categorías"
            )

        except LLMClientError as e:
            logger.error(f"❌ Error en llamada única al LLM: {e}")
            # summaries queda vacío → todas las categorías irán al fallback

        # ── Fallback: categorías faltantes (parse) ───────────────────────
        missing = [c for c in grouped_articles if c not in summaries]

        if missing:
            logger.warning(
                f"⚠️ {len(missing)} categorías requieren llamada individual de fallback: {missing}"
            )
            for category_name in missing:
                articles = grouped_articles[category_name]
                logger.info(f"🔄 Fallback: generando resumen individual para '{category_name}'...")
                try:
                    summary = self.generate_category_summary(category_name, articles)
                    summaries[category_name] = summary
                    logger.info(f"✅ Fallback exitoso para '{category_name}'")
                except LLMClientError as e:
                    logger.error(f"❌ Fallback falló para '{category_name}': {e}")
                    summaries[category_name] = (
                        f"# {category_name}\n\n⚠️ Error generando resumen: {e}"
                    )

        # ── Validación de IDs: todos los artículos deben aparecer referenciados ──
        logger.info("🔍 Validando referencias [ID] en los resúmenes generados...")
        for category_name, summary in list(summaries.items()):
            articles = grouped_articles.get(category_name, [])
            if not articles:
                continue

            missing_ids = self._validate_article_ids(summary, articles)
            if not missing_ids:
                logger.debug(f"✅ [{category_name}] todos los IDs presentes")
                continue

            # Hay IDs ausentes → reintento individual
            logger.warning(
                f"⚠️ [{category_name}] faltan {len(missing_ids)}/{len(articles)} IDs "
                f"en el resumen. Reintentando con llamada individual..."
            )
            try:
                retry_summary = self.generate_category_summary(category_name, articles)
                retry_missing = self._validate_article_ids(retry_summary, articles)

                if not retry_missing:
                    summaries[category_name] = retry_summary
                    logger.info(
                        f"✅ [{category_name}] reintento exitoso: todos los IDs presentes"
                    )
                else:
                    # Reintento también falló
                    if len(articles) == 1:
                        # Categoría de 1 artículo: tolerable, usar reintento
                        summaries[category_name] = retry_summary
                        logger.warning(
                            f"⚠️ [{category_name}] reintento sin IDs pero solo hay 1 artículo "
                            f"— se usa el resumen de todos modos"
                        )
                    else:
                        # Múltiples artículos sin IDs: error crítico
                        logger.critical(
                            f"🚨 [{category_name}] CRÍTICO: tras reintento siguen faltando "
                            f"{len(retry_missing)}/{len(articles)} IDs {retry_missing}. "
                            f"El resumen se enviará SIN referencias válidas — "
                            f"el mapeo message→artículos estará incompleto."
                        )
                        # Usamos el reintento (puede ser levemente mejor que el original)
                        summaries[category_name] = retry_summary

            except LLMClientError as e:
                logger.error(
                    f"❌ [{category_name}] reintento de validación falló con error: {e}. "
                    f"Se conserva el resumen original sin IDs."
                )

        elapsed = time.time() - start_time
        logger.debug(f"← generate_summaries_by_category() → {len(summaries)} resúmenes")
        logger.info(
            f"✅ Resúmenes generados: {len(summaries)}/{num_categories} categorías "
            f"en {elapsed:.1f}s ({total_articles} artículos)"
        )

        return summaries
