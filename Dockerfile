# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# System monitoring tools
RUN apk add --no-cache util-linux procps iproute2 net-tools

COPY --from=builder /app/build ./build
COPY --from=builder /app/server.js ./
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules

ENV NODE_ENV=production
ENV PORT=3334
ENV ORIGIN=http://192.168.0.16:7003

EXPOSE 3334

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:3334/ || exit 1

CMD ["node", "server.js"]
