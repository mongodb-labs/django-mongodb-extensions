default:
    echo 'Hello, world!'

test:
    uvx --with '.[test]' pytest .

coverage:
    uvx --with '.[test]' pytest --cov --cov-report=term --cov-report=html --cov-report=xml

lint:
    uvx pre-commit run --all-files --hook-stage manual
