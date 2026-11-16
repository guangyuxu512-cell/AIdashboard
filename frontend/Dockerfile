FROM node:22-bookworm-slim AS build

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json ./frontend/package.json
COPY electron/package.json ./electron/package.json
COPY mobile/package.json ./mobile/package.json

RUN corepack enable && pnpm install --frozen-lockfile \
    --filter @control-center/frontend... \
    --filter @control-center/mobile...

COPY frontend ./frontend
COPY mobile ./mobile

ARG VITE_API_MODE=real
ARG VITE_API_BASE_URL=/
ARG MOBILE_VITE_API_BASE_URL=/api/v1/

ENV VITE_API_MODE=${VITE_API_MODE} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    MOBILE_VITE_API_BASE_URL=${MOBILE_VITE_API_BASE_URL}

RUN pnpm --filter @control-center/frontend build && \
    VITE_API_BASE_URL=${MOBILE_VITE_API_BASE_URL} pnpm --filter @control-center/mobile build

FROM nginx:1.27-alpine

COPY frontend/deploy/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html
COPY --from=build /workspace/mobile/dist /usr/share/nginx/html/mobile

EXPOSE 18080
