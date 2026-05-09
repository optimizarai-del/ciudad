# ─── Frontend CIUDAD — React + Vite ─────────────────────────────────────────
# Stage 1: build
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# La URL del backend se inyecta en el bundle. Pasala como build-arg desde
# Easypanel: --build-arg VITE_API_URL=https://api.ciudad.optimizar-ia.com
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Stage 2: serve estático con nginx
FROM nginx:alpine

# SPA fallback + cache headers + gzip
COPY --from=build /app/dist /usr/share/nginx/html

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ > /dev/null || exit 1
