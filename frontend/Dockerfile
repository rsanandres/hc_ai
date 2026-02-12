FROM node:22

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application code
COPY . .

# Build argument for API URL (baked into the build)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build the Next.js app
RUN npm run build

# Run as non-root user (node user is built into the node image)
USER node

# Expose port
EXPOSE 3000

# Run production server
CMD ["npm", "run", "start"]
