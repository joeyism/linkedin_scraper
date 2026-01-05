# Contributing to LinkedIn Scraper

Thank you for your interest in contributing to LinkedIn Scraper! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Git

### Setting Up Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/joeyism/linkedin_scraper.git
   cd linkedin_scraper
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Set up environment variables** (for testing)
   ```bash
   cp .env.example .env
   # Edit .env and add your LinkedIn credentials (optional, for integration tests)
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_person.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=linkedin_scraper
```

### Code Style

This project follows these guidelines:

- **PEP 8**: Python code style guide
- **Type hints**: Use type annotations where appropriate
- **Docstrings**: Document all public functions and classes
- **Line length**: Maximum 100 characters

Before submitting, ensure your code passes linting:

```bash
# Format code
black linkedin_scraper/

# Check for issues
flake8 linkedin_scraper/
mypy linkedin_scraper/
```

### Testing Your Changes

1. Write tests for new functionality
2. Ensure all existing tests pass
3. Test manually with the sample scripts in `samples/`
4. Verify documentation is updated

## Making Changes

### Branching Strategy

- `main` - Stable release branch
- `feature/your-feature` - New features
- `fix/your-bugfix` - Bug fixes
- `docs/your-doc-change` - Documentation updates

### Commit Messages

Write clear, descriptive commit messages:

```
Add support for scraping job descriptions

- Extract full job description text
- Parse job requirements section
- Add tests for job description parsing
```

Format:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed explanation (wrap at 72 chars)
- List specific changes with bullet points

### Pull Request Process

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, well-documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "Your descriptive commit message"
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Go to the GitHub repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template
   - Wait for review

### Pull Request Guidelines

- **Description**: Clearly describe what changes you made and why
- **Tests**: Include tests that cover your changes
- **Documentation**: Update README.md or other docs if needed
- **Small PRs**: Keep changes focused and manageable
- **Responsive**: Be ready to address feedback

## What to Contribute

### Good First Issues

Look for issues labeled `good first issue` for beginner-friendly tasks:

- Documentation improvements
- Bug fixes
- Additional test coverage
- Code refactoring

### Feature Requests

Before implementing major features:

1. Check existing issues to avoid duplication
2. Open an issue to discuss the feature
3. Wait for maintainer approval
4. Implement the feature once approved

### Bug Reports

When reporting bugs, include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages/stack traces
- Sample code if possible

## Code Review Process

1. A maintainer will review your PR
2. They may request changes
3. Make requested changes and push updates
4. Once approved, a maintainer will merge your PR

## Questions?

If you have questions about contributing:

- Open an issue on GitHub
- Check existing issues and discussions
- Review the README.md for usage examples

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to LinkedIn Scraper! Your efforts help make this project better for everyone.
