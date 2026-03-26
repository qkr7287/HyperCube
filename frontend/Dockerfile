# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG BASE_PATH=/dcmtool
ENV BASE_PATH=${BASE_PATH}

RUN npm run build

# Production stage - nginx serves static files
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 7003

CMD ["nginx", "-g", "daemon off;"]
