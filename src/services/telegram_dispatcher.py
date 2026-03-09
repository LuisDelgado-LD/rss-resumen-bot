"""
Dispatcher de mensajes de Telegram.
Maneja el envío según el modo configurado (chat 1:1 o supergroup).
"""
import logging
import time
import re
from typing import Optional
from datetime import datetime

from src.config import settings
from src.clients.telegram_client import TelegramClient
from src.db.state_manager import StateManager


logger = logging.getLogger(__name__)


class TelegramDispatcher:
    """
    Dispatcher que maneja el envío de resúmenes según el modo configurado.
    
    Modos:
    - chat: Envío a chat 1:1 con índice + botones (modo actual)
    - supergroup: Envío a topics con 1 mensaje por resumen
    """
    
    def __init__(
        self,
        telegram_client: TelegramClient,
        state_manager: Optional[StateManager] = None
    ):
        """
        Inicializa el dispatcher.
        
        Args:
            telegram_client: Cliente de Telegram
            state_manager: Gestor de estado (requerido para modo supergroup)
        """
        logger.debug(f"→ TelegramDispatcher.__init__(mode={settings.TELEGRAM_MODE})")
        
        self.client = telegram_client
        self.mode = settings.TELEGRAM_MODE
        self.state_manager = state_manager
        
        # Validar dependencias según modo
        if self.mode == "supergroup" and state_manager is None:
            raise ValueError("StateManager es requerido para modo 'supergroup'")
        
        # Cargar topics si es supergroup
        if self.mode == "supergroup":
            self.topics_map = settings.get_topics_map()
            logger.info(f"Topics cargados: {len(self.topics_map)} categorías")
            logger.debug(f"Categorías: {list(self.topics_map.keys())}")
        
        logger.info(f"TelegramDispatcher inicializado en modo: {self.mode}")
        logger.debug(f"← TelegramDispatcher.__init__()")
    
    def send_digest(
        self,
        summaries: dict[str, str],
        articles_by_category: dict[str, list[dict]]
    ):
        """
        Envía el digest completo según el modo configurado.
        
        Args:
            summaries: Dict con categoría → resumen completo
            articles_by_category: Dict con categoría → lista de artículos
        """
        logger.debug(f"→ send_digest(categories={len(summaries)}, mode={self.mode})")
        logger.info(f"Enviando digest ({len(summaries)} categorías) en modo {self.mode}...")
        
        if self.mode == "chat":
            self._send_chat_mode(summaries, articles_by_category)
        elif self.mode == "supergroup":
            self._send_supergroup_mode(summaries, articles_by_category)
        else:
            raise ValueError(f"Modo desconocido: {self.mode}")
        
        # Persistir mapa ID → URL para que el bot pueda resolver /url <ID>
        if self.state_manager is not None:
            all_articles = [
                article
                for arts in articles_by_category.values()
                for article in arts
            ]
            saved = self.state_manager.save_article_urls(all_articles)
            logger.debug(f"URLs persistidas tras send_digest: {saved}")

        logger.debug(f"← send_digest()")
    
    def _send_chat_mode(
        self,
        summaries: dict[str, str],
        articles_by_category: dict[str, list[dict]]
    ):
        """
        Envía en modo chat 1:1 (comportamiento actual).
        
        Args:
            summaries: Dict con categoría → resumen
            articles_by_category: Dict con categoría → artículos
        """
        logger.debug(f"→ _send_chat_mode(categories={len(summaries)})")
        logger.info("Enviando en modo chat 1:1...")
        
        # Enviar índice con botones
        self.client.send_summary_index(summaries, articles_by_category)
        
        logger.debug(f"← _send_chat_mode()")
        logger.info(f"✅ Índice enviado en modo chat")
    
    def _send_supergroup_mode(
        self,
        summaries: dict[str, str],
        articles_by_category: dict[str, list[dict]]
    ):
        """
        Envía en modo supergroup con topics.
        
        Estrategia:
        - Divide el resumen de Gemini en párrafos (separados por líneas en blanco)
        - Envía cada párrafo como mensaje individual al topic correspondiente
        - Extrae los IDs de artículos mencionados en cada párrafo para mapeo preciso
        - Mensaje final con estadísticas y botones de batch
        
        Args:
            summaries: Dict con categoría → resumen
            articles_by_category: Dict con categoría → artículos
        """
        logger.debug(f"→ _send_supergroup_mode(categories={len(summaries)})")
        logger.info("Enviando en modo supergroup...")
        
        total_messages = 0
        total_articles = 0
        
        # Enviar cada resumen a su topic correspondiente
        for category, summary in summaries.items():
            logger.debug(f"Procesando categoría: {category}")
            
            # Verificar que la categoría tenga topic configurado
            if category not in self.topics_map:
                logger.warning(f"⚠️  Categoría '{category}' no tiene topic configurado, saltando")
                continue
            
            topic_id = self.topics_map[category]
            articles = articles_by_category.get(category, [])
            num_articles = len(articles)
            
            logger.info(f"Enviando resumen de {category} al topic {topic_id} ({num_articles} artículos)...")
            
            # Dividir resumen en párrafos y enviar mensajes individuales
            paragraphs = self._split_summary_by_paragraphs(summary)
            messages_sent = 0
            
            for i, paragraph in enumerate(paragraphs, 1):
                # Extraer IDs de artículos mencionados en este párrafo
                mentioned_ids = self._extract_article_ids(paragraph)
                
                # Filtrar solo los IDs que existen en esta categoría
                valid_article_ids = [
                    aid for aid in mentioned_ids 
                    if any(article['id'] == aid for article in articles)
                ]
                
                # Enviar párrafo como mensaje individual (con logging y manejo de errores)
                try:
                    logger.debug(
                        f"→ Enviando párrafo {i}/{len(paragraphs)} a topic={topic_id} | category={category} | chars={len(paragraph)}"
                    )

                    start_ts = time.time()
                    message_id = self.client.send_summary_paragraph(
                        topic_id=topic_id,
                        category=category,
                        paragraph=paragraph,
                        paragraph_num=i,
                        total_paragraphs=len(paragraphs)
                    )
                    elapsed = time.time() - start_ts

                    logger.debug(
                        f"← Enviado párrafo {i}/{len(paragraphs)} → msg_id={message_id} (elapsed={elapsed:.2f}s)"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Error enviando párrafo {i} para category={category} to topic={topic_id}: {e}",
                        exc_info=True
                    )
                    # Continuar con los siguientes párrafos pero registrar el fallo
                    continue
                
                # Guardar mapeo SOLO si hay IDs válidos mencionados
                # (evita que párrafos introductorios marquen todos los artículos)
                if valid_article_ids:
                    self.state_manager.save_message_mapping(
                        message_id=message_id,
                        article_ids=valid_article_ids,
                        category=category,
                        timestamp=datetime.now()
                    )
                    logger.debug(f"✅ Mapeo guardado: msg {message_id} → {len(valid_article_ids)} artículos")
                else:
                    logger.debug(f"⚠️  Párrafo {i} sin IDs mencionados, no se guarda mapeo (msg {message_id})")
                
                messages_sent += 1
                
                # Log diferenciado según si tiene artículos o no
                if valid_article_ids:
                    logger.debug(f"✅ Párrafo {i}/{len(paragraphs)} enviado (msg_id: {message_id}, {len(valid_article_ids)} artículos)")
                else:
                    logger.debug(f"✅ Párrafo {i}/{len(paragraphs)} enviado (msg_id: {message_id}, sin artículos - introductorio)")
                
                # Pequeño delay entre párrafos de la misma categoría
                if i < len(paragraphs):
                    time.sleep(settings.TELEGRAM_MESSAGE_DELAY)
            
            total_messages += messages_sent
            total_articles += num_articles
            
            logger.info(f"✅ Resumen de {category} enviado ({messages_sent} mensajes, {num_articles} artículos)")
            
            # Enviar botones de gestión para este topic
            self._send_topic_buttons(
                topic_id=topic_id,
                category=category,
                num_articles=num_articles
            )
            
            # Delay entre categorías para evitar rate limiting
            time.sleep(settings.TELEGRAM_CATEGORY_DELAY)
        
        # Enviar mensaje final con estadísticas (sin topic = chat principal)
        logger.info("Enviando mensaje final con estadísticas al chat principal...")
        self._send_final_summary_message(
            total_categories=len(summaries),
            total_messages=total_messages,
            total_articles=total_articles,
            topic_id=None  # Chat principal (sin topic específico)
        )
        
        logger.debug(f"← _send_supergroup_mode() → {total_messages} mensajes, {total_articles} artículos")
        logger.info(f"✅ Digest enviado: {total_messages} resúmenes en {len(summaries)} categorías, {total_articles} artículos")
    
    def _send_topic_buttons(
        self,
        topic_id: int,
        category: str,
        num_articles: int
    ):
        """
        Envía botones de gestión para un topic específico.
        
        Args:
            topic_id: ID del topic
            category: Nombre de la categoría
            num_articles: Número de artículos en este topic
        """
        logger.debug(f"→ _send_topic_buttons(topic={topic_id}, cat={category}, articles={num_articles})")
        
        text = (
            f"📋 **Gestión de lecturas - {category}**\n\n"
            f"💡 **Marca estos {num_articles} artículos como leídos:**"
        )
        
        # Botones específicos para este topic/categoría
        buttons = [
            [
                {"text": f"✅ Marcar {category} como leído", "callback_data": f"category:mark:{category}"}
            ],
            [
                {"text": "🚫 Excluir de marcado masivo", "callback_data": f"category:exclude:{category}"}
            ]
        ]
        
        try:
            logger.debug(f"→ Enviando botones para category={category} to topic={topic_id} | buttons_count={len(buttons)}")
            start_ts = time.time()
            message_id = self.client.send_message_with_buttons(
                text=text,
                buttons=buttons,
                topic_id=topic_id
            )
            elapsed = time.time() - start_ts

            logger.debug(f"← _send_topic_buttons() → msg_id={message_id} (elapsed={elapsed:.2f}s)")
            logger.info(f"✅ Botones de gestión enviados al topic {topic_id} (msg_id: {message_id})")
        except Exception as e:
            logger.error(f"❌ Error enviando botones para topic={topic_id}, category={category}: {e}", exc_info=True)
            # No bloquear el envío global
            return None
    
    def _split_summary_by_paragraphs(self, summary: str) -> list[str]:
        """
        Divide un resumen en párrafos usando líneas en blanco como separadores.
        
        Args:
            summary: Resumen completo de Gemini
            
        Returns:
            Lista de párrafos (sin líneas vacías)
        """
        # Dividir por dobles saltos de línea (párrafos)
        paragraphs = [p.strip() for p in summary.split('\n\n') if p.strip()]
        
        logger.debug(f"Resumen dividido en {len(paragraphs)} párrafos")
        
        return paragraphs
    
    def _extract_article_ids(self, text: str) -> list[int]:
        """
        Extrae los IDs de artículos mencionados en un texto.
        Busca referencias en formato [123] (número entre corchetes).
        
        Args:
            text: Texto del párrafo
            
        Returns:
            Lista de IDs de artículos mencionados
        """
        # Patrón: [número]
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, text)
        
        # Convertir a enteros
        article_ids = [int(match) for match in matches]
        
        logger.debug(f"Extraídos {len(article_ids)} IDs del párrafo: {article_ids[:5]}{'...' if len(article_ids) > 5 else ''}")
        
        return article_ids
    
    def _send_final_summary_message(
        self,
        total_categories: int,
        total_messages: int,
        total_articles: int,
        topic_id: Optional[int] = None
    ):
        """
        Envía mensaje final con estadísticas y botones de batch marking global.
        
        Args:
            total_categories: Total de categorías procesadas
            total_messages: Total de mensajes enviados
            total_articles: Total de artículos
            topic_id: ID del topic donde enviar (default: None = chat principal)
        """
        logger.debug(f"→ _send_final_summary_message(cats={total_categories}, msgs={total_messages}, articles={total_articles})")
        
        date_str = datetime.now().strftime("%d/%m/%Y")
        
        text = (
            f"📊 **Resumen del día: {date_str}**\n\n"
            f"✅ Enviados: {total_messages} resúmenes en {total_categories} categorías\n"
            f"📰 Total artículos: {total_articles}\n\n"
            f"---\n\n"
            f"💡 **Reacciones en mensajes con artículos [ID]:**\n"
            f"❤️ 👍 🔥 → marca SOLO los artículos mencionados\n"
            f"🚫 → excluye del marcado masivo\n\n"
            f"🔽 **O usa botones de categoría para marcar todo:**"
        )
        
        # Botones para batch marking
        buttons = [
            [
                {"text": "Marcar TODOS como leídos", "callback_data": "batch:mark_all"},
                {"text": "Solo no reaccionados", "callback_data": "batch:mark_pending"}
            ]
        ]
        
        try:
            logger.debug(f"→ Enviando mensaje final (topics_summary) to topic={topic_id}")
            start_ts = time.time()
            message_id = self.client.send_message_with_buttons(
                text=text,
                buttons=buttons,
                topic_id=topic_id
            )
            elapsed = time.time() - start_ts

            logger.debug(f"← _send_final_summary_message() → msg_id={message_id} (elapsed={elapsed:.2f}s)")
            logger.info(f"✅ Mensaje final enviado (msg_id: {message_id})")
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje final: {e}", exc_info=True)
            return None
