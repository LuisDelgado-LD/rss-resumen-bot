"""
Gestor de prompts para el cliente LLM.
Carga y formatea prompts desde archivos de texto.
"""
from pathlib import Path
from typing import Dict, List
import logging


logger = logging.getLogger(__name__)


class PromptManager:
    """Gestiona la carga y formateo de prompts desde archivos."""
    
    def __init__(self, prompts_dir: Path = None):
        """
        Inicializa el gestor de prompts.
        
        Args:
            prompts_dir: Directorio donde están los prompts (default: ./prompts)
        """
        if prompts_dir is None:
            # Buscar directorio prompts relativo al proyecto
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            prompts_dir = project_root / "utils/prompts"
        
        self.prompts_dir = Path(prompts_dir)
        
        if not self.prompts_dir.exists():
            logger.warning(f"⚠️ Directorio de prompts no encontrado: {self.prompts_dir}")
        
        logger.debug(f"PromptManager inicializado (prompts_dir: {self.prompts_dir})")
    
    def load_prompt(self, prompt_name: str) -> str:
        """
        Carga un prompt desde archivo.
        
        Args:
            prompt_name: Nombre del archivo de prompt (sin extensión)
            
        Returns:
            Contenido del prompt
            
        Raises:
            FileNotFoundError: Si el prompt no existe
        """
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt no encontrado: {prompt_file}\n"
                f"Disponibles: {self.list_prompts()}"
            )
        
        logger.debug(f"→ Cargando prompt: {prompt_name}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.debug(f"← Prompt cargado: {len(content)} chars")
        
        return content
    
    def format_category_prompt(
        self,
        category_name: str,
        articles: List[Dict],
        max_tokens: int = 2000
    ) -> str:
        """
        Formatea el prompt de resumen por categoría.
        
        Busca un prompt específico para la categoría, si no existe usa el genérico.
        
        Orden de búsqueda:
        1. prompts/categories/{category_name}.txt (específico)
        2. prompts/category_summary.txt (genérico)
        
        Args:
            category_name: Nombre de la categoría
            articles: Lista de artículos preparados
            max_tokens: Máximo de tokens para el resumen
            
        Returns:
            Prompt completo formateado
        """
        # Intentar cargar prompt específico de categoría
        category_safe_name = self._sanitize_category_name(category_name)
        category_prompt_path = self.prompts_dir / "categories" / f"{category_safe_name}.txt"
        
        if category_prompt_path.exists():
            logger.debug(f"→ Usando prompt específico para categoría: {category_name}")
            with open(category_prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            # Usar prompt genérico
            logger.debug(f"→ Usando prompt genérico (no existe específico para {category_name})")
            template = self.load_prompt("category_summary")
        
        # Formatear artículos con IDs
        articles_text = self._format_articles_with_ids(articles)
        
        # Reemplazar placeholders
        prompt = template.format(
            category_name=category_name,
            num_articles=len(articles),
            max_tokens=max_tokens,
            articles=articles_text
        )
        
        logger.debug(f"Prompt formateado: {len(prompt)} chars, {len(articles)} artículos")
        
        return prompt
    
    def format_all_categories_prompt(
        self,
        articles_by_category: Dict[str, List[Dict]],
        max_tokens_per_category: int = 2000
    ) -> str:
        """
        Formatea el prompt unificado con todas las categorías para una sola llamada LLM.

        La respuesta esperada del LLM es un JSON con la forma:
        {"CATEGORIA_1": "resumen...", "CATEGORIA_2": "resumen...", ...}

        Args:
            articles_by_category: Dict con categoría → lista de artículos
            max_tokens_per_category: Máximo de tokens por resumen de categoría

        Returns:
            Prompt completo formateado
        """
        logger.debug(
            f"→ format_all_categories_prompt("
            f"categories={list(articles_by_category.keys())}, "
            f"max_tokens_per_category={max_tokens_per_category})"
        )

        template = self.load_prompt("all_categories_summary")

        # Construir contenido de cada categoría
        sections = []
        for category_name in sorted(articles_by_category.keys()):
            articles = articles_by_category[category_name]
            articles_text = self._format_articles_with_ids(articles)
            sections.append(
                f"## CATEGORÍA: {category_name} ({len(articles)} artículos)\n\n{articles_text}"
            )

        categories_content = "\n\n---\n\n".join(sections)
        category_names = ", ".join(f'"{c}"' for c in sorted(articles_by_category.keys()))

        prompt = template.format(
            category_names=category_names,
            max_tokens_per_category=max_tokens_per_category,
            categories_content=categories_content
        )

        total_articles = sum(len(a) for a in articles_by_category.values())
        logger.debug(
            f"← format_all_categories_prompt() → {len(prompt)} chars, "
            f"{len(articles_by_category)} categorías, {total_articles} artículos"
        )

        return prompt

    def _sanitize_category_name(self, category_name: str) -> str:
        """
        Convierte nombre de categoría a nombre de archivo válido.
        
        Args:
            category_name: Nombre de la categoría
            
        Returns:
            Nombre sanitizado (lowercase, sin espacios ni caracteres especiales)
        """
        # Lowercase y reemplazar espacios por guiones bajos
        safe_name = category_name.lower().replace(' ', '_')
        
        # Remover caracteres no válidos
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
        
        return safe_name
    
    def _format_articles_with_ids(self, articles: List[Dict]) -> str:
        """
        Formatea artículos con sus IDs para el prompt.
        
        Args:
            articles: Lista de artículos
            
        Returns:
            Texto formateado
        """
        parts = []
        
        for article in articles:
            article_id = article['id']
            title = article['title']
            feed = article['feed_title']
            content = article['content']
            
            # Formato: [ID] Título | Feed | Contenido
            parts.append(f"[{article_id}] {title}")
            parts.append(f"Feed: {feed}")
            parts.append(f"Contenido: {content}")
            parts.append("")  # Línea en blanco
        
        return "\n".join(parts)
    
    def list_prompts(self) -> List[str]:
        """
        Lista los prompts disponibles.
        
        Returns:
            Lista de nombres de prompts (sin extensión)
        """
        if not self.prompts_dir.exists():
            return []
        
        prompts = [
            p.stem for p in self.prompts_dir.glob("*.txt")
        ]
        
        return sorted(prompts)