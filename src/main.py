"""
Punto de entrada principal de la aplicación.
Orquesta el flujo completo del procesamiento de noticias.
"""
import sys
from src.config import settings
from src.utils import logger


def validate_configuration() -> bool:
    """
    Valida que todas las configuraciones requeridas estén presentes.

    Returns:
        True si la configuración es válida, False en caso contrario
    """
    import time
    
    logger.debug("→ validate_configuration()")
    logger.info("Validando configuración...")
    
    start_time = time.time()
    is_valid, errors = settings.validate()
    elapsed = time.time() - start_time

    if not is_valid:
        logger.debug(f"← validate_configuration() → False ({len(errors)} errores, {elapsed:.3f}s)")
        logger.error("❌ Configuración inválida. Errores encontrados:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\n💡 Revisa tu archivo .env y compáralo con .env.example")
        return False

    logger.debug(f"← validate_configuration() → True ({elapsed:.3f}s)")
    logger.info("✅ Configuración validada correctamente")
    return True


def main():
    """Función principal de la aplicación."""
    logger.debug("→ main()")
    logger.info("=" * 60)
    logger.info("🚀 Iniciando RSS News Digest Bot")
    logger.info("=" * 60)

    # Validar configuración
    logger.debug("Iniciando validación de configuración...")
    if not validate_configuration():
        logger.debug("← main() → exit(1) [validación falló]")
        sys.exit(1)

    # Mostrar configuración (enmascarada)
    logger.debug("Obteniendo configuración enmascarada...")
    logger.info("📋 Configuración cargada:")
    config = settings.get_masked_config()
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
        logger.debug(f"    [config] {key}={value}")

    logger.info("\n" + "=" * 60)
    logger.info("⚠️  ETAPA 1 COMPLETADA - Estructura Base")
    logger.info("=" * 60)
    logger.debug("Estado del sistema: operativo")
    logger.info("✅ Sistema de configuración operativo")
    logger.info("✅ Logging configurado")
    logger.info("✅ Validación de entorno funcionando")
    logger.info("\n📝 Próximos pasos:")
    logger.info("  1. Implementar cliente TT-RSS (Etapa 2)")
    logger.info("  2. Integrar generación de resúmenes (Etapa 3)")
    logger.info("  3. Configurar bot de Telegram (Etapa 4)")
    logger.info("  4. Conectar con Wallabag (Etapa 5)")
    logger.info("  5. Dockerizar la aplicación (Etapa 6)")
    logger.info("=" * 60)
    
    logger.debug("← main() → exit(0) [éxito]")


if __name__ == "__main__":
    try:
        logger.debug("=== Iniciando ejecución ===")
        main()
    except KeyboardInterrupt:
        logger.debug("Ejecución interrumpida por usuario (KeyboardInterrupt)")
        logger.info("\n⚠️  Ejecución interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.debug(f"Excepción crítica capturada: {type(e).__name__}: {e}")
        logger.exception(f"❌ Error crítico: {e}")
        sys.exit(1)