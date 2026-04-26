#!/bin/bash
set -x  # Enable debug output

echo "Canton Starting..."
echo "DATABASE_URL: ${DATABASE_URL:0:30}..."

# Parse DATABASE_URL
if [ -n "$DATABASE_URL" ]; then
  export PGHOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
  export PGPORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
  export PGDATABASE=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
  export PGUSER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
  export PGPASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
fi

echo "DB Config: $PGUSER@$PGHOST:$PGPORT/$PGDATABASE"

# Wait for postgres
echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" 2>/dev/null; then
    echo "PostgreSQL ready!"
    break
  fi
  echo "Attempt $i/30..."
  sleep 2
done

# Export for Canton config
export CANTON_DB_HOST="$PGHOST"
export CANTON_DB_PORT="$PGPORT"
export CANTON_DB_NAME="$PGDATABASE"
export CANTON_DB_USER="$PGUSER"
export CANTON_DB_PASSWORD="$PGPASSWORD"

echo "Starting Canton..."
exec /canton/bin/canton daemon -c /canton/config/canton-railway.conf
