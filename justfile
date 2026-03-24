default:
    echo 'Hello, world!'

test:
    uv run --extra test --with django-mongodb-backend django-admin test -v 2 \
        --settings=tests.settings

test-coverage:
    uv run --extra test --with django-mongodb-backend \
        coverage run -m django test -v 2 --settings=tests.settings

coverage-html:
    coverage html

lint:
    uvx pre-commit run --all-files --hook-stage manual
