default:
    echo 'Hello, world!'

test:
    echo 'TODO'

lint:
    uvx pre-commit run --all-files --hook-stage manual
