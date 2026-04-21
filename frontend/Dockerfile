# Production image for the HyperCube web tier.
# Context: repository root (`.`) so nginx/nginx.conf can be baked in.
# The image embeds the SvelteKit static build AND the nginx config, so
# the runtime needs no volume mounts — perfect for pull-and-run deploys.

FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

ARG BASE_PATH=/hypercube
ENV BASE_PATH=${BASE_PATH}

RUN npm run build


FROM nginx:alpine AS runtime

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 7003

CMD ["nginx", "-g", "daemon off;"]
