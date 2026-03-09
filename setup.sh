#!/bin/bash

# Script de configuración inicial para RSS News Digest Bot
# Autor: Tu nombre
# Descripción: Automatiza la configuración inicial del proyecto

set -e  # Salir si hay errores

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "  RSS News Digest Bot - Setup Inicial"
echo "=================================================="
echo ""

# 1. Verificar Python
echo -e "${YELLOW}[1/6]${NC} Verificando Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION encontrado"
else
    echo -e "${RED}✗${NC} Python 3 no encontrado. Por favor instálalo primero."
    exit 1
fi

# 2. Crear entorno virtual
echo ""
echo -e "${YELLOW}[2/6]${NC} Creando entorno virtual..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠️${NC} Se encontró un entorno virtual existente."
    read -p "¿Deseas eliminarlo y crear uno nuevo? (s/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[SsYy]$ ]]; then
        echo -e "${RED}🗑️  Eliminando entorno virtual anterior...${NC}"
        rm -rf venv
    else
        echo -e "${RED}❌ Operación cancelada. Manteniendo entorno virtual existente.${NC}"
        exit 0
    fi
fi

python3 -m venv venv
echo -e "${GREEN}✓${NC} Entorno virtual creado"

# 3. Activar entorno virtual
echo ""
echo -e "${YELLOW}[3/6]${NC} Activando entorno virtual..."
source venv/bin/activate

# Verificar que el venv funciona correctamente
WHICH_PIP=$(which pip)
if [[ "$WHICH_PIP" != *"venv/bin/pip"* ]]; then
    echo -e "${RED}✗${NC} Error: El venv no se activó correctamente"
    echo -e "${RED}✗${NC} pip está en: $WHICH_PIP (debería estar en venv/bin/pip)"
    echo ""
    echo "Por favor, ejecuta manualmente:"
    echo "  rm -rf venv"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo -e "${GREEN}✓${NC} Entorno virtual activado correctamente"
echo -e "${GREEN}✓${NC} Usando pip desde: $WHICH_PIP"

# 4. Instalar dependencias
echo ""
echo -e "${YELLOW}[4/6]${NC} Instalando dependencias..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencias instaladas"

# 5. Crear archivo .env
echo ""
echo -e "${YELLOW}[5/6]${NC} Configurando archivo .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓${NC} Archivo .env creado desde .env.example"
echo -e "${YELLOW}⚠️${NC}  IMPORTANTE: Debes editar el archivo .env con tus credenciales"
else
    echo -e "${GREEN}✓${NC} Archivo .env ya existe"
fi

# 6. Crear directorio de logs
echo ""
echo -e "${YELLOW}[6/6]${NC} Creando directorios necesarios..."
mkdir -p tests/logs
echo -e "${GREEN}✓${NC} Directorios creados"

# Resumen final
echo ""
echo "=================================================="
echo -e "${GREEN}✓ Setup completado exitosamente${NC}"
echo "=================================================="
echo ""
echo "📝 Próximos pasos:"
echo ""
echo "1. Edita el archivo .env con tus credenciales:"
echo "   nano .env"
echo ""
echo "2. Activa el entorno virtual (si no está activo):"
echo "   source venv/bin/activate"
echo ""
echo "3. Ejecuta la aplicación:"
echo "   python src/main.py"
echo ""
echo "4. Para desactivar el entorno virtual:"
echo "   deactivate"
echo ""
echo "=================================================="