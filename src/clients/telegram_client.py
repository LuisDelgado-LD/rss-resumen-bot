"""
Cliente para interactuar con Telegram Bot API.
Envía resúmenes de noticias con formato y botones de navegación.
"""
import logging
import json
import time
from typing import Optional
from datetime import datetime

from src.config import settings
from src.utils.http_helper import HTTPRequestHelper


logger = logging.getLogger(__name__)


class TelegramClientError(Exception):
    """Excepción base para errores del cliente Telegram."""
    pass


class TelegramClient:
    """Cliente para enviar mensajes a Telegram."""
    
    # Límite de caracteres por mensaje de Telegram
    MAX_MESSAGE_LENGTH = 4096
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        """
        Inicializa el cliente de Telegram.
        
        Args:
            bot_token: Token del bot (si no se proporciona, usa settings)
            chat_id: ID del chat destino (si no se proporciona, usa settings)
        """
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        
        if not self.bot_token or self.bot_token == "tu_bot_token":
            raise TelegramClientError(
                "TELEGRAM_BOT_TOKEN no configurado. "
                "Crea un bot en @BotFather y configura el token en .env"
            )
        
        if not self.chat_id or self.chat_id == "tu_chat_id":
            raise TelegramClientError(
                "TELEGRAM_CHAT_ID no configurado. "
                "Obtén tu chat ID de @userinfobot y configúralo en .env"
            )
        
        # Base URL para API
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Mapeo de IDs de artículos a URLs (para consultas)
        self.article_urls = {}
        
        logger.info(f"Cliente Telegram inicializado (chat_id: {self.chat_id})")
        logger.debug(f"→ Bot token: {self.bot_token[:10]}...")
    
    def _escape_markdown(self, text: str) -> str:
        """
        Escapa caracteres especiales para MarkdownV2 de Telegram.
        
        Args:
            text: Texto a escapar
            
        Returns:
            Texto escapado
        """
        # Caracteres que necesitan escape en MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        escaped = text
        for char in special_chars:
            escaped = escaped.replace(char, f'\\{char}')
        
        return escaped
    
    def _format_summary_header(
        self,
        category_name: str,
        num_articles: int,
        date: Optional[datetime] = None
    ) -> str:
        """
        Genera la cabecera del resumen.
        
        Args:
            category_name: Nombre de la categoría
            num_articles: Número de artículos
            date: Fecha del resumen (default: hoy)
            
        Returns:
            Cabecera formateada en MarkdownV2
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%d/%m")
        
        # Sin escape, luego lo escapamos todo junto
        header = f"📰 *Resumen {date_str} | {category_name} | {num_articles} artículos*\n\n"
        
        return header
    
    def _format_summary_for_telegram(
        self,
        category_name: str,
        summary: str,
        num_articles: int
    ) -> str:
        """
        Formatea un resumen para Telegram SIN MarkdownV2 (texto plano).
        
        Args:
            category_name: Nombre de la categoría
            summary: Resumen generado por el LLM
            num_articles: Número de artículos
            
        Returns:
            Texto formateado para Telegram
        """
        # Cabecera simple (sin markdown)
        date_str = datetime.now().strftime("%d/%m")
        header = f"📰 Resumen {date_str} | {category_name} | {num_articles} artículos\n\n"
        
        # El resumen ya viene con referencias [ID]
        # Lo dejamos como texto plano (sin escape)
        content = summary
        
        # Combinar
        formatted = header + content
        
        logger.debug(f"Resumen formateado: {len(formatted)} chars")
        
        return formatted
    
    def _split_long_message(self, text: str) -> list[str]:
        """
        Divide un mensaje largo en partes que caben en Telegram.
        Intenta dividir por párrafos para mantener coherencia.
        
        Args:
            text: Texto completo
            
        Returns:
            Lista de mensajes
        """
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return [text]
        
        parts = []
        current_part = ""
        
        # Dividir por párrafos (doble salto de línea)
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # Si el párrafo solo ya es muy largo, dividir por oraciones
            if len(paragraph) > self.MAX_MESSAGE_LENGTH:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    sentence_with_dot = sentence if sentence.endswith('.') else sentence + '.'
                    
                    if len(current_part) + len(sentence_with_dot) + 2 <= self.MAX_MESSAGE_LENGTH:
                        current_part += sentence_with_dot + ' '
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = sentence_with_dot + ' '
            else:
                # Intentar agregar el párrafo completo
                test_part = current_part + paragraph + '\n\n'
                
                if len(test_part) <= self.MAX_MESSAGE_LENGTH:
                    current_part = test_part
                else:
                    # No cabe, guardar parte actual y empezar nueva
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
        
        # Agregar última parte
        if current_part:
            parts.append(current_part.strip())
        
        logger.debug(f"Mensaje dividido en {len(parts)} partes (original: {len(text)} chars)")
        
        return parts
    
    def send_summary(
        self,
        category_name: str,
        summary: str,
        num_articles: int
    ) -> list[int]:
        """
        Envía un resumen de categoría.
        
        Args:
            category_name: Nombre de la categoría
            summary: Resumen generado
            num_articles: Número de artículos
            
        Returns:
            Lista de message_ids enviados
        """
        logger.info(f"→ Enviando resumen de {category_name} ({num_articles} artículos)")
        
        # Formatear
        formatted = self._format_summary_for_telegram(category_name, summary, num_articles)
        
        # Dividir si es necesario
        parts = self._split_long_message(formatted)
        
        message_ids = []
        
        for i, part in enumerate(parts, 1):
            try:
                logger.debug(f"Enviando parte {i}/{len(parts)} ({len(part)} chars)")
                
                # Enviar vía API directa
                url = f"{self.api_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': part
                    # Sin parse_mode - texto plano
                }
                
                response = HTTPRequestHelper.post(
                    url=url,
                    json_data=payload,
                    timeout=30,
                    context=f"Telegram sendMessage parte {i}/{len(parts)}"
                )
                
                result = response.json()
                
                if not result.get('ok'):
                    raise TelegramClientError(f"API error: {result.get('description')}")
                
                message_id = result['result']['message_id']
                message_ids.append(message_id)
                
                logger.debug(f"Mensaje enviado (id: {message_id})")
                
            except Exception as e:
                logger.error(f"❌ Error enviando parte {i}: {e}")
                raise TelegramClientError(f"Error enviando mensaje: {e}") from e
        
        logger.info(f"✅ Resumen de {category_name} enviado ({len(parts)} mensajes)")
        
        return message_ids
    
    def send_to_topic(
        self,
        topic_id: int,
        category: str,
        summary: str,
        num_articles: int
    ) -> int:
        """
        Envía un resumen a un topic específico de un supergrupo.
        Si el resumen es muy largo, lo divide en múltiples mensajes.
        
        Args:
            topic_id: ID del topic en el supergrupo
            category: Nombre de la categoría
            summary: Resumen generado
            num_articles: Número de artículos
            
        Returns:
            message_id del primer mensaje enviado
        """
        logger.debug(f"→ send_to_topic(topic={topic_id}, cat={category}, articles={num_articles})")
        logger.info(f"Enviando resumen de {category} al topic {topic_id}...")
        
        # Formatear mensaje
        formatted = self._format_summary_for_telegram(category, summary, num_articles)
        
        # Dividir si es necesario
        if len(formatted) > self.MAX_MESSAGE_LENGTH:
            logger.warning(f"⚠️  Resumen de {category} muy largo ({len(formatted)} chars), dividiendo en partes")
            parts = self._split_long_message(formatted)
            logger.info(f"📄 Resumen dividido en {len(parts)} mensajes")
        else:
            parts = [formatted]
        
        try:
            first_message_id = None
            
            for i, part in enumerate(parts, 1):
                url = f"{self.api_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'message_thread_id': topic_id,  # Enviar al topic específico
                    'text': part
                }
                
                response = HTTPRequestHelper.post(
                    url=url,
                    json_data=payload,
                    timeout=30,
                    context=f"Telegram sendMessage topic {topic_id} parte {i}/{len(parts)}"
                )
                
                result = response.json()
                
                if not result.get('ok'):
                    logger.error(f"❌ API error en categoría {category}")
                    raise TelegramClientError(f"API error: {result.get('description')}")
                
                message_id = result['result']['message_id']
                
                if first_message_id is None:
                    first_message_id = message_id
                
                logger.debug(f"Parte {i}/{len(parts)} enviada (msg_id: {message_id})")
                
                # Delay entre partes del mismo resumen
                if i < len(parts):
                    time.sleep(settings.TELEGRAM_MESSAGE_DELAY)
            
            logger.debug(f"← send_to_topic() → msg_id={first_message_id}")
            logger.info(f"✅ Resumen de {category} enviado al topic {topic_id} ({len(parts)} mensaje(s), primer msg_id: {first_message_id})")
            
            return first_message_id
        
        except Exception as e:
            # Manejar rate limiting con retry automático
            if e.response.status_code == 429:
                retry_after = e.response.json().get('parameters', {}).get('retry_after', 60)
                logger.warning(f"⚠️  Rate limit alcanzado en topic {topic_id}, esperando {retry_after} segundos...")
                time.sleep(retry_after + 1)
                
                # Reintentar envío completo (llamada recursiva)
                logger.info(f"🔄 Reintentando envío a topic {topic_id}...")
                return self.send_to_topic(topic_id, category, summary, num_articles)
            
            # Si no es 429, propagar el error
            raise TelegramClientError(f"Error enviando al topic {topic_id}: {e}") from e
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout enviando a topic {topic_id} (>30s)")
            raise TelegramClientError(f"Timeout enviando mensaje al topic {topic_id}") 
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red enviando a topic {topic_id}: {e}", exc_info=True)
            raise TelegramClientError(f"Error enviando mensaje: {e}") from e
    
    def send_summary_paragraph(
        self,
        topic_id: int,
        category: str,
        paragraph: str,
        paragraph_num: int,
        total_paragraphs: int
    ) -> int:
        """
        Envía un párrafo individual de un resumen a un topic.
        
        Args:
            topic_id: ID del topic en el supergrupo
            category: Nombre de la categoría
            paragraph: Texto del párrafo
            paragraph_num: Número del párrafo (1-indexed)
            total_paragraphs: Total de párrafos en el resumen
            
        Returns:
            message_id del mensaje enviado
        """
        logger.debug(f"→ send_summary_paragraph(topic={topic_id}, cat={category}, para={paragraph_num}/{total_paragraphs})")
        
        # Formatear como texto plano (sin cabecera, solo el contenido)
        formatted = paragraph
        
        # Si el párrafo es muy largo, dividir
        if len(formatted) > self.MAX_MESSAGE_LENGTH:
            logger.warning(f"⚠️  Párrafo {paragraph_num} muy largo ({len(formatted)} chars), dividiendo")
            parts = self._split_long_message(formatted)
        else:
            parts = [formatted]
        
        try:
            first_message_id = None
            
            for i, part in enumerate(parts, 1):
                url = f"{self.api_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'message_thread_id': topic_id,
                    'text': part
                }
                
                response = HTTPRequestHelper.post(
                    url=url,
                    json_data=payload,
                    timeout=30,
                    context=f"Telegram sendMessage párrafo {paragraph_num} parte {i}/{len(parts)}"
                )
                
                result = response.json()
                
                if not result.get('ok'):
                    logger.error(f"❌ API error en párrafo {paragraph_num}")
                    raise TelegramClientError(f"API error: {result.get('description')}")
                
                message_id = result['result']['message_id']
                
                if first_message_id is None:
                    first_message_id = message_id
                
                # Delay entre partes
                if i < len(parts):
                    time.sleep(settings.TELEGRAM_MESSAGE_DELAY)
            
            logger.debug(f"← send_summary_paragraph() → msg_id={first_message_id}")
            
            return first_message_id
        
        except Exception as e:
            # Manejar rate limiting
            if hasattr(e, 'response') and e.response.status_code == 429:
                retry_after = e.response.json().get('parameters', {}).get('retry_after', 60)
                logger.warning(f"⚠️  Rate limit en párrafo {paragraph_num}, esperando {retry_after}s...")
                time.sleep(retry_after + 1)
                
                logger.info(f"🔄 Reintentando párrafo {paragraph_num}...")
                return self.send_summary_paragraph(topic_id, category, paragraph, paragraph_num, total_paragraphs)
            
            raise TelegramClientError(f"Error enviando párrafo: {e}") from e
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout enviando párrafo {paragraph_num} (>30s)")
            raise TelegramClientError(f"Timeout enviando párrafo al topic {topic_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red enviando párrafo {paragraph_num}: {e}", exc_info=True)
            raise TelegramClientError(f"Error enviando párrafo: {e}") from e
    
    def send_message_with_buttons(
        self,
        text: str,
        buttons: list[list[dict]],
        topic_id: Optional[int] = None
    ) -> int:
        """
        Envía un mensaje con botones inline.
        
        Args:
            text: Texto del mensaje
            buttons: Matriz de botones [[{text, callback_data}, ...], ...]
            topic_id: ID del topic (opcional, para supergrupos)
            
        Returns:
            message_id del mensaje enviado
        """
        logger.debug(f"→ send_message_with_buttons(text_len={len(text)}, buttons={len(buttons)}x?, topic={topic_id})")
        logger.info(f"Enviando mensaje con botones...")
        
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'reply_markup': {
                    'inline_keyboard': buttons
                }
            }
            
            # Enviar al topic si se especifica
            if topic_id is not None:
                payload['message_thread_id'] = topic_id
            
            response = HTTPRequestHelper.post(
                url=url,
                json_data=payload,
                timeout=30,
                context=f"Telegram sendMessage con botones (topic {topic_id})"
            )
            
            result = response.json()
            
            if not result.get('ok'):
                logger.error(f"❌ API error enviando mensaje con botones")
                logger.debug(f"   Texto: {text[:200]}...")
                logger.debug(f"   Botones: {buttons}")
                raise TelegramClientError(f"API error: {result.get('description')}")
            
            message_id = result['result']['message_id']
            
            logger.debug(f"← send_message_with_buttons() → msg_id={message_id}")
            logger.info(f"✅ Mensaje con botones enviado (msg_id: {message_id})")
            
            return message_id
        
        except Exception as e:
            # Manejar rate limiting con retry automático
            if hasattr(e, 'response') and e.response.status_code == 429:
                retry_after = e.response.json().get('parameters', {}).get('retry_after', 60)
                logger.warning(f"⚠️  Rate limit alcanzado, esperando {retry_after} segundos...")
                time.sleep(retry_after + 1)
                
                # Reintentar una vez
                logger.info("🔄 Reintentando envío...")
                response = HTTPRequestHelper.post(
                    url=url,
                    json_data=payload,
                    timeout=30,
                    context="Telegram sendMessage con botones (retry)"
                )
                result = response.json()
                
                if result.get('ok'):
                    message_id = result['result']['message_id']
                    logger.info(f"✅ Mensaje con botones enviado tras retry (msg_id: {message_id})")
                    return message_id
            
            # Si no es 429 o el retry falló, propagar el error
            raise TelegramClientError(f"Error enviando mensaje: {e}") from e
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout enviando mensaje con botones (>30s)")
            raise TelegramClientError("Timeout enviando mensaje con botones")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red enviando mensaje con botones: {e}", exc_info=True)
            raise TelegramClientError(f"Error enviando mensaje: {e}") from e
    
    def send_summary_index(
        self,
        summaries: dict[str, str],
        articles_by_category: dict[str, list[dict]]
    ) -> int:
        """
        Envía un mensaje índice con botones para ver cada categoría.
        
        Args:
            summaries: Dict con categoría → resumen
            articles_by_category: Dict con categoría → lista de artículos
            
        Returns:
            message_id del índice
        """
        logger.info("→ Enviando mensaje índice con botones")
        
        # Calcular estadísticas
        total_articles = sum(len(arts) for arts in articles_by_category.values())
        date_str = datetime.now().strftime("%d/%m/%Y")
        
        # Texto del índice (sin formato markdown especial para simplificar)
        index_text = f"📰 Resumen de Noticias - {date_str}\n\n"
        index_text += f"📊 Total: {total_articles} artículos en {len(summaries)} categorías\n\n"
        index_text += "Selecciona una categoría para ver el resumen:"
        
        # Crear botones inline (2 por fila)
        buttons = []
        sorted_categories = sorted(summaries.keys())
        
        for i in range(0, len(sorted_categories), 2):
            row = []
            
            # Primera categoría de la fila
            cat1 = sorted_categories[i]
            num1 = len(articles_by_category[cat1])
            row.append({
                'text': f"{cat1} ({num1})",
                'callback_data': f"cat:{cat1}"
            })
            
            # Segunda categoría (si existe)
            if i + 1 < len(sorted_categories):
                cat2 = sorted_categories[i + 1]
                num2 = len(articles_by_category[cat2])
                row.append({
                    'text': f"{cat2} ({num2})",
                    'callback_data': f"cat:{cat2}"
                })
            
            buttons.append(row)
        
        keyboard = {'inline_keyboard': buttons}
        
        try:
            # Enviar vía API directa
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': index_text,
                # Sin parse_mode para evitar problemas con caracteres especiales
                'reply_markup': keyboard
            }
            
            logger.debug(f"Payload índice: {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}")
            
            response = HTTPRequestHelper.post(
                url=url,
                json_data=payload,
                timeout=30,
                context="Telegram sendMessage índice"
            )
            
            result = response.json()
            
            if not result.get('ok'):
                logger.error(f"❌ API error enviando índice")
                raise TelegramClientError(f"API error: {result.get('description')}")
            
            message_id = result['result']['message_id']
            
            logger.info(f"✅ Índice enviado (id: {message_id}, {len(summaries)} categorías)")
            
            return message_id
            
        except Exception as e:
            logger.error(f"❌ Error enviando índice: {e}")
            raise TelegramClientError(f"Error enviando índice: {e}") from e
    
    def send_all_summaries(
        self,
        summaries: dict[str, str],
        articles_by_category: dict[str, list[dict]],
        send_index: bool = True
    ) -> dict[str, list[int]]:
        """
        Envía todos los resúmenes a Telegram.
        
        Args:
            summaries: Dict con categoría → resumen
            articles_by_category: Dict con categoría → lista de artículos
            send_index: Si enviar mensaje índice con botones
            
        Returns:
            Dict con categoría → lista de message_ids
        """
        logger.info(f"Enviando {len(summaries)} resúmenes a Telegram")
        logger.debug(f"→ send_all_summaries(categories={list(summaries.keys())})")
        
        message_ids = {}
        
        # Enviar índice primero (si se solicita)
        if send_index:
            index_id = self.send_summary_index(summaries, articles_by_category)
            message_ids['__index__'] = [index_id]
        
        # Enviar cada resumen
        for category_name in sorted(summaries.keys()):
            summary = summaries[category_name]
            articles = articles_by_category[category_name]
            
            try:
                ids = self.send_summary(category_name, summary, len(articles))
                message_ids[category_name] = ids
                
            except TelegramClientError as e:
                logger.error(f"❌ Error enviando {category_name}: {e}")
                message_ids[category_name] = []
        
        total_messages = sum(len(ids) for ids in message_ids.values())
        
        logger.debug(f"← send_all_summaries() → {len(message_ids)} categorías")
        logger.info(f"✅ Envío completado: {total_messages} mensajes en {len(summaries)} categorías")
        
        return message_ids
    
    def register_article_urls(self, articles: list[dict]):
        """
        Registra el mapeo ID → URL para consultas posteriores.
        
        Args:
            articles: Lista de artículos con 'id' y 'link'
        """
        for article in articles:
            article_id = article.get('id')
            url = article.get('link')
            if article_id and url:
                self.article_urls[article_id] = url
        
        logger.debug(f"Registrados {len(self.article_urls)} URLs de artículos")
    
    def get_article_url(self, article_id: int) -> Optional[str]:
        """
        Obtiene la URL de un artículo por su ID.
        
        Args:
            article_id: ID del artículo
            
        Returns:
            URL del artículo o None
        """
        return self.article_urls.get(article_id)
