"""
Servicio para procesar y limpiar artículos.
Prepara el contenido de los artículos para ser procesados por el LLM.
"""
from typing import Optional
from bs4 import BeautifulSoup
import re
import logging


logger = logging.getLogger(__name__)


def clean_html_content(html: str) -> str:
    """
    Limpia contenido HTML y lo convierte a texto plano.
    
    Usa BeautifulSoup para:
    1. Parsear HTML
    2. Remover tags innecesarios
    3. Convertir a texto plano limpio
    
    Args:
        html: Contenido HTML del artículo
        
    Returns:
        Texto plano limpio con solo el contenido principal
    """
    import time
    
    logger.debug(f"→ clean_html_content(html={len(html) if html else 0} chars)")
    
    if not html or not html.strip():
        logger.debug("← clean_html_content() → '' (HTML vacío)")
        return ""
    
    start_time = time.time()
    
    try:
        # Paso 1: Parse con BeautifulSoup
        # Usar html.parser (built-in, no requiere dependencias)
        logger.debug(f"Parseando HTML ({len(html)} chars)...")
        soup = BeautifulSoup(html, 'html.parser')
        logger.debug("HTML parseado exitosamente")
        
        # Paso 2: Remover elementos inútiles
        tags_to_remove = ['script', 'style', 'iframe', 'nav', 'footer', 
                         'aside', 'header', 'form', 'button']
        removed_count = 0
        for tag in soup(tags_to_remove):
            tag.decompose()
            removed_count += 1
        logger.debug(f"Removidos {removed_count} elementos innecesarios")
        
        # Paso 3: Convertir a texto plano
        text = soup.get_text(separator=' ', strip=True)
        logger.debug(f"Texto extraído: {len(text)} chars")
        
        # Paso 4: Limpieza final
        # Remover URLs
        text = re.sub(r'http[s]?://\S+', '', text)
        
        # Remover emails
        text = re.sub(r'\S+@\S+', '', text)
        
        # Normalizar espacios múltiples
        text = re.sub(r'\s+', ' ', text)
        
        # Remover líneas muy cortas (probablemente metadata/ruido)
        lines = []
        for line in text.split('.'):
            line = line.strip()
            # Solo conservar oraciones con contenido significativo
            if len(line) > 30:  # Mínimo 30 caracteres
                lines.append(line)
        
        cleaned_text = '. '.join(lines)
        
        # Limpieza final de espacios
        cleaned_text = cleaned_text.strip()
        
        elapsed = time.time() - start_time
        word_count = len(cleaned_text.split())
        
        logger.debug(f"← clean_html_content() → {len(cleaned_text)} chars, {word_count} palabras ({elapsed:.3f}s)")
        logger.info(f"✅ HTML limpiado: {len(html)} → {len(cleaned_text)} chars ({word_count} palabras)")
        
        return cleaned_text
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Error limpiando HTML ({elapsed:.3f}s): {type(e).__name__}: {e}", exc_info=True)
        # Fallback: intentar extraer texto básico
        try:
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception as fallback_error:
            # Último recurso: devolver HTML crudo
            logger.error(f"❌ Fallback también falló: {type(fallback_error).__name__}: {fallback_error}")
            logger.warning(f"⚠️  Devolviendo HTML crudo ({len(html)} chars)")
            return html


def prepare_article_for_llm(article: dict) -> dict:
    """
    Prepara un artículo individual para ser procesado por el LLM.
    
    Args:
        article: Diccionario con datos del artículo de TT-RSS
        
    Returns:
        Diccionario con campos limpios y preparados
    """
    article_id = article.get('id', 'N/A')
    title = article.get('title', 'Sin título')
    raw_content_len = len(article.get('content', ''))
    
    logger.debug(f"→ prepare_article_for_llm(id={article_id}, title='{title[:50]}...', content={raw_content_len} chars)")
    
    cleaned_content = clean_html_content(article.get('content', ''))
    
    prepared = {
        'id': article.get('id'),
        'title': article.get('title', 'Sin título'),
        'content': cleaned_content,
        'link': article.get('link', ''),
        'feed_id': article.get('feed_id'),  # ← ESTO FALTABA
        'feed_title': article.get('feed_title', 'Desconocido'),
        'updated': article.get('updated'),
    }
    
    word_count = len(cleaned_content.split()) if cleaned_content else 0
    logger.debug(f"← prepare_article_for_llm() → content={len(cleaned_content)} chars, {word_count} palabras")
    
    return prepared


def prepare_articles_for_llm(articles: list[dict]) -> list[dict]:
    """
    Prepara múltiples artículos para ser procesados por el LLM.
    
    Si el contenido es insuficiente y SCRAPING_ENABLED=true,
    intenta obtener contenido completo desde la URL.
    
    Args:
        articles: Lista de artículos de TT-RSS
        
    Returns:
        Lista de artículos limpios y preparados
    """
    import time
    from src.services.scraper import scrape_articles_parallel
    from src.config import settings
    
    logger.debug(f"→ prepare_articles_for_llm({len(articles)} artículos)")
    logger.info(f"Preparando {len(articles)} artículos para LLM...")
    
    start_time = time.time()
    prepared = []
    articles_needing_scraping = []
    
    # Primera pasada: intentar con contenido de TT-RSS
    for article in articles:
        try:
            prepared_article = prepare_article_for_llm(article)
            
            # Validar contenido
            content = prepared_article['content']
            word_count = len(content.split()) if content else 0
            
            if word_count >= settings.SCRAPING_MIN_WORDS:
                # ✅ Suficiente contenido
                prepared.append(prepared_article)
                logger.debug(f"✅ Artículo '{prepared_article['title'][:40]}...' OK ({word_count} palabras)")
            else:
                # ⚠️ Contenido insuficiente, marcar para scraping
                logger.debug(
                    f"⚠️  Contenido insuficiente para '{prepared_article['title'][:40]}...' "
                    f"({word_count} palabras, mínimo {settings.SCRAPING_MIN_WORDS})"
                )
                articles_needing_scraping.append((article, prepared_article, word_count))
                
        except Exception as e:
            article_id = article.get('id', 'N/A')
            title = article.get('title', 'Sin título')[:40]
            logger.error(f"❌ Error preparando artículo {article_id} ('{title}...'): {e}", exc_info=True)
            continue
    
    logger.debug(f"Primera pasada: {len(prepared)} artículos OK, {len(articles_needing_scraping)} necesitan scraping")
    
    # Segunda pasada: scraping de artículos con contenido insuficiente
    if articles_needing_scraping and settings.SCRAPING_ENABLED:
        logger.info(
            f"🔍 Intentando scraping para {len(articles_needing_scraping)} artículos "
            f"con contenido insuficiente"
        )
        
        # Extraer artículos originales para scraping
        articles_to_scrape = [item[0] for item in articles_needing_scraping]
        
        # Scraping en paralelo
        scraped_contents = scrape_articles_parallel(articles_to_scrape)
        
        # Procesar resultados de scraping
        for original_article, prepared_article, original_word_count in articles_needing_scraping:
            url = original_article.get('link')
            scraped_html = scraped_contents.get(url)
            
            if scraped_html:
                # Limpiar contenido scrapeado
                clean_content = clean_html_content(scraped_html)
                scraped_word_count = len(clean_content.split())
                
                if scraped_word_count >= settings.SCRAPING_MIN_WORDS:
                    # ✅ Scraping exitoso
                    prepared_article['content'] = clean_content
                    prepared.append(prepared_article)
                    logger.info(
                        f"✅ Scraping exitoso para '{prepared_article['title'][:40]}...': "
                        f"{original_word_count} → {scraped_word_count} palabras"
                    )
                    logger.debug(f"   URL scrapeada: {url}")
                else:
                    # ❌ Scraping también dio poco contenido
                    logger.warning(
                        f"⚠️  Artículo '{prepared_article['title'][:40]}...' descartado: "
                        f"contenido insuficiente incluso después de scraping "
                        f"({scraped_word_count} palabras, URL: {url})"
                    )
            else:
                # ❌ Scraping falló
                logger.warning(
                    f"⚠️  Artículo '{prepared_article['title'][:40]}...' descartado: "
                    f"scraping falló ({original_word_count} palabras originales, URL: {url})"
                )
    
    elif articles_needing_scraping:
        # Scraping deshabilitado, descartar artículos con contenido insuficiente
        logger.debug(f"Scraping deshabilitado, descartando {len(articles_needing_scraping)} artículos")
        for _, prepared_article, word_count in articles_needing_scraping:
            logger.warning(
                f"⚠️  Artículo '{prepared_article['title'][:40]}...' descartado: "
                f"contenido insuficiente ({word_count} palabras, "
                f"scraping deshabilitado)"
            )
    
    elapsed = time.time() - start_time
    logger.debug(f"← prepare_articles_for_llm() → {len(prepared)} artículos ({elapsed:.2f}s)")
    logger.info(f"✅ Preparados {len(prepared)}/{len(articles)} artículos para LLM en {elapsed:.2f}s")
    
    return prepared


def estimate_token_count(text: str) -> int:
    """
    Estima el número de tokens en un texto.
    
    Usa la aproximación: 1 token ≈ 4 caracteres para español.
    
    Args:
        text: Texto a estimar
        
    Returns:
        Número estimado de tokens
    """
    estimated = len(text) // 4
    logger.debug(f"→ estimate_token_count({len(text)} chars) → {estimated} tokens")
    return estimated


def truncate_article_if_needed(article: dict, max_tokens: int = 500) -> dict:
    """
    Trunca el contenido de un artículo si excede el límite de tokens.
    
    Args:
        article: Artículo preparado
        max_tokens: Límite máximo de tokens por artículo
        
    Returns:
        Artículo con contenido truncado si es necesario
    """
    article_id = article.get('id', 'N/A')
    title = article.get('title', 'Sin título')[:40]
    content = article['content']
    estimated_tokens = estimate_token_count(content)
    
    logger.debug(f"→ truncate_article_if_needed(id={article_id}, title='{title}...', ~{estimated_tokens} tokens, max={max_tokens})")
    
    if estimated_tokens > max_tokens:
        # Truncar a aprox max_tokens
        max_chars = max_tokens * 4
        article['content'] = content[:max_chars] + "..."
        logger.debug(
            f"← truncate_article_if_needed() → TRUNCADO: "
            f"'{title}...' de ~{estimated_tokens} a ~{max_tokens} tokens"
        )
    else:
        logger.debug(f"← truncate_article_if_needed() → sin cambios (~{estimated_tokens} tokens)")
    
    return article


def group_articles_by_category(
    articles: list[dict],
    feed_to_category_map: dict
) -> dict[str, list[dict]]:
    """
    Agrupa artículos por categoría usando el mapeo feed → categoría.
    
    Args:
        articles: Lista de artículos
        feed_to_category_map: Mapeo de feed_id a información de categoría
        
    Returns:
        Dict con categorías como keys y listas de artículos como values
    """
    logger.debug(f"→ group_articles_by_category({len(articles)} artículos, {len(feed_to_category_map)} feeds en mapa)")
    logger.info(f"Agrupando {len(articles)} artículos por categoría...")
    
    grouped = {}
    unmapped = []
    
    for article in articles:
        feed_id = article.get('feed_id')
        
        if feed_id in feed_to_category_map:
            cat_name = feed_to_category_map[feed_id]['cat_name']
            
            if cat_name not in grouped:
                grouped[cat_name] = []
                logger.debug(f"Nueva categoría encontrada: {cat_name}")
            
            grouped[cat_name].append(article)
        else:
            unmapped.append(article)
            logger.debug(f"Artículo sin mapeo: feed_id={feed_id}, título='{article.get('title', '')[:40]}...'")
    
    # Agregar artículos sin categoría a "Uncategorized"
    if unmapped:
        logger.warning(f"⚠️  {len(unmapped)} artículos sin mapeo de categoría, agregados a 'Uncategorized'")
        grouped['Uncategorized'] = unmapped
    
    # Log resumen
    category_summary = {cat: len(arts) for cat, arts in grouped.items()}
    logger.debug(f"← group_articles_by_category() → {len(grouped)} categorías")
    logger.debug(f"Distribución: {category_summary}")
    logger.info(f"✅ Artículos agrupados en {len(grouped)} categorías")
    
    return grouped