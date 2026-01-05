FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --production

COPY server.js ./
COPY public ./public

ENV API_BASE_URL=http://backend:8000
EXPOSE 3000

CMD ["npm", "start"]
