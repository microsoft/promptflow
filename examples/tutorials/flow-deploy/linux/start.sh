python connections_setup.py --file connections.sqlite --encryption-key-file /run/secrets/ENCRYPTION_KEY --clean --ignore-errors
pf flow serve --source flow --host 0.0.0.0
