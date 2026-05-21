#!/usr/bin/env bash
# Rebuildea el frontend y copia el dist/ a backend/app/static/
# para que el ZIP de "Versiones local" lo incluya y que el Dockerfile
# de producción lo empaquete en el container sin necesidad de Node.
#
# Uso:  ./scripts/copy_frontend.sh
#
# Correlo cada vez que cambies el frontend Y querés:
#   - actualizar lo que sirve el container de producción en /api → SPA
#   - actualizar lo que se descarga en "Versiones local"

set -e
cd "$(dirname "$0")/.."

echo "==> Buildeando frontend con Vite..."
cd frontend
npm run build
cd ..

echo "==> Copiando frontend/dist → backend/app/static/"
rm -rf backend/app/static
mkdir -p backend/app/static
cp -r frontend/dist/* backend/app/static/

echo ""
echo "Listo. Recordá commitear backend/app/static/ para que el deploy lo levante."
ls -la backend/app/static/ | head -10
