# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

# npm ci 대신 install 사용 (의존성 문제 해결을 위해)
RUN npm install

COPY . .

ENV VITE_HOST=0.0.0.0
ENV HOST=0.0.0.0

EXPOSE 5173

# CMD는 docker-compose에서 덮어씌우지만, 기본값으로 둡니다.
CMD ["npm", "run", "dev", "--", "--host"]