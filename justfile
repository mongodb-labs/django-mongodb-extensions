default:
    echo 'Hello, world!'

test:
    uvx pytest .

lint:
    uvx pre-commit run --all-files --hook-stage manual
