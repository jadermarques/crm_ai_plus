#!/bin/bash

echo "🔍 Iniciando correção de imports nos arquivos Python..."

# Corrige 'from backend' para 'from src.backend'
# O grep evita substituir se já estiver corrigido (evita src.src.backend)
find src -type f -name "*.py" -exec grep -l "from backend" {} + | xargs sed -i 's/from backend/from src.backend/g'

# Corrige 'from core' para 'from src.core'
find src -type f -name "*.py" -exec grep -l "from core" {} + | xargs sed -i 's/from core/from src.core/g'

# Corrige 'from modules' para 'from src.modules'
find src -type f -name "*.py" -exec grep -l "from modules" {} + | xargs sed -i 's/from modules/from src.modules/g'

# Corrige 'from frontend' para 'from src.frontend' (caso exista referência cruzada)
find src -type f -name "*.py" -exec grep -l "from frontend" {} + | xargs sed -i 's/from frontend/from src.frontend/g'

echo "✅ Correção concluída! Tente rodar o uvicorn novamente."
