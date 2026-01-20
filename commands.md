# For migrations
docker-compose run --rm migration alembic revision --autogenerate -m "Add Sector Performance"
docker-compose run --rm migration alembic upgrade head


# For open the postgres shell to run the query
docker exec -it gyan_db psql -U postgres -d gyan_db
