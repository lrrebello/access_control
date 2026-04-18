#!/bin/bash

echo "=================================================="
echo "          ESTRUTURA COMPLETA DO PROJETO"
echo "=================================================="
echo ""

echo "=== TREE (estrutura de pastas) ==="
tree -I '__pycache__|venv|env|.git|node_modules|__MACOSX|*.zip|*.pyc' --dirsfirst || \
find . -type d -not -path '*/__pycache__/*' -not -path '*/venv/*' -not -path '*/.git/*' | head -50

echo ""
echo "=================================================="
echo "          ARQUIVOS E SEU CONTEÚDO"
echo "=================================================="
echo ""

# Arquivos que queremos mostrar
find . -type f \
    -not -path '*/__pycache__/*' \
    -not -path '*/venv/*' \
    -not -path '*/env/*' \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/static/uploads/*' \
    -not -name '*.pyc' \
    -not -name '*.zip' \
    -not -name '*.log' \
    \( -name "*.py" -o -name "*.html" -o -name "*.css" -o -name "*.js" \
       -o -name "*.json" -o -name "*.yml" -o -name "*.yaml" \
       -o -name "requirements.txt" -o -name "*.env*" -o -name "README*" \) \
    | sort | while read -r file; do
        echo "=================================================="
        echo "📄 ARQUIVO: $file"
        echo "=================================================="
        echo ""
        cat "$file"
        echo ""
        echo "=================================================="
        echo ""
    done

echo "✅ Fim do cat_all.sh - Tudo enviado!"
