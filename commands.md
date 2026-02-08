# For migrations
docker-compose run --rm migration alembic revision --autogenerate -m "Database changes"
docker-compose run --rm migration alembic upgrade head

docker-compose exec astra_brain alembic current


# For open the postgres shell to run the query
docker exec -it gyan_db psql -U postgres -d gyan_db
