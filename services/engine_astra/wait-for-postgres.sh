#!/bin/sh
# wait-for-postgres.sh

set -e

# Get host and user from the environment variables
host=$(echo $DATABASE_URL | cut -d'@' -f2 | cut -d':' -f1)
user=$(echo $DATABASE_URL | cut -d'/' -f3 | cut -d':' -f1)

echo "Waiting for database at host: $host"

# Loop until postgres is ready
until pg_isready -h "$host" -U "$user"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# We just exit successfully.
>&2 echo "Postgres is up!"

exec "$@"