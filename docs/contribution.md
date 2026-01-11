# Contributing

We are always happy to see new contributors! If small or large, every contribution is welcome. Please follow these guidelines to ensure a smooth contribution process.

## Development Process

We use `uv` as our Python package manager and project tool. If you don't have `uv` installed, follow the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

1. Clone or fork the repository from GitHub.

```bash
# Clone the repository
git clone https://github.com/metasauce/plistsync
cd plistsync
```

2. Install the required dependencies (including dev, test dependencies and all optional dependencies)

```bash
uv sync --all-groups --all-extras
```

3. Make your changes in a new branch.

```bash
git checkout -b my-feature-branch
```

- Write code
- Add or update tests as needed
- Update documentation if your changes affect the public API

4. Ensure code meets quality standards.

```bash
# Activate the virtual environment first
source ./.venv/bin/activate

# Check code style and formatting
ruff check .
ruff format --check .

# Run type checking
mypy .

# Run tests
pytest .
```

5. Commit your changes with clear messages.

```bash
git add .
git commit -m "Add feature X"
```

### 6. Run pre-commit hooks (optional but recommended)

If you want to run the same checks that will run in CI:

```bash
uv run pre-commit run --all-files
```

## Report Bugs

If you encounter any bugs or issues, please report them on the [GitHub Issues page](https://github.com/metasauce/plistsync/issues).

## Submit Pull Requests

Feel free to follow this [guide](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project) for more information on how to create a pull request. Once you are done we will review your changes as soon as possible. Please be patient, as we are a small team and may not be able to review your changes immediately.

## Code Style

We use:

- **Ruff** for linting and formatting
- **mypy** for type checking
- **pytest** for testing

Please ensure your code passes all checks before submitting a pull request.
