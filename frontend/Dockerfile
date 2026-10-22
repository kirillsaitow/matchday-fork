FROM node:22-alpine

WORKDIR /app

# npm ci ставит строго те версии, что записаны в package-lock.json.
# Благодаря этому сборка у всех в команде одинаковая.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
