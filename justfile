default:
    echo 'Hello, world!'

test:
    uv run --extra test --with django-mongodb-backend django-admin test --settings=tests.settings

lint:
    uvx pre-commit run --all-files --hook-stage manual
