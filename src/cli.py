"""
Interfaz de línea de comandos (CLI) para RSS Digest Bot.
Proporciona comandos para ejecutar el digest y otras operaciones.

Uso:
    # Digest normal (últimas 24h del .env)
    python -m src.cli digest
    
    # Digest con rango personalizado
    python -m src.cli digest --hours 48
    python -m src.cli digest --hours 168
    
    # Dry-run (sin enviar a Telegram)
    python -m src.cli digest --dry-run
    
    # Sin marcar como leídos
    python -m src.cli digest --no-mark
    
    # Ver estadísticas
    python -m src.cli stats
    
    # Validar configuración
    python -m src.cli validate
"""
import sys
import click
from pathlib import Path

from src.config import settings
from src.utils.logger import logger
from src.orchestrator import (
    run_daily_digest,
    validate_environment,
    show_configuration
)


# ============================================================================
# GRUPO PRINCIPAL DE COMANDOS
# ============================================================================

@click.group()
@click.version_option(version='1.0.0', prog_name='RSS Digest Bot')
def cli():
    """
    🤖 RSS Digest Bot - Automatización de resúmenes de noticias.
    
    Este bot obtiene artículos de TT-RSS, genera resúmenes con Gemini,
    y los envía a un supergrupo de Telegram.
    """
    pass


# ============================================================================
# COMANDO: digest
# ============================================================================

@cli.command()
@click.option(
    '--hours',
    type=int,
    default=None,
    metavar='N',
    help=f'Procesar artículos de las últimas N horas (default: {settings.ARTICLES_MAX_AGE_HOURS}h del .env)'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Modo de prueba: procesa pero NO envía a Telegram ni marca como leído'
)
@click.option(
    '--mark',
    is_flag=True,
    help='Marcar artículos como leídos después de procesar (requiere acción explícita)'
)
@click.option(
    '--quiet',
    is_flag=True,
    help='Modo silencioso: solo muestra errores'
)
def digest(hours, dry_run, mark, quiet):
    """
    Ejecutar digest diario de artículos.
    
    Este comando coordina todo el flujo:
    
    \b
    1. Obtiene artículos no leídos de TT-RSS
    2. Genera resúmenes usando Gemini LLM
    3. Envía resúmenes al supergrupo de Telegram
    4. Marca artículos como leídos (opcional)
    
    \b
    Ejemplos:
    
    \b
      # Digest normal (últimas 24h)
      $ python -m src.cli digest
    
    \b
      # Fin de semana (últimas 48h)
      $ python -m src.cli digest --hours 48
    
    \b
      # Después de vacaciones (última semana)
      $ python -m src.cli digest --hours 168
    
    \b
      # Prueba sin enviar
      $ python -m src.cli digest --dry-run
    """
    # Configurar nivel de logging si es modo silencioso
    if quiet:
        import logging
        logging.getLogger().setLevel(logging.ERROR)
    
    try:
        # Ejecutar digest
        result = run_daily_digest(
            since_hours=hours,
            dry_run=dry_run,
            mark_as_read=mark
        )
        
        # Mostrar resultado resumido
        if result['status'] == 'success':
            click.echo(
                f"\n✅ Digest completado exitosamente\n"
                f"   📰 Artículos procesados: {result['articles_processed']}\n"
                f"   📱 Mensajes enviados: {result['messages_sent']}\n"
                f"   ⏱️  Tiempo: {result['elapsed_time']:.1f}s"
            )
            sys.exit(0)
            
        elif result['status'] == 'no_articles':
            click.echo(
                f"\nℹ️  Sin artículos no leídos de las últimas {result['hours']} horas"
            )
            sys.exit(0)
            
        elif result['status'] == 'interrupted':
            click.echo("\n⚠️  Ejecución interrumpida por el usuario")
            sys.exit(130)
            
        else:  # error
            click.echo(
                f"\n❌ Error durante la ejecución: {result.get('error', 'Error desconocido')}",
                err=True
            )
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"\n❌ Error crítico: {e}", err=True)
        logger.exception(e)
        sys.exit(1)


# ============================================================================
# COMANDO: validate
# ============================================================================

@cli.command()
def validate():
    """
    Validar configuración del sistema.
    
    Verifica que todas las variables de entorno requeridas estén presentes
    y tengan valores válidos.
    
    \b
    Ejemplo:
      $ python -m src.cli validate
    """
    click.echo("🔍 Validando configuración...\n")
    
    is_valid, errors = validate_environment()
    
    if not is_valid:
        click.echo("❌ Configuración inválida:\n", err=True)
        for error in errors:
            click.echo(f"  • {error}", err=True)
        click.echo("\n💡 Revisa tu archivo .env y compáralo con .env.example")
        sys.exit(1)
    
    click.echo("✅ Configuración válida\n")
    show_configuration()
    sys.exit(0)


# ============================================================================
# COMANDO: stats
# ============================================================================

@cli.command()
@click.option(
    '--hours',
    type=int,
    default=None,
    metavar='N',
    help=f'Ver estadísticas de las últimas N horas (default: {settings.ARTICLES_MAX_AGE_HOURS}h)'
)
def stats(hours):
    """
    Mostrar estadísticas de artículos sin procesarlos.
    
    Obtiene información sobre artículos no leídos disponibles en TT-RSS
    sin generar resúmenes ni enviar a Telegram.
    
    \b
    Ejemplos:
    
    \b
      # Estadísticas de últimas 24h
      $ python -m src.cli stats
    
    \b
      # Estadísticas de última semana
      $ python -m src.cli stats --hours 168
    """
    from src.clients import TTRSSClient
    
    hours_param = hours or settings.ARTICLES_MAX_AGE_HOURS
    
    click.echo(f"📊 Obteniendo estadísticas de las últimas {hours_param} horas...\n")
    
    try:
        # Conectar a TT-RSS
        ttrss = TTRSSClient(
            url=settings.TTRSS_URL,
            username=settings.TTRSS_USER,
            password=settings.TTRSS_PASSWORD
        )
        
        if not ttrss.login():
            click.echo("❌ No se pudo conectar a TT-RSS", err=True)
            sys.exit(1)
        
        # Obtener artículos
        articles, has_more = ttrss.get_all_unread_articles(since_hours=hours_param)
        
        if not articles:
            click.echo(f"ℹ️  No hay artículos no leídos de las últimas {hours_param} horas")
            sys.exit(0)
        
        # Agrupar por categoría
        from src.services import prepare_articles_for_llm, group_articles_by_category
        
        prepared = prepare_articles_for_llm(articles)
        grouped = group_articles_by_category(prepared)
        
        # Mostrar estadísticas
        click.echo(f"📰 Total de artículos: {len(articles)}")
        click.echo(f"📁 Categorías: {len(grouped)}\n")
        
        click.echo("Distribución por categoría:")
        for cat_name in sorted(grouped.keys()):
            count = len(grouped[cat_name])
            click.echo(f"  • {cat_name}: {count} artículo{'s' if count != 1 else ''}")
        
        if has_more:
            click.echo("\n⚠️  Hay más artículos disponibles (límite alcanzado)")
        
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        logger.exception(e)
        sys.exit(1)


# ============================================================================
# COMANDO: version
# ============================================================================

@cli.command()
def version():
    """
    Mostrar información de versión y configuración del sistema.
    """
    import platform
    
    click.echo("🤖 RSS Digest Bot")
    click.echo("=" * 50)
    click.echo(f"Versión: 1.0.0 (ETAPA 8)")
    click.echo(f"Python: {platform.python_version()}")
    click.echo(f"Plataforma: {platform.system()} {platform.release()}")
    click.echo("=" * 50)
    click.echo("\nComponentes:")
    click.echo("  ✓ TT-RSS Client")
    click.echo("  ✓ Gemini LLM Client")
    click.echo("  ✓ Telegram Bot")
    click.echo("  ✓ Wallabag Integration")
    click.echo("  ✓ Orchestrator")
    click.echo("\nEtapas completadas: 1-8")
    click.echo("Repositorio: https://github.com/tu-usuario/rss-resume-bot")


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

def main():
    """Punto de entrada principal del CLI."""
    cli()


if __name__ == '__main__':
    main()
