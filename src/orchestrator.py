"""
Orquestador de producción para RSS Digest Bot.
Automatiza el flujo completo: obtener artículos → resumir → enviar → marcar.

Este módulo coordina todos los componentes del sistema para ejecutar el digest
diario de forma automatizada, sin intervención manual.

Uso:
    from src.orchestrator import run_daily_digest
    
    # Ejecutar digest diario
    result = run_daily_digest()
    
    # Ejecutar con rango personalizado
    result = run_daily_digest(since_hours=48)
    
    # Solo obtener estadísticas sin enviar
    result = run_daily_digest(dry_run=True)
"""
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from src.config import settings
from src.utils.logger import logger
from src.clients import TTRSSClient, LLMClient, TelegramClient
from src.services import (
    prepare_articles_for_llm,
    group_articles_by_category,
    TelegramDispatcher
)
from src.db import StateManager


# ============================================================================
# VALIDACIÓN Y CONFIGURACIÓN
# ============================================================================

def validate_environment() -> Tuple[bool, List[str]]:
    """
    Valida que el entorno esté correctamente configurado.
    
    Returns:
        Tupla (es_válido, lista_errores)
    """
    logger.debug("→ validate_environment()")
    
    is_valid, errors = settings.validate()
    
    if not is_valid:
        logger.error("❌ Configuración inválida:")
        for error in errors:
            logger.error(f"  - {error}")
    else:
        logger.info("✅ Configuración validada correctamente")
    
    logger.debug(f"← validate_environment() → {is_valid}")
    return is_valid, errors


def show_configuration():
    """Muestra la configuración actual (enmascarada)."""
    logger.debug("→ show_configuration()")
    
    config = settings.get_masked_config()
    logger.info("📋 Configuración:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    logger.debug("← show_configuration()")


# ============================================================================
# ORQUESTADOR PRINCIPAL
# ============================================================================

def run_daily_digest(
    since_hours: Optional[int] = None,
    dry_run: bool = False,
    mark_as_read: bool = False
) -> Dict:
    """
    Ejecuta el digest diario completo.
    
    Este es el punto de entrada principal para la ejecución automatizada.
    Coordina todos los componentes:
    
    1. Obtiene artículos no leídos de TT-RSS
    2. Prepara y agrupa artículos por categoría
    3. Genera resúmenes con Gemini LLM
    4. Envía resúmenes al supergrupo de Telegram
    5. Marca artículos como leídos (opcional)
    
    Args:
        since_hours: Filtrar artículos de las últimas N horas
                    (None = usar ARTICLES_MAX_AGE_HOURS del .env)
        dry_run: Si True, solo obtiene estadísticas sin enviar a Telegram
        mark_as_read: Si True, marca artículos como leídos después de enviar
        
    Returns:
        Dict con estadísticas de la ejecución:
        {
            'status': 'success' | 'no_articles' | 'error',
            'articles_fetched': int,
            'articles_processed': int,
            'categories': int,
            'summaries_generated': int,
            'messages_sent': int,
            'articles_marked': int,
            'elapsed_time': float,
            'error': str (solo si status='error')
        }
        
    Raises:
        Exception: Si hay un error crítico en la ejecución
    """
    start_time = time.time()
    
    # Determinar rango de horas
    hours = since_hours or settings.ARTICLES_MAX_AGE_HOURS
    
    logger.debug(f"→ run_daily_digest(since_hours={since_hours}, dry_run={dry_run}, mark_as_read={mark_as_read})")
    logger.debug(f"Usando rango de {hours} horas")
    
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO DIGEST DIARIO")
    logger.info("=" * 70)
    logger.info(f"📅 Rango: últimas {hours} horas")
    logger.info(f"🔄 Modo: {'DRY-RUN (sin enviar)' if dry_run else 'PRODUCCIÓN'}")
    logger.info(f"✓ Marcar como leído: {'Sí' if mark_as_read else 'No'}")
    logger.info("=" * 70)
    
    result = {
        'status': 'error',
        'articles_fetched': 0,
        'articles_processed': 0,
        'categories': 0,
        'summaries_generated': 0,
        'messages_sent': 0,
        'articles_marked': 0,
        'elapsed_time': 0.0,
        'hours': hours,
        'dry_run': dry_run
    }
    
    try:
        # ====================================================================
        # PASO 1: Obtener artículos de TT-RSS
        # ====================================================================
        logger.info("\n📰 PASO 1/5: Obteniendo artículos de TT-RSS...")
        
        ttrss = TTRSSClient(
            url=settings.TTRSS_URL,
            username=settings.TTRSS_USER,
            password=settings.TTRSS_PASSWORD
        )
        
        # Login
        logger.debug("Iniciando sesión en TT-RSS...")
        if not ttrss.login():
            error_msg = "No se pudo iniciar sesión en TT-RSS"
            logger.error(f"❌ {error_msg}")
            logger.debug(f"URL: {settings.TTRSS_URL}, Usuario: {settings.TTRSS_USER}")
            result['error'] = error_msg
            result['status'] = 'error'
            logger.debug(f"← run_daily_digest() → {result['status']}")
            return result
        
        logger.info("✅ Sesión iniciada en TT-RSS")
        
        # Obtener artículos no leídos
        logger.info(f"Buscando artículos no leídos (últimas {hours}h)...")
        articles, has_more = ttrss.get_all_unread_articles(since_hours=hours)
        
        result['articles_fetched'] = len(articles)
        
        if not articles:
            logger.info("ℹ️  No hay artículos no leídos para procesar")
            result['status'] = 'no_articles'
            result['elapsed_time'] = time.time() - start_time
            logger.info(f"\n⏱️  Tiempo total: {result['elapsed_time']:.2f}s")
            logger.debug(f"← run_daily_digest() → {result['status']}")
            return result
        
        logger.info(f"✅ Obtenidos {len(articles)} artículos")
        logger.debug(f"IDs de muestra: {[a.get('id') for a in articles[:5]]}...")
        if has_more:
            logger.warning(f"⚠️  Hay más artículos disponibles (límite alcanzado)")
        
        # ====================================================================
        # PASO 2: Preparar y agrupar artículos
        # ====================================================================
        logger.info("\n🗂️  PASO 2/5: Preparando y agrupando artículos...")
        
        # Preparar artículos (enriquecer metadatos)
        logger.debug("Preparando artículos para LLM...")
        prepared_articles = prepare_articles_for_llm(articles)
        logger.info(f"✅ Preparados {len(prepared_articles)} artículos")
        
        # Obtener feeds y categorías para mapeo
        logger.debug("Obteniendo feeds y categorías de TT-RSS...")
        feeds = ttrss.get_feeds()
        categories = ttrss.get_categories()
        
        # Construir mapeo feed → categoría
        logger.debug("Construyendo mapeo feed → categoría...")
        feed_map = ttrss.build_feed_to_category_map(feeds, categories)
        logger.debug(f"Mapa construido: {len(feed_map)} feeds")
        
        # Agrupar por categoría
        logger.debug("Agrupando artículos por categoría...")
        articles_by_category = group_articles_by_category(prepared_articles, feed_map)
        
        result['articles_processed'] = len(prepared_articles)
        result['categories'] = len(articles_by_category)
        
        logger.info(f"✅ Agrupados en {len(articles_by_category)} categorías:")
        for cat_name, cat_articles in articles_by_category.items():
            logger.info(f"   • {cat_name}: {len(cat_articles)} artículos")
        
        # ====================================================================
        # PASO 3: Generar resúmenes con LLM
        # ====================================================================
        logger.info("\n🤖 PASO 3/5: Generando resúmenes con Gemini...")
        
        llm_client = LLMClient(
            api_key=settings.GOOGLE_API_KEY,
            model=settings.GOOGLE_MODEL
        )
        
        logger.info(f"Modelo: {settings.GOOGLE_MODEL}")
        logger.info("⏳ Generando resúmenes (puede tardar varios minutos)...")
        
        summary_start = time.time()
        summaries = llm_client.generate_summaries_by_category(articles_by_category)
        summary_elapsed = time.time() - summary_start
        
        result['summaries_generated'] = len(summaries)
        
        logger.info(f"✅ Generados {len(summaries)} resúmenes en {summary_elapsed:.1f}s")
        
        # Mostrar preview de resúmenes
        logger.debug("Preview de resúmenes generados:")
        for cat_name, summary in summaries.items():
            preview = summary[:100].replace('\n', ' ')
            logger.debug(f"  {cat_name}: {preview}...")
        
        # ====================================================================
        # PASO 4: Enviar a Telegram
        # ====================================================================
        logger.info("\n📱 PASO 4/5: Enviando resúmenes a Telegram...")
        
        if dry_run:
            logger.info("ℹ️  Modo DRY-RUN: Omitiendo envío a Telegram")
            result['messages_sent'] = 0
        else:
            telegram_client = TelegramClient(
                bot_token=settings.TELEGRAM_BOT_TOKEN
            )
            
            # StateManager siempre disponible para persistir URLs, estado de sesión,
            # y otras operaciones de estado (el modo supergroup además lo requiere)
            state_manager = StateManager()
            
            dispatcher = TelegramDispatcher(
                telegram_client=telegram_client,
                state_manager=state_manager
            )
            
            logger.info(f"Modo: {settings.TELEGRAM_MODE}")
            logger.info("⏳ Enviando resúmenes (puede tardar varios minutos)...")
            
            send_start = time.time()
            dispatcher.send_digest(
                summaries=summaries,
                articles_by_category=articles_by_category
            )
            send_elapsed = time.time() - send_start
            
            # Contar mensajes enviados (aproximado por categorías)
            result['messages_sent'] = len(summaries)
            
            logger.info(f"✅ Digest enviado en {send_elapsed:.1f}s")
        
        # ====================================================================
        # PASO 5: Marcar artículos como leídos
        # ====================================================================
        logger.info("\n✓ PASO 5/5: Marcando artículos como leídos...")
        
        if not mark_as_read:
            logger.info("ℹ️  Marcado deshabilitado (mark_as_read=False)")
            result['articles_marked'] = 0
        elif dry_run:
            logger.info("ℹ️  Modo DRY-RUN: Omitiendo marcado de artículos")
            result['articles_marked'] = 0
        else:
            # Marcar todos los artículos procesados como leídos
            article_ids = [article['id'] for article in articles]
            
            logger.info(f"Marcando {len(article_ids)} artículos como leídos...")
            
            marked_count = 0
            failed_ids = []
            
            # Usar el método correcto mark_articles_as_read
            try:
                ttrss.mark_articles_as_read(article_ids)
                marked_count = len(article_ids)
            except Exception as e:
                logger.error(f"❌ Error marcando artículos como leídos: {e}", exc_info=True)
                failed_ids = article_ids
            
            result['articles_marked'] = marked_count
            
            if failed_ids:
                logger.warning(f"⚠️  Fallaron {len(failed_ids)} artículos al marcar")
                logger.debug(f"IDs fallidos: {failed_ids}")
            
            logger.info(f"✅ Marcados {marked_count}/{len(article_ids)} artículos")
        
        # ====================================================================
        # FINALIZACIÓN
        # ====================================================================
        result['status'] = 'success'
        result['elapsed_time'] = time.time() - start_time
        
        logger.info("\n" + "=" * 70)
        logger.info("🎉 DIGEST COMPLETADO EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   • Artículos obtenidos: {result['articles_fetched']}")
        logger.info(f"   • Artículos procesados: {result['articles_processed']}")
        logger.info(f"   • Categorías: {result['categories']}")
        logger.info(f"   • Resúmenes generados: {result['summaries_generated']}")
        logger.info(f"   • Mensajes enviados: {result['messages_sent']}")
        logger.info(f"   • Artículos marcados: {result['articles_marked']}")
        logger.info(f"   ⏱️  Tiempo total: {result['elapsed_time']:.1f}s")
        logger.info("=" * 70)
        logger.debug(f"← run_daily_digest() → {result['status']}")
        
        return result
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Ejecución interrumpida por el usuario")
        result['error'] = 'Interrumpido por usuario'
        result['status'] = 'interrupted'
        result['elapsed_time'] = time.time() - start_time
        logger.debug(f"← run_daily_digest() → {result['status']}")
        return result
        
    except Exception as e:
        logger.exception(f"❌ Error crítico durante la ejecución: {e}")
        logger.debug(f"Estado al fallar: {result}")
        result['error'] = str(e)
        result['status'] = 'error'
        result['elapsed_time'] = time.time() - start_time
        logger.debug(f"← run_daily_digest() → {result['status']}")
        return result


# ============================================================================
# PUNTO DE ENTRADA PARA TESTING/DEBUG
# ============================================================================

def main():
    """
    Punto de entrada para ejecutar el orquestador directamente.
    
    Uso:
        python -m src.orchestrator              # Digest normal
        python -m src.orchestrator --dry-run    # Sin enviar a Telegram
        python -m src.orchestrator --hours 48   # Últimas 48 horas
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Orquestador de RSS Digest Bot'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=None,
        help=f'Horas hacia atrás (default: {settings.ARTICLES_MAX_AGE_HOURS})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Ejecutar sin enviar a Telegram'
    )
    parser.add_argument(
        '--mark',
        action='store_true',
        help='Marcar artículos como leídos (opt-in explícito)'
    )
    
    args = parser.parse_args()
    
    # Validar configuración
    logger.info("🔍 Validando configuración...")
    is_valid, errors = validate_environment()
    
    if not is_valid:
        logger.error("\n💡 Revisa tu archivo .env y compáralo con .env.example")
        sys.exit(1)
    
    show_configuration()
    
    # Ejecutar digest
    result = run_daily_digest(
        since_hours=args.hours,
        dry_run=args.dry_run,
        mark_as_read=args.mark
    )
    
    # Exit code según resultado
    exit_codes = {
        'success': 0,
        'no_articles': 0,  # No es un error
        'interrupted': 130,  # SIGINT
        'error': 1
    }
    
    exit_code = exit_codes.get(result['status'], 1)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
