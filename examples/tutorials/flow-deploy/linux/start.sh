python connections_setup.py --file connections.sqlite --migration-secret-file /run/secrets/MIGRATION_SECRET --clean --ignore-errors
pf flow serve --source flow --host 0.0.0.0
