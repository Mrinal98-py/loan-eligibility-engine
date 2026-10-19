#!/bin/bash
set -e

# Initializes separate application database and n8n orchestration database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 1. Create Application Database & User
    CREATE USER loan_app_user WITH ENCRYPTED PASSWORD 'loan_app_password';
    CREATE DATABASE loan_engine OWNER loan_app_user;
    GRANT ALL PRIVILEGES ON DATABASE loan_engine TO loan_app_user;

    -- 2. Create n8n Persistence Database & User
    CREATE USER n8n_user WITH ENCRYPTED PASSWORD 'n8n_secure_password';
    CREATE DATABASE n8n_db OWNER n8n_user;
    GRANT ALL PRIVILEGES ON DATABASE n8n_db TO n8n_user;
EOSQL

# Apply initial schema to loan_engine
psql -v ON_ERROR_STOP=1 --username "loan_app_user" --dbname "loan_engine" -f /docker-entrypoint-initdb.d/schema.sql
psql -v ON_ERROR_STOP=1 --username "loan_app_user" --dbname "loan_engine" -f /docker-entrypoint-initdb.d/seed_demo_products.sql
