# Severynsor Platform

A Django-based application designed to collect external sensor telemetry via a REST API authentication protocol and showcase dynamic progress metrics.

## Features

- **Dockerized Setup**: Fully self-contained Django and PostgreSQL orchestration.
- **RESTful Sensor Pipeline**: Authenticate sensors through standard Bearer tokens (`Authorization: Bearer <token>`) and collect metrics dynamically.
- **Admin Insight Component**: Native integration with Unfold Admin interface out of the box, with built-in time-series graphs scaling your sensor measurements in real-time right on the admin model form.

## Quickstart

Run our fully integrated Makefile commands to spin up your application.

```bash
# 1. Setup Postgres and initial server tables, superuser config, and perform Django migrations
make setup

# 2. Spawn and daemonize your local web and db workers
make up
```

Login into your admin panel mounted dynamically onto localhost's root `http://localhost:8000/`.
- Default Username: `admin`
- Default Email: `admin@example.com`

> **Note**: To stop the instance, you can use `make down`.

## Development Commands

- `make build` → Rebuild the application containers.
- `make setup` → Creates all dependent instances, migrates the API, and provides a default user.
- `make up` → Load background daemon.
- `make down` → Teardown network bindings.
- `make test` → Execute local backend assertions and test API parameters via Docker container.
- `make lint` → Enforce consistent formatting policies utilizing Dockerized `ruff`.
- `make create-app name=<app>` → Utilize Django scaffolding within virtual limits.

## REST Integrations

The REST interface will listen on `POST /api/records/`.
Measurements demand precise floating values bounded with chronological precision strings formatted strictly according to ISO directives.

**Headers:**
`Authorization: Bearer <SENSOR_TOKEN_KEY>`
(Generate unique keys seamlessly out of the Unfold layout by generating a Severynsor schema!)

**Payload format:**
```json
{
  "value": 45.6,
  "timestamp": "2026-04-03T09:00:00Z"
}
```
**Code Responses**:
- `201 CREATED`: Data published dynamically
- `401 UNAUTHORIZED`: Invalid Authorization Bearer signature scheme or unhandled key.
- `400 BAD REQUEST`: Invalid payload.
