FROM node:20-alpine

WORKDIR /app

# Dependency layer — cached unless package.json changes
COPY package.json package-lock.json* ./
RUN npm install

# Source. Bind-mounted over in dev (see docker-compose.yml) so edits are live.
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
