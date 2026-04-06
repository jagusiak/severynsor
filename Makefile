.PHONY: build setup up down test lint create-app migrate makemigrations grab-data

# Build the docker image
build:
	docker-compose build

# Setup the initial database and superuser
setup: build
	docker-compose up -d db
	sleep 3
	docker-compose run --rm web python manage.py migrate
	docker-compose run -e DJANGO_SUPERUSER_PASSWORD=admin --rm web python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

# Run the app
up:
	docker-compose up -d

# Stop the app
down:
	docker-compose down

# Run tests
test:
	docker-compose run --rm web python manage.py test

# Check styling with ruff
lint:
	docker-compose run --rm web ruff check .

# Create a new app (usage: make create-app name=app_name)
create-app:
	docker-compose run --rm web python manage.py startapp $(name)

# Make database migrations
makemigrations:
	docker-compose run --rm web python manage.py makemigrations

# Apply database migrations
migrate:
	docker-compose run --rm web python manage.py migrate

# Grab sensor data manually or via cron
grab-data:
	docker-compose exec web python manage.py grab_sensor_data
