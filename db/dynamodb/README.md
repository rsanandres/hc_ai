# DynamoDB Local Setup

This directory contains the Docker Compose configuration for running DynamoDB Local, used for session storage.

## Quick Start

1. Ensure you have the required environment variables set in your `.env` file at the project root:
   ```
   DDB_ENDPOINT=http://localhost:8001
   AWS_REGION=us-east-1
   DDB_TURNS_TABLE=hcai_session_turns
   DDB_SUMMARY_TABLE=hcai_session_summary
   DDB_AUTO_CREATE=true
   SESSION_RECENT_LIMIT=10
   ```

2. Start the DynamoDB Local container:
   ```bash
   cd db/dynamodb
   docker-compose up -d
   ```

3. Verify the container is running:
   ```bash
   docker ps | grep dynamodb-local
   ```

## Data Persistence

The DynamoDB data is persisted in `../../POC_retrieval/docker/dynamodb` (relative to this directory). This ensures your session data persists even if you stop or remove the container.

## Connection

- **Endpoint**: `http://localhost:8001` (from your host machine)
- **Region**: `us-east-1` (default, configurable via `AWS_REGION`)
- **Credentials**: Not required for local DynamoDB (dummy credentials are used automatically)

## Tables

The application automatically creates tables if `DDB_AUTO_CREATE=true`:
- **Turns table**: `hcai_session_turns` (stores conversation turns)
- **Summary table**: `hcai_session_summary` (stores session summaries)

## Stopping the Database

To stop the container:
```bash
docker-compose down
```

To stop and remove volumes (⚠️ **WARNING**: This will delete all session data):
```bash
docker-compose down -v
```

## Troubleshooting

- **Port already in use**: Make sure port 8001 is not already in use. The unified API uses port 8000, so DynamoDB uses 8001 to avoid conflicts.
- **Connection refused**: Ensure the container is running with `docker ps`
- **MissingAuthenticationToken error**: Verify `DDB_ENDPOINT` is set to `http://localhost:8001` in your `.env` file

## Alternative Setup

If you prefer to use a different docker-compose file, you can use:
```bash
docker-compose -f docker-compose-dynamodb.yml up -d
```
