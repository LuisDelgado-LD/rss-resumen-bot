"""
Bot interactivo de Telegram.
Escucha updates (clicks, comandos, reacciones) y responde usando el TelegramClient.
Soporta modo chat (1:1) y supergroup (con topics).
"""
import logging
import requests
import time
from typing import Optional

from src.clients.telegram_client import TelegramClient
from src.clients.ttrss_client import TTRSSClient
from src.clients.wallabag_client import WallabagClient
from src.db.state_manager import StateManager
from src.config import settings


logger = logging.getLogger(__name__)


class TelegramBot:
    """Bot interactivo de Telegram con handlers para chat y supergroup."""
    
    def __init__(
        self,
        telegram_client: TelegramClient,
        ttrss_client: TTRSSClient,
        state_manager: StateManager,
        wallabag_client: Optional[WallabagClient] = None,
        summaries: Optional[dict[str, str]] = None,
        articles_by_category: Optional[dict[str, list[dict]]] = None
    ):
        """
        Inicializa el bot.
        
        Args:
            telegram_client: Cliente de Telegram para enviar mensajes
            ttrss_client: Cliente de TT-RSS para marcar artículos
            state_manager: Gestor de estado para tracking
            summaries: Dict con categoría → resumen (modo chat)
            articles_by_category: Dict con categoría → artículos (modo chat)
        """
        logger.debug(f"→ TelegramBot.__init__(mode={settings.TELEGRAM_MODE})")
        
        self.client = telegram_client
        self.ttrss_client = ttrss_client
        self.state_manager = state_manager
        self.wallabag_client = wallabag_client
        self.summaries = summaries or {}
        self.articles_by_category = articles_by_category or {}
        
        # Estado
        self.running = True
        self.last_update_id = 0
        self.mode = settings.TELEGRAM_MODE

        # Cargar URLs persistidas del último digest para que /url funcione
        # sin necesidad de haber corrido el digest en la misma ejecución
        if self.state_manager is not None:
            persisted_urls = self.state_manager.load_article_urls()
            if persisted_urls:
                self.client.article_urls.update(persisted_urls)
                logger.info(
                    f"✅ URLs de artículos cargadas del estado: {len(persisted_urls)} entradas"
                )
            else:
                logger.warning(
                    "⚠️  No hay URLs de artículos persistidas. "
                    "Ejecuta el digest al menos una vez para poblar article_urls.json"
                )

        logger.info(f"Bot interactivo inicializado en modo: {self.mode}")
        logger.debug(f"→ Categorías disponibles: {list(self.summaries.keys())}")
        logger.debug(f"← TelegramBot.__init__() completado")
    
    def handle_callback_query(self, callback_query: dict):
        """
        Maneja clicks en botones inline (chat y supergroup).
        
        Args:
            callback_query: Datos del callback de Telegram
        """
        callback_id = callback_query['id']
        data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        user = callback_query['from']['first_name']
        
        logger.debug(f"→ handle_callback_query(data={data}, user={user}, msg={message_id})")
        logger.info(f"→ Callback recibido: {data} de {user}")
        
        # Modo CHAT: Botones de navegación y resumen
        if data.startswith('cat:'):
            self._handle_chat_callback(callback_id, data, chat_id, message_id, user)
        
        # Modo SUPERGROUP: Botones de marcado por categoría
        elif data.startswith('category:mark:'):
            category = data.replace('category:mark:', '')
            self._handle_mark_category(callback_id, category, user)
        
        elif data.startswith('category:exclude:'):
            category = data.replace('category:exclude:', '')
            self._handle_exclude_category(callback_id, category, user)
        
        # Modo SUPERGROUP: Botones de marcado masivo (batch)
        elif data.startswith('batch:'):
            batch_action = data.replace('batch:', '')
            if batch_action == 'mark_all':
                self._handle_mark_all(callback_id, user)
            elif batch_action == 'mark_pending':
                self._handle_mark_unreacted(callback_id, user)
            else:
                logger.warning(f"⚠️  Acción batch desconocida: {batch_action}")
                self._answer_callback_query(callback_id, "⚠️ Acción no reconocida")
        
        # LEGACY: Compatibilidad con callbacks antiguos
        elif data.startswith('mark_topic_'):
            self._handle_mark_topic(callback_id, data, user)
        
        elif data == 'mark_all':
            self._handle_mark_all(callback_id, user)
        
        elif data == 'mark_unreacted':
            self._handle_mark_unreacted(callback_id, user)
        
        else:
            logger.warning(f"⚠️  Callback desconocido: {data}")
            self._answer_callback_query(callback_id, "⚠️ Acción no reconocida")
        
        logger.debug(f"← handle_callback_query() completado")
    
    def _handle_chat_callback(self, callback_id: str, data: str, chat_id: int, message_id: int, user: str):
        """Handler para callbacks de modo chat."""
        logger.debug(f"→ _handle_chat_callback(data={data}, chat={chat_id})")
        
        category_name = data[4:]  # Quitar "cat:"
        
        if category_name in self.summaries:
            summary = self.summaries[category_name]
            num_articles = len(self.articles_by_category[category_name])
            
            logger.info(f"Enviando resumen de {category_name} ({num_articles} artículos)")
            
            # Enviar resumen
            try:
                self.client.send_summary(category_name, summary, num_articles)
                
                # Responder al callback (para quitar el "loading" del botón)
                self._answer_callback_query(callback_id, f"✅ Resumen de {category_name} enviado")
                
                logger.info(f"✅ Resumen de {category_name} enviado por callback")
                
                # Reenviar el índice para que pueda elegir otra categoría
                logger.info("Reenviando índice...")
                self.client.send_summary_index(self.summaries, self.articles_by_category)
                logger.info("✅ Índice reenviado")
                
            except Exception as e:
                logger.error(f"❌ Error enviando resumen: {e}", exc_info=True)
                self._answer_callback_query(callback_id, "❌ Error enviando resumen")
        else:
            logger.warning(f"⚠️  Categoría no encontrada: {category_name}")
            self._answer_callback_query(callback_id, "⚠️ Categoría no encontrada")
        
        logger.debug(f"← _handle_chat_callback() completado")
    
    def _handle_mark_category(self, callback_id: str, category: str, user: str):
        """
        Marca como leídos los artículos del flujo asociado al botón presionado.

        Usa el message_id del mensaje con botones para obtener exactamente
        los artículos enviados en ese flujo, evitando marcar artículos de
        otros días o ejecuciones anteriores.

        Args:
            callback_id: ID del callback — contiene el message_id del botón
            category: Nombre de la categoría
            user: Nombre del usuario
        """
        logger.debug(f"→ _handle_mark_category(category={category}, user={user})")
        logger.info(f"Marcando categoría: {category}")

        try:
            # Obtener el message_id del mensaje con botones desde el callback
            # El callback_query trae el mensaje que contiene el botón presionado
            # — se resuelve en handle_callback_query y se pasa como contexto
            message_map = self.state_manager.load_message_map()

            # Buscar en el mapa los IDs asociados a esta categoría
            # Dado que el dispatcher ahora guarda el message_id del botón
            # con todos los IDs del flujo, basta con buscar por categoría
            # y tomar la entrada más reciente (la del botón)
            candidates = {
                msg_id: data
                for msg_id, data in message_map.items()
                if data.get('category') == category
            }

            if not candidates:
                logger.warning(f"⚠️  No se encontraron artículos para categoría: {category}")
                self._answer_callback_query(callback_id, f"⚠️ No hay artículos en {category}")
                logger.debug(f"← _handle_mark_category() → sin artículos")
                return

            # Tomar la entrada más reciente (el mensaje con botones del último flujo)
            latest_msg_id = max(
                candidates,
                key=lambda k: candidates[k].get('timestamp', '')
            )
            article_ids = candidates[latest_msg_id].get('article_ids', [])
            unique_ids = list(dict.fromkeys(article_ids))  # deduplicar preservando orden

            logger.debug(
                f"Usando msg_id={latest_msg_id} ({candidates[latest_msg_id].get('timestamp')}) "
                f"→ {len(unique_ids)} artículos"
            )

            if not unique_ids:
                self._answer_callback_query(callback_id, f"⚠️ No hay artículos en {category}")
                logger.debug(f"← _handle_mark_category() → sin artículos válidos")
                return

            # Marcar en StateManager y TT-RSS
            self.state_manager.mark_read(unique_ids)
            start_time = time.time()
            self.ttrss_client.mark_articles_as_read(unique_ids)
            elapsed = time.time() - start_time

            logger.debug(f"← _handle_mark_category() → {len(unique_ids)} marcados en {elapsed:.2f}s")
            logger.info(f"✅ Categoría {category} marcada: {len(unique_ids)} artículos ({elapsed:.2f}s)")

            self._answer_callback_query(callback_id, f"✅ {len(unique_ids)} artículos de {category} marcados")

        except Exception as e:
            logger.error(f"❌ Error marcando categoría {category}: {e}", exc_info=True)
            self._answer_callback_query(callback_id, f"❌ Error marcando {category}")
            logger.debug(f"← _handle_mark_category() → error")
    
    def _handle_exclude_category(self, callback_id: str, category: str, user: str):
        """
        Excluye una categoría del marcado masivo.
        
        Args:
            callback_id: ID del callback
            category: Nombre de la categoría
            user: Nombre del usuario
        """
        logger.debug(f"→ _handle_exclude_category(category={category}, user={user})")
        logger.info(f"Excluyendo categoría del marcado masivo: {category}")
        
        # TODO: Implementar lógica de exclusión en StateManager
        # Por ahora solo respondemos
        logger.warning(f"⚠️  Funcionalidad de exclusión no implementada aún")
        self._answer_callback_query(callback_id, f"⚠️ Función no disponible aún")
        
        logger.debug(f"← _handle_exclude_category() → no implementado")
    
    def _handle_mark_topic(self, callback_id: str, data: str, user: str):
        """
        Marca todos los artículos de un topic como leídos.
        
        Args:
            callback_id: ID del callback
            data: Callback data (formato: mark_topic_{category})
            user: Nombre del usuario
        """
        category = data.replace('mark_topic_', '')
        
        logger.debug(f"→ _handle_mark_topic(category={category}, user={user})")
        logger.info(f"Marcando topic completo: {category}")
        
        try:
            # Obtener todos los mensajes de esta categoría desde StateManager
            message_map = self.state_manager.load_message_map()
            article_ids = []
            for msg_id, msg_data in message_map.items():
                if msg_data.get('category') == category:
                    article_ids.extend(msg_data.get('article_ids', []))
            
            if not article_ids:
                logger.warning(f"⚠️  No se encontraron artículos para categoría: {category}")
                self._answer_callback_query(callback_id, f"⚠️ No hay artículos en {category}")
                return
            
            logger.debug(f"Artículos encontrados: {len(article_ids)}")
            logger.debug(f"Primeros 10 IDs: {article_ids[:10]}")
            
            # Marcar en TT-RSS
            start_time = time.time()
            self.ttrss_client.mark_articles_as_read(article_ids)
            elapsed = time.time() - start_time
            
            logger.debug(f"← _handle_mark_topic() → {len(article_ids)} marcados en {elapsed:.2f}s")
            logger.info(f"✅ Topic {category} marcado: {len(article_ids)} artículos ({elapsed:.2f}s)")
            
            self._answer_callback_query(callback_id, f"✅ {len(article_ids)} artículos de {category} marcados")
            
        except Exception as e:
            logger.error(f"❌ Error marcando topic {category}: {e}", exc_info=True)
            self._answer_callback_query(callback_id, f"❌ Error marcando {category}")
    
    def _handle_mark_all(self, callback_id: str, user: str):
        """
        Marca todos los artículos como leídos.
        
        Args:
            callback_id: ID del callback
            user: Nombre del usuario
        """
        logger.debug(f"→ _handle_mark_all(user={user})")
        logger.info("Marcando TODOS los artículos como leídos")
        
        try:
            # Obtener IDs del mensaje final del digest (__digest__)
            message_map = self.state_manager.load_message_map()
            digest_entry = next(
                (data for data in message_map.values()
                 if data.get('category') == '__digest__'),
                None
            )
            if digest_entry is None:
                logger.warning("⚠️  No se encontró entrada __digest__ en message_map, usando mapa completo")
                all_article_ids = []
                for msg_data in message_map.values():
                    all_article_ids.extend(msg_data.get('article_ids', []))
            else:
                all_article_ids = digest_entry.get('article_ids', [])
                logger.debug(f"Usando entrada __digest__ → {len(all_article_ids)} artículos")

            unique_ids = list(dict.fromkeys(all_article_ids))  # deduplicar preservando orden

            if not unique_ids:
                logger.warning("⚠️  No hay artículos para marcar")
                self._answer_callback_query(callback_id, "⚠️ No hay artículos pendientes")
                return

            logger.debug(f"Artículos únicos encontrados: {len(unique_ids)}")
            logger.debug(f"Primeros 10 IDs: {unique_ids[:10]}")

            # Marcar en TT-RSS
            start_time = time.time()
            self.ttrss_client.mark_articles_as_read(unique_ids)
            elapsed = time.time() - start_time

            logger.debug(f"← _handle_mark_all() → {len(unique_ids)} marcados en {elapsed:.2f}s")
            logger.info(f"✅ Marcado masivo: {len(unique_ids)} artículos ({elapsed:.2f}s)")

            self._answer_callback_query(callback_id, f"✅ {len(unique_ids)} artículos marcados")

        except Exception as e:
            logger.error(f"❌ Error en marcado masivo: {e}", exc_info=True)
            self._answer_callback_query(callback_id, "❌ Error marcando artículos")
    
    def _handle_mark_unreacted(self, callback_id: str, user: str):
        """
        Marca como leídos solo los artículos SIN reacciones.
        
        Args:
            callback_id: ID del callback
            user: Nombre del usuario
        """
        logger.debug(f"→ _handle_mark_unreacted(user={user})")
        logger.info("Marcando artículos no reaccionados como leídos")
        
        try:
            # Obtener IDs del mensaje final del digest (__digest__)
            message_map = self.state_manager.load_message_map()
            digest_entry = next(
                (data for data in message_map.values()
                 if data.get('category') == '__digest__'),
                None
            )
            if digest_entry is None:
                logger.warning("⚠️  No se encontró entrada __digest__ en message_map, usando mapa completo")
                all_article_ids = []
                for msg_data in message_map.values():
                    all_article_ids.extend(msg_data.get('article_ids', []))
            else:
                all_article_ids = digest_entry.get('article_ids', [])
                logger.debug(f"Usando entrada __digest__ → {len(all_article_ids)} artículos")

            unique_ids = list(dict.fromkeys(all_article_ids))  # deduplicar preservando orden

            # Filtrar: obtener solo los que NO están marcados (no tienen reacción)
            unreacted = [
                aid for aid in unique_ids
                if not self.state_manager.is_marked(aid)
            ]

            if not unreacted:
                logger.warning("⚠️  No hay artículos sin reaccionar")
                self._answer_callback_query(callback_id, "⚠️ Todos los artículos tienen reacción")
                return

            logger.debug(f"Artículos sin reaccionar: {len(unreacted)}/{len(unique_ids)}")
            logger.debug(f"Primeros 10 IDs: {unreacted[:10]}")

            # Marcar en TT-RSS
            start_time = time.time()
            self.ttrss_client.mark_articles_as_read(unreacted)
            elapsed = time.time() - start_time

            logger.debug(f"← _handle_mark_unreacted() → {len(unreacted)} marcados en {elapsed:.2f}s")
            logger.info(f"✅ No reaccionados marcados: {len(unreacted)}/{len(unique_ids)} artículos ({elapsed:.2f}s)")

            self._answer_callback_query(callback_id, f"✅ {len(unreacted)} artículos sin reacción marcados")

        except Exception as e:
            logger.error(f"❌ Error marcando no reaccionados: {e}", exc_info=True)
            self._answer_callback_query(callback_id, "❌ Error marcando artículos")
    
    def handle_command(self, message: dict):
        """
        Maneja comandos del usuario.
        
        Args:
            message: Mensaje de Telegram
        """
        text = message['text']
        chat_id = message['chat']['id']
        user = message['from'].get('first_name', 'Usuario')
        topic_id = message.get('message_thread_id') if self.mode == "supergroup" else None

        logger.debug(f"→ handle_command(text={text}, user={user}, chat={chat_id}, topic_id={topic_id})")
        logger.info(f"→ Comando recibido: {text} de {user}")

        # /url ID
        if text.startswith('/url'):
            parts = text.split()

            # Determinar el ID: explícito en el comando o desde reply
            article_id = None
            if len(parts) == 2:
                try:
                    article_id = int(parts[1])
                except ValueError:
                    response = "❌ ID inválido. Uso: /url 123456"
                    self._send_message(chat_id, response, topic_id=topic_id)
                    logger.debug(f"← handle_command() → ID inválido")
            elif len(parts) == 1:
                # Sin ID explícito → intentar extraer del reply
                ids, reply_warning = self._extract_ids_from_reply(message)
                if reply_warning:
                    self._send_message(chat_id, reply_warning, topic_id=topic_id)
                    logger.debug("← handle_command() → /url TextQuote inválido")
                elif ids:
                    article_id = ids[0]
                    logger.info(f"ID extraído desde reply para /url: {article_id}")
                else:
                    response = (
                        "❌ Indicá un ID o citá el texto de un artículo.\n"
                        "Ejemplo: /url 123456"
                    )
                    self._send_message(chat_id, response, topic_id=topic_id)
                    logger.debug("← handle_command() → /url sin ID ni reply")
            else:
                response = "❌ Uso: /url [ID]\nEjemplo: /url 133201"
                self._send_message(chat_id, response, topic_id=topic_id)
                logger.debug(f"← handle_command() → formato incorrecto")

            if article_id is not None:
                article = self._resolve_article(article_id)
                if article:
                    response = f"🔗 Artículo [{article_id}]:\n{article['link']}"
                    logger.debug(f"← handle_command() → URL encontrada")
                    logger.info(f"✅ URL encontrada para artículo {article_id}")
                else:
                    response = f"⚠️ No se encontró el artículo {article_id}"
                    logger.warning(f"⚠️  Artículo {article_id} no encontrado")
                self._send_message(chat_id, response, topic_id=topic_id)
        
        # /guardar ID1 [ID2 ID3 ...]
        elif text.startswith('/guardar'):
            self._handle_guardar_command(text, chat_id, user, topic_id=topic_id, message=message)
        
        # /ayuda
        elif text.startswith('/ayuda') or text.startswith('/help'):
            wallabag_status = "✅ Configurado" if (self.wallabag_client and self.wallabag_client.is_configured()) else "⚠️ No configurado"
            
            if self.mode == "supergroup":
                response = (
                    "🤖 Comandos disponibles:\n\n"
                    "/url [ID] - Obtener URL de un artículo\n"
                    f"/guardar [ID...] - Guardar en Wallabag ({wallabag_status})\n"
                    "/ayuda - Mostrar esta ayuda\n\n"
                    "💡 Tips de Supergroup:\n"
                    "- Los números [ID] indican artículos específicos\n"
                    "- Reacciona con ❤️ 👍 🔥 a mensajes con [ID] para marcarlos\n"
                    "- Usa botones de categoría para marcar grupos completos\n"
                    "- Párrafos sin [ID] son introductorios (no se marcan individualmente)\n\n"
                    "📝 Ejemplo guardado: /guardar 123456 123457"
                )
            else:
                response = (
                    "🤖 Comandos disponibles:\n\n"
                    "/url [ID] - Obtener URL de un artículo\n"
                    f"/guardar [ID...] - Guardar en Wallabag ({wallabag_status})\n"
                    "/ayuda - Mostrar esta ayuda\n\n"
                    "💡 Tips:\n"
                    "- Haz click en los botones para ver resúmenes\n"
                    "- Los números [ID] en los resúmenes son IDs de artículos\n\n"
                    "📝 Ejemplo guardado: /guardar 123456"
                )
            self._send_message(chat_id, response)
            logger.debug(f"← handle_command() → ayuda enviada")
            logger.info("✅ Ayuda enviada")
        
        # Comando desconocido
        else:
            logger.debug(f"← handle_command() → comando desconocido: {text}")
    
    def _resolve_article(self, article_id: int):
        """
        Resuelve un artículo por ID con fallback en tres pasos:
        1. Caché en memoria (article_urls del telegram_client)
        2. article_urls.json en disco
        3. API de TT-RSS directamente

        Returns:
            Dict con al menos {'id', 'link', 'title'}, o None si no se encuentra
        """
        logger.debug(f"→ _resolve_article(id={article_id})")

        # Paso 1: caché en memoria
        if hasattr(self, 'client'):
            url = self.client.get_article_url(article_id)
            if url:
                logger.debug(f"← _resolve_article() → caché memoria")
                return {'id': article_id, 'link': url, 'title': ''}

        # Paso 2: disco
        if self.state_manager:
            meta = self.state_manager.load_article_metadata()
            entry = meta.get(article_id) or meta.get(str(article_id))
            if entry:
                logger.info(f"✅ Artículo {article_id} encontrado en disco")
                return {'id': article_id, 'link': entry['link'], 'title': entry.get('title', '')}

        # Paso 3: API de TT-RSS
        logger.info(f"Artículo {article_id} no en caché, consultando TT-RSS API...")
        article = self.ttrss_client.get_article_by_id(article_id)
        if article:
            logger.info(f"✅ Artículo {article_id} obtenido desde TT-RSS API")
            return article

        logger.warning(f"⚠️  Artículo {article_id} no encontrado en ninguna fuente")
        logger.debug(f"← _resolve_article() → None")
        return None

    def _extract_ids_from_reply(self, message: dict) -> tuple[list[int], str | None]:
        """
        Extrae IDs de artículo desde un mensaje citado (reply/quote).

        Estrategia:
        1. TextQuote (texto seleccionado manualmente por el usuario):
           - Se espera que contenga SOLO dígitos (el ID sin corchetes)
           - Si contiene caracteres no numéricos → se considera inválido,
             se avisa al usuario y se sugieren los IDs del fallback
        2. Fallback — texto completo del mensaje citado:
           - Busca IDs en formato [123456] con corchetes

        Args:
            message: Mensaje de Telegram que contiene reply_to_message

        Returns:
            Tupla (ids, warning):
            - ids: Lista de IDs encontrados (puede ser vacía)
            - warning: Mensaje de advertencia para mostrar al usuario, o None
        """
        logger.debug("→ _extract_ids_from_reply()")

        reply_to = message.get("reply_to_message")
        if not reply_to:
            logger.debug("← _extract_ids_from_reply() → ([], None) sin reply")
            return [], None

        def find_ids_bracketed(text: str) -> list[int]:
            """Busca IDs en formato [123456] con corchetes."""
            return [int(m) for m in re.findall(r'\[(\d+)\]', text)]

        # Paso 1: TextQuote — el usuario seleccionó texto específico
        quote = message.get("quote")
        if quote:
            quote_text = quote.get("text", "").strip()
            is_manual = quote.get("is_manual", False)

            logger.debug(
                f"TextQuote detectado (manual={is_manual}): {repr(quote_text[:100])}"
            )

            # Verificar si el quote contiene exactamente un ID (solo dígitos)
            if quote_text.isdigit():
                ids = [int(quote_text)]
                logger.debug(f"← _extract_ids_from_reply() → {ids} (TextQuote numérico)")
                return ids, None

            # Contiene caracteres no numéricos → inválido, calcular sugerencias
            fallback_ids = find_ids_bracketed(reply_to.get("text", ""))
            warning = (
                f"⚠️ El texto seleccionado contiene caracteres inesperados: "
                f"{repr(quote_text[:80])}\n"
            )
            if fallback_ids:
                warning += (
                    f"💡 IDs encontrados en el mensaje completo: "
                    f"{', '.join(str(i) for i in fallback_ids)}\n"
                    f"Podés usar: /guardar {' '.join(str(i) for i in fallback_ids)}"
                )
            else:
                warning += "No se encontraron IDs en el mensaje citado."

            logger.warning(
                f"⚠️  TextQuote con caracteres no numéricos: {repr(quote_text[:80])} "
                f"— sugeridos: {fallback_ids}"
            )
            return [], warning

        # Paso 2: fallback — sin TextQuote, usar texto completo con corchetes
        full_text = reply_to.get("text", "")
        ids = find_ids_bracketed(full_text)

        if ids:
            logger.debug(f"← _extract_ids_from_reply() → {ids} (mensaje completo)")
        else:
            logger.debug("← _extract_ids_from_reply() → [] (sin IDs en ninguna fuente)")

        return ids, None

    def _handle_guardar_command(self, text: str, chat_id: int, user: str, topic_id: int = None, message: dict = None):
        """
        Maneja el comando /guardar [ID1 ID2 ...] para guardar artículos en Wallabag.

        Args:
            text: Texto del comando
            chat_id: ID del chat
            user: Nombre del usuario
            topic_id: ID del topic (supergroup) donde responder
            message: Mensaje completo de Telegram (necesario para extraer IDs de reply)
        """
        logger.debug(f"→ _handle_guardar_command(text={text}, user={user})")
        
        # Verificar si Wallabag está configurado
        if not self.wallabag_client or not self.wallabag_client.is_configured():
            response = (
                "⚠️ Wallabag no está configurado.\n\n"
                "Configura las variables WALLABAG_* en tu archivo .env"
            )
            self._send_message(chat_id, response)
            logger.warning("Comando /guardar usado pero Wallabag no configurado")
            logger.debug("← _handle_guardar_command()")
            return
        
        # Extraer IDs: primero del comando, si no hay usar reply
        parts = text.split()
        article_ids = []

        if len(parts) >= 2:
            # IDs explícitos en el comando: /guardar 123456 123457
            for part in parts[1:]:
                try:
                    article_ids.append(int(part))
                except ValueError:
                    logger.warning(f"⚠️  ID inválido ignorado en comando: {part!r}")
            logger.debug(f"IDs desde comando: {article_ids}")
        else:
            # Sin IDs explícitos → intentar extraer del mensaje citado
            article_ids, reply_warning = self._extract_ids_from_reply(message)
            if reply_warning:
                # TextQuote inválido: mostrar advertencia con sugerencias y salir
                self._send_message(chat_id, reply_warning, topic_id=topic_id)
                logger.debug("← _handle_guardar_command() → TextQuote inválido")
                return
            if article_ids:
                logger.info(f"IDs extraídos desde reply: {article_ids}")
        
        if not article_ids:
            response = (
                "❌ No se encontraron IDs.\n"
                "Opciones:\n"
                "• Escribe los IDs: /guardar 123456 123457\n"
                "• Cita el texto de un artículo y responde /guardar"
            )
            self._send_message(chat_id, response, topic_id=topic_id)
            logger.debug("← _handle_guardar_command() → sin IDs (ni en comando ni en reply)")
            return
        
        logger.info(f"Guardando {len(article_ids)} artículos en Wallabag: {article_ids}")
        
        # Obtener artículos de TT-RSS
        saved_count = 0
        duplicate_count = 0
        failed_count = 0
        failed_ids = []
        
        for article_id in article_ids:
            try:
                # Obtener datos del artículo (caché → disco → API)
                article = self._resolve_article(article_id)

                if not article:
                    logger.warning(f"Artículo {article_id} no encontrado en ninguna fuente")
                    failed_count += 1
                    failed_ids.append(article_id)
                    continue
                
                url = article.get('link')
                title = article.get('title', 'Sin título')
                
                # Determinar categoría para tag
                category_tag = None
                for cat_name, articles in self.articles_by_category.items():
                    if any(a['id'] == article_id for a in articles):
                        category_tag = cat_name
                        break
                
                # Tags: categoría + default (si existe)
                tags = []
                if category_tag:
                    tags.append(category_tag)
                
                logger.debug(f"Guardando artículo {article_id}: {title[:50]}...")
                logger.debug(f"Tags: {tags}")
                
                # Guardar en Wallabag
                result = self.wallabag_client.add_entry(
                    url=url,
                    title=title,
                    tags=tags,
                    archived=False  # No archivar, mantener como no leído
                )
                
                if result:
                    # Verificar si es duplicado
                    is_duplicate = result.get('_is_duplicate', False)
                    if is_duplicate:
                        duplicate_count += 1
                    else:
                        saved_count += 1

                    logger.info(f"✅ Artículo {article_id} procesado")

                    # Notificar con URL de Wallabag en el topic
                    entry_id = result.get('id')
                    wallabag_base = getattr(self.wallabag_client, 'base_url', '').rstrip('/')
                    if entry_id and wallabag_base:
                        status_icon = "ℹ️ Ya existía" if is_duplicate else "✅ Guardado"
                        notify_msg = (
                            f"{status_icon} en Wallabag: {title}\n"
                            f"🔗 {wallabag_base}/view/{entry_id}"
                        )
                        self._send_message(chat_id, notify_msg, topic_id=topic_id)

                    # Marcar como leído en TT-RSS
                    self.ttrss_client.mark_articles_as_read([article_id])
                    self.state_manager.mark_read([article_id])
                    logger.info(f"✅ Artículo {article_id} marcado como leído en TT-RSS")
                else:
                    failed_count += 1
                    failed_ids.append(article_id)
                    logger.error(f"❌ Error guardando artículo {article_id}")
                
            except Exception as e:
                logger.error(f"Error procesando artículo {article_id}: {e}")
                failed_count += 1
                failed_ids.append(article_id)
        
        # Respuesta al usuario
        total_ok = saved_count + duplicate_count
        
        if total_ok > 0 and failed_count == 0:
            parts = []
            if saved_count > 0:
                parts.append(f"✅ {saved_count} nuevo(s)")
            if duplicate_count > 0:
                parts.append(f"ℹ️ {duplicate_count} ya existía(n)")
            response = f"{', '.join(parts)} - Todos marcados como leídos en TT-RSS"
        elif total_ok > 0 and failed_count > 0:
            parts = []
            if saved_count > 0:
                parts.append(f"✅ {saved_count} nuevo(s)")
            if duplicate_count > 0:
                parts.append(f"ℹ️ {duplicate_count} duplicado(s)")
            response = (
                f"{', '.join(parts)}, ❌ {failed_count} fallido(s)\n"
                f"IDs fallidos: {', '.join(map(str, failed_ids))}"
            )
        else:
            response = f"❌ No se pudo guardar ningún artículo\nIDs: {', '.join(map(str, failed_ids))}"
        
        self._send_message(chat_id, response, topic_id=topic_id)
        logger.info(f"✅ Comando /guardar completado: {saved_count} nuevos, {duplicate_count} duplicados, {failed_count} fallos")
        logger.debug("← _handle_guardar_command()")
    
    def handle_message_reaction(self, reaction_update: dict):
        """
        Maneja reacciones (emojis) en mensajes de supergroup.
        Cualquier emoji marca el artículo como leído.
        
        Args:
            reaction_update: Update de tipo message_reaction
        """
        message_id = reaction_update['message_id']
        chat_id = reaction_update['chat']['id']
        user_id = reaction_update['user']['id']
        user_name = reaction_update['user'].get('first_name', 'Usuario')
        
        # new_reaction contiene la lista de reacciones actuales
        new_reactions = reaction_update.get('new_reaction', [])
        old_reactions = reaction_update.get('old_reaction', [])
        
        logger.debug(f"→ handle_message_reaction(msg={message_id}, user={user_name}, chat={chat_id})")
        logger.debug(f"→ Reacciones: old={len(old_reactions)}, new={len(new_reactions)}")
        
        # Si agregó reacciones (lista nueva > lista vieja)
        if len(new_reactions) > len(old_reactions):
            # Extraer emojis para log
            emojis = []
            for reaction in new_reactions:
                if 'emoji' in reaction:
                    emojis.append(reaction['emoji'])
                elif 'custom_emoji' in reaction:
                    emojis.append(f"custom:{reaction['custom_emoji']}")
            
            logger.info(f"→ Reacción agregada: {emojis} en mensaje {message_id} por {user_name}")
            
            # Buscar artículos asociados al mensaje
            article_ids = self.state_manager.get_articles_by_message(message_id)
            
            if not article_ids:
                logger.warning(f"⚠️  Mensaje {message_id} no tiene artículos asociados (probablemente es un párrafo introductorio)")
                logger.info(f"💡 Usa los botones de categoría para marcar artículos completos")
                logger.debug(f"← handle_message_reaction() → sin artículos")
                return
            
            logger.debug(f"Artículos en mensaje: {len(article_ids)}")
            logger.debug(f"IDs: {article_ids}")
            
            try:
                # Guardar en StateManager (para tracking)
                self.state_manager.mark_read(article_ids)
                
                # Marcar en TT-RSS
                start_time = time.time()
                self.ttrss_client.mark_articles_as_read(article_ids)
                elapsed = time.time() - start_time
                
                logger.debug(f"← handle_message_reaction() → {len(article_ids)} marcados en {elapsed:.2f}s")
                logger.info(f"✅ Reacción procesada: {len(article_ids)} artículos marcados ({elapsed:.2f}s)")
                
            except Exception as e:
                logger.error(f"❌ Error marcando artículos por reacción: {e}", exc_info=True)
                logger.debug(f"← handle_message_reaction() → error")
        
        # Si quitó todas las reacciones
        elif len(new_reactions) == 0 and len(old_reactions) > 0:
            logger.info(f"→ Reacciones removidas en mensaje {message_id} por {user_name}")
            logger.debug(f"← handle_message_reaction() → reacciones removidas (sin acción)")
        
        else:
            logger.debug(f"← handle_message_reaction() → sin cambios significativos")
    
    def _answer_callback_query(self, callback_id: str, text: str):
        """Responde a un callback query (quita el loading del botón)."""
        logger.debug(f"→ _answer_callback_query(text={text[:50]}...)")
        
        url = f"{self.client.api_url}/answerCallbackQuery"
        payload = {
            'callback_query_id': callback_id,
            'text': text
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if not response.ok:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Telegram API error en answerCallbackQuery: {error_data}")
                response.raise_for_status()
            
            logger.debug(f"← _answer_callback_query() → OK")
            
        except Exception as e:
            logger.error(f"❌ Error respondiendo callback: {e}", exc_info=True)
    
    def _send_message(self, chat_id: int, text: str, parse_mode: str = None):
        """Envía un mensaje de respuesta."""
        logger.debug(f"→ _send_message(chat={chat_id}, text_len={len(text)}, mode={parse_mode})")
        
        url = f"{self.client.api_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        
        if parse_mode:
            payload['parse_mode'] = parse_mode
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if not response.ok:
                error_data = response.json() if response.text else {}
                error_description = error_data.get('description', 'Sin descripción')
                
                logger.error(f"❌ Telegram API error en sendMessage: {error_description}")
                logger.debug(f"→ Mensaje: {text[:200]}...")
                response.raise_for_status()
            
            logger.debug(f"← _send_message() → enviado")
            
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje: {e}", exc_info=True)
    def _send_message(self, chat_id: int, text: str, parse_mode: str = None, topic_id: int = None):
        """Envía un mensaje de respuesta. Permite enviar a un topic específico en supergrupo."""
        logger.debug(f"→ _send_message(chat={chat_id}, text_len={len(text)}, mode={parse_mode}, topic_id={topic_id})")
        url = f"{self.client.api_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if topic_id is not None:
            payload['message_thread_id'] = topic_id
        try:
            response = requests.post(url, json=payload, timeout=10)
            if not response.ok:
                error_data = response.json() if response.text else {}
                error_description = error_data.get('description', 'Sin descripción')
                logger.error(f"❌ Telegram API error en sendMessage: {error_description}")
                logger.debug(f"→ Mensaje: {text[:200]}...")
                response.raise_for_status()
            logger.debug(f"← _send_message() → enviado")
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje: {e}", exc_info=True)
    
    def get_updates(self, timeout: int = 60):
        """
        Obtiene actualizaciones de Telegram (long polling).
        
        Args:
            timeout: Timeout del long polling en segundos
            
        Returns:
            Lista de updates
        """
        logger.debug(f"→ get_updates(timeout={timeout}, offset={self.last_update_id + 1})")
        
        url = f"{self.client.api_url}/getUpdates"
        params = {
            'offset': self.last_update_id + 1,
            'timeout': timeout,
            'allowed_updates': ['message', 'callback_query', 'message_reaction']
        }
        
        try:
            response = requests.get(url, params=params, timeout=timeout + 5)
            
            if not response.ok:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Telegram API error en getUpdates: {error_data}")
                response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                updates = result.get('result', [])
                
                if updates:
                    logger.debug(f"← get_updates() → {len(updates)} updates recibidos")
                    
                    # Log de tipos de updates
                    update_types = {}
                    for update in updates:
                        for key in ['message', 'callback_query', 'message_reaction']:
                            if key in update:
                                update_types[key] = update_types.get(key, 0) + 1
                    
                    if update_types:
                        logger.info(f"📨 Updates recibidos: {', '.join(f'{k}={v}' for k, v in update_types.items())}")
                
                return updates
            else:
                logger.error(f"❌ Error en getUpdates: {result}")
                return []
                
        except requests.exceptions.Timeout:
            # Timeout es normal en long polling
            logger.debug(f"← get_updates() → timeout (normal)")
            return []
        except Exception as e:
            logger.error(f"❌ Error en getUpdates: {e}", exc_info=True)
            return []
    
    def run(self):
        """Ejecuta el bot (loop infinito)."""
        logger.debug("→ run()")
        logger.info("=" * 70)
        logger.info(f"🤖 BOT INICIADO - Modo: {self.mode}")
        logger.info("=" * 70)
        logger.info("Presiona Ctrl+C para detener")
        logger.info("")
        
        # Estadísticas
        stats = {
            'messages': 0,
            'callbacks': 0,
            'reactions': 0,
            'commands': 0
        }
        
        while self.running:
            try:
                # Obtener updates
                updates = self.get_updates(timeout=30)
                
                for update in updates:
                    # Actualizar last_update_id
                    self.last_update_id = update['update_id']
                    logger.debug(f"Procesando update_id={self.last_update_id}")
                    # Callback query (click en botón)
                    if 'callback_query' in update:
                        self.handle_callback_query(update['callback_query'])
                        stats['callbacks'] += 1
                    # Message reaction (emoji en mensaje)
                    elif 'message_reaction' in update:
                        self.handle_message_reaction(update['message_reaction'])
                        stats['reactions'] += 1
                    # Mensaje (comando)
                    elif 'message' in update and 'text' in update['message']:
                        message = update['message']
                        text = message['text']
                        if text.startswith('/'):
                            self.handle_command(message)
                            stats['commands'] += 1
                        stats['messages'] += 1
                
            except KeyboardInterrupt:
                logger.info("")
                logger.info("⚠️  Deteniendo bot...")
                logger.debug(f"← run() → interrumpido por usuario")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Error en loop del bot: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("=" * 70)
        logger.info("🛑 BOT DETENIDO")
        logger.info(f"📊 Estadísticas: {stats['commands']} comandos, {stats['callbacks']} callbacks, "
                   f"{stats['reactions']} reacciones, {stats['messages']} mensajes")
        logger.info("=" * 70)
        logger.debug(f"← run() completado")
