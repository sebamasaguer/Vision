# Stage 1: build de la landing (marketing, servida en /)
FROM node:22-alpine AS build-landing
WORKDIR /app
COPY landing/package*.json ./
RUN npm install --no-audit --no-fund
COPY landing/ .
ARG VITE_EMAILJS_SERVICE_ID
ARG VITE_EMAILJS_TEMPLATE_ID
ARG VITE_EMAILJS_PUBLIC_KEY
ENV VITE_EMAILJS_SERVICE_ID=$VITE_EMAILJS_SERVICE_ID
ENV VITE_EMAILJS_TEMPLATE_ID=$VITE_EMAILJS_TEMPLATE_ID
ENV VITE_EMAILJS_PUBLIC_KEY=$VITE_EMAILJS_PUBLIC_KEY
RUN npm run build

# Stage 2: build de la app (dashboard, servida en /admin/)
FROM node:22-alpine AS build-app
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 3: nginx sirviendo ambos builds por path
FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-landing /app/dist /usr/share/nginx/html
COPY --from=build-app /app/dist /usr/share/nginx/html/admin
EXPOSE 80
