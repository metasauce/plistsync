# Contributing

We are always happy to see new contributors! If small or large, every contribution is welcome. Please follow these guidelines to ensure a smooth contribution process.


## Development Process

1. Clone or fork the repository from GitHub.
```bash
# Clone the repository
git clone https://github.com/metasauce/plistsync
cd plistsync
```

2. Install the required dependencies. It is recommended to use a virtual environment to avoid conflicts with other Python packages.
```bash
pip install -e '.[all]'
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
# Check code style
ruff check .
mypy .

# Run tests
pytest .
```

5. Commit your changes with clear messages.
```bash
git add .
git commit -m "Add feature X"
```

## Report Bugs

If you encounter any bugs or issues, please report them on the [GitHub Issues page](https://github.com/metasauce/plistsync/issues).

## Submit Pull Requests

Feel free to follow this [guide](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project) for more information on how to create a pull request. Once you are done we will review your changes as soon as possible. Please be patient, as we are a small team and may not be able to review your changes immediately.
