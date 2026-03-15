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
ruff check --fix .
ruff format .

# Run type checking
mypy .

# Strip output from notebooks (if modified)
find . -name '*.ipynb' -exec nbstripout --keep-output {} +

# Run mypy on notebooks
./.github/workflows/mypy_notebooks.sh
```

If this looks tedious you may alternatively install the
pre-commit hooks to automatically enforce code quality standards before each commit (this runs the commands above autocmatically).

```bash
# Install the git hooks
pre-commit install
```

Once installed, every `git commit` will trigger automatic formatting with ruff, type checking with mypy, and linting. If you need to skip these checks (e.g., for a work-in-progress commit), use `git commit --no-verify`.

5. Run tests

```bash
pytest .
```

5. Commit your changes with clear messages.

```bash
git add .
git commit -m "Add feature X"
```

## Good First Issues

Looking for a place to start? Search the codebase for `TODO` and `FIXME` comments. These mark areas that need improvement, new features, or bug fixes and are often great entry points for new contributors.

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

```{toctree}
:maxdepth: 2
:hidden:

dev/debug.md
```

## Notes on AI usage

We are not opposed to AI-generated contributions, but communication should be handled by a real person. We will ask you questions about your PR and you need to be able to make clear you understood the proposed changes. Also you need to be clearly disclosed upfront if the content is AI-generated.

> We value human oversight and accountability, AI as a tool, not a contributor.
