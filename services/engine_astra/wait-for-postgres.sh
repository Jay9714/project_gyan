#!/bin/sh
# wait-for-postgres.sh

set -e

# We get the 'db' host from the DATABASE_URL
host=$(echo $DATABASE_URL | cut -d'@' -f2 | cut -d':' -f1)
# We get the 'postgres' user
user=$(echo $DATABASE_URL | cut -d'/' -f3 | cut -d':' -f1)

echo "Waiting for database at host: $host"

# We use 'pg_isready' to ping the server until it's ready
until pg_isready -h "$host" -U "$user"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"

# This runs whatever command we pass to it
exec "$@"