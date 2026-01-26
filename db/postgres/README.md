# PostgreSQL Setup

This directory contains the Docker Compose configuration for running PostgreSQL with pgvector extension.

## Quick Start

1. Ensure you have the required environment variables set in your `.env` file at the project root:
   ```
   DB_USER=postgres
   DB_PASSWORD=your_password_here
   DB_NAME=your_database_name
   DB_HOST=localhost
   DB_PORT=5432
   ```

2. Start the PostgreSQL container:
   ```bash
   cd db/postgres
   docker-compose up -d
   ```

3. Verify the container is running:
   ```bash
   docker ps | grep postgres-db
   ```

## Data Persistence

The database data is persisted in `../../postgres_data` (relative to this directory), which maps to the project root `postgres_data/` directory. This ensures your data persists even if you stop or remove the container.

## Connection

- **Host**: `localhost` (from your host machine)
- **Port**: `5432`
- **Database**: Value of `DB_NAME` from your `.env`
- **User**: Value of `DB_USER` from your `.env`
- **Password**: Value of `DB_PASSWORD` from your `.env`

## Stopping the Database

To stop the container:
```bash
docker-compose down
```

To stop and remove volumes (⚠️ **WARNING**: This will delete all data):
```bash
docker-compose down -v
```

## Schema and Tables

The application automatically creates:
- Schema: `hc_ai_schema` (configurable via `HC_AI_SCHEMA` env var)
- Vector store table: `hc_ai_table` (created automatically by the application)

## Troubleshooting

- **Port already in use**: Make sure port 5432 is not already in use by another PostgreSQL instance
- **Connection refused**: Ensure the container is running with `docker ps`
- **Authentication failed**: Verify your `DB_USER` and `DB_PASSWORD` match what's in the container
