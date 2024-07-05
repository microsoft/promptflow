install-requirements:
	pip install -r requirements.txt

build:
	cd test_runner && ./build.sh

stop-all-tests:
	cd test_runner && docker-compose down --remove-orphans

test-mock:
	cd test_runner && ./test.sh mock

test-staticsync:
	cd test_runner && ./test.sh staticsync

test-staticasync:
	cd test_runner && ./test.sh staticasync

test-flexasync:
	cd test_runner && ./test.sh flexasync
