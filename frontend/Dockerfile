FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
ARG VITE_MS4_URL
ENV VITE_MS4_URL=$VITE_MS4_URL
COPY . .
RUN npm run build

FROM node:18-alpine
RUN npm install -g serve
COPY --from=build /app/dist /app/dist
CMD ["sh", "-c", "serve -s /app/dist -l ${PORT:-3000}"]
