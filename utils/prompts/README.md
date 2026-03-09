# 📝 Sistema de Prompts

Este directorio contiene los prompts utilizados por el LLM para generar resúmenes.

## 📁 Estructura

```
prompts/
├── category_summary.txt     # Prompt genérico (usado por defecto)
├── categories/              # Prompts específicos por categoría
│   ├── linux.txt
│   ├── seguridad.txt
│   └── devops.txt
└── README.md                # Este archivo
```

## 🎯 Cómo funciona

El sistema busca prompts en este orden:

1. **Prompt específico**: `categories/{categoria}.txt`
2. **Prompt genérico**: `category_summary.txt` (fallback)

### Ejemplo:

```
Categoría: "Linux"
  ↓
Busca: prompts/categories/linux.txt
  ↓
¿Existe? → Sí: usa ese prompt
         → No: usa category_summary.txt
```

## ✏️ Crear prompt específico para una categoría

### 1. Crear archivo

El nombre del archivo debe ser el nombre de la categoría en **lowercase** y con **guiones bajos** en lugar de espacios:

```
"Linux" → linux.txt
"Noticias Linux" → noticias_linux.txt
"Noticias Seguridad" → noticias_seguridad.txt
```

### 2. Ubicación

Coloca el archivo en `prompts/categories/`:

```bash
prompts/categories/linux.txt
prompts/categories/seguridad.txt
```

### 3. Formato del prompt

El prompt debe usar estos **placeholders**:

- `{category_name}` - Nombre de la categoría
- `{num_articles}` - Cantidad de artículos
- `{max_tokens}` - Límite de tokens
- `{articles}` - Artículos formateados (automático)

**Ejemplo** (`prompts/categories/seguridad.txt`):

```
Eres un experto en ciberseguridad que resume las últimas amenazas y vulnerabilidades.

# CATEGORÍA: {category_name}

Tienes {num_articles} artículos de seguridad. 

ENFOQUE ESPECIAL:
- Prioriza CVEs y vulnerabilidades críticas
- Menciona vectores de ataque
- Indica si hay parches disponibles
- Usa referencias con superíndice¹ ² ³

Máximo {max_tokens} tokens.

# ARTÍCULOS:

{articles}

---

Genera el resumen enfocado en ciberseguridad:
```

## 📋 Variables disponibles en artículos

Cada artículo en `{articles}` tiene este formato:

```
[ID_ARTICULO] Título del artículo
Feed: Nombre del feed
Contenido: Texto completo del artículo

```

**El ID es importante** para las referencias con superíndice.

## 💡 Consejos

### Para prompts específicos:

**Linux**:
- Enfocarse en distribuciones, kernel, software libre
- Mencionar versiones de paquetes

**Seguridad**:
- Priorizar CVEs, CVSS scores
- Mencionar vectores de ataque
- Indicar parches/mitigaciones

**DevOps**:
- Enfocarse en herramientas, CI/CD, infraestructura
- Mencionar versiones y releases

**Noticias generales**:
- Más contexto empresarial
- Menos detalles técnicos

### Estilo conversacional:

✅ **Bueno**:
```
Se descubrieron tres vulnerabilidades críticas en Cisco ASA¹, Fortinet FortiOS² 
y Palo Alto PAN-OS³ que permiten ejecución remota de código...
```

❌ **Malo**:
```
## Vulnerabilidades Críticas
- Cisco ASA: CVE-2024-1234
- Fortinet FortiOS: CVE-2024-5678
```

## 🔄 Actualizar prompts

Los cambios en los archivos `.txt` se aplican **inmediatamente**. No necesitas reiniciar nada.

1. Edita el archivo de prompt
2. Ejecuta el test o el programa
3. El nuevo prompt se usa automáticamente

## 🧪 Probar prompts

```bash
# Probar con fixtures (usa los mismos artículos)
python tests/integration/test_etapa3_llm.py

# Los resúmenes se guardan en:
tests/logs/etapa3_llm/summaries/
```

## 📊 Ver qué prompt se usó

En los logs aparece:

```
→ Usando prompt específico para categoría: Linux
→ Usando prompt genérico (no existe específico para DevOps)
```

## 🎨 Ejemplos de prompts por categoría

### Seguridad (`categories/seguridad.txt`)
```
Eres un analista de ciberseguridad que resume amenazas y vulnerabilidades.

Prioriza:
- CVEs críticos y altos
- Exploits activos
- Vectores de ataque
- Disponibilidad de parches

Usa lenguaje técnico pero claro. Referencias con superíndice.

{category_name} | {num_articles} artículos | Max {max_tokens} tokens

{articles}
```

### Linux (`categories/linux.txt`)
```
Resumen de noticias del ecosistema Linux y software libre.

Enfoque:
- Releases de distribuciones
- Actualizaciones de kernel
- Proyectos open source importantes
- Comunidad y eventos

Estilo conversacional, referencias con superíndice.

{category_name} | {num_articles} artículos | Max {max_tokens} tokens

{articles}
```

---

**💡 Tip**: Empieza con el prompt genérico y crea específicos solo para las categorías donde notes que el resumen no es óptimo.