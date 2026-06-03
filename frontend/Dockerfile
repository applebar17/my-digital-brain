FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_WEB_CHAT_AUTH_TOKEN=change-me-web-chat-token
ARG VITE_OWNER_ID=owner-local
ARG VITE_SENDER_ID=owner-local
ARG VITE_CONVERSATION_ID=web-local

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_WEB_CHAT_AUTH_TOKEN=${VITE_WEB_CHAT_AUTH_TOKEN}
ENV VITE_OWNER_ID=${VITE_OWNER_ID}
ENV VITE_SENDER_ID=${VITE_SENDER_ID}
ENV VITE_CONVERSATION_ID=${VITE_CONVERSATION_ID}

COPY index.html vite.config.ts tsconfig*.json ./
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
