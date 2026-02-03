# Contributing to MTG Card Aggregator

Thank you for considering contributing to this project! We welcome contributions of all kinds.

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Initial Setup

```bash
# Clone repository
git clone https://github.com/patrickgaskill/mtg.git
cd mtg

# Install all dependencies including dev tools
uv sync --dev

# Set up pre-commit hooks
uv run pre-commit install

# Verify installation
uv run pytest
```

## Development

### Available Commands

```bash
# Data operations
uv run python card_aggregator.py download          # Fetch Scryfall data
uv run python card_aggregator.py update-types      # Update MTG types
uv run python card_aggregator.py run --serve       # Generate and view reports

# Testing
uv run pytest                    # Run test suite
uv run pytest --cov             # With coverage report
uv run pytest -k test_name      # Run specific test
uv run pytest -m "not slow"     # Skip slow tests

# Code quality
uv run ruff format .            # Format code
uv run ruff check .             # Lint code
uv run ruff check --fix .       # Auto-fix issues
uv run ty check                 # Type check
```

### Making Changes

1. Create a feature branch from main
2. Make your changes
3. Add or update tests
4. Ensure all checks pass
5. Commit with descriptive messages
6. Open a pull request

## Code Standards

### Style Requirements

- Python 3.12+ type hints (use `dict` not `Dict`, `list` not `List`)
- Google-style docstrings for public functions
- Functions should be under 80 lines
- Pass all ruff checks with zero violations
- Pass ty type checking
- Maintain or improve test coverage

### Testing Requirements

- Write tests for all new features
- Place tests in `tests/` directory
- Name test files as `test_*.py`
- Use fixtures from `tests/conftest.py`
- Target 80%+ coverage for new code

### Example Test

```python
def test_function_behavior():
    """Test that function handles input correctly."""
    result = my_function("input")
    assert result == "expected"
```

## Pull Requests

### Before Submitting

Run all quality checks:
```bash
uv run ruff format .
uv run ruff check .
uv run ty check
uv run pytest
```

### PR Guidelines

- Link to related issue if applicable
- Describe what changed and why
- Include test results
- Update relevant documentation
- Keep changes focused and atomic

### PR Checklist

- [ ] Tests added/updated and passing
- [ ] Code formatted with ruff
- [ ] No linting violations
- [ ] Type checking passes
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for user-facing changes)

## Project Structure

```
mtg/
├── aggregators/              # Aggregator implementations
│   ├── base.py              # Base aggregator class
│   ├── count_aggregators.py # Counting aggregators
│   ├── first_card_aggregators.py
│   ├── metadata_aggregators.py
│   ├── type_aggregators.py
│   └── supercycle_aggregators.py
├── templates/               # HTML templates
├── tests/                   # Test suite
├── card_aggregator.py      # Main CLI
├── card_utils.py           # Utility functions
└── type_updater.py         # Type scraper
```

## Adding Aggregators

Aggregators process cards and generate reports.

### Implementation Steps

**1. Choose location**
- `count_aggregators.py` - Counting/grouping
- `first_card_aggregators.py` - First by criteria
- `metadata_aggregators.py` - Promo/foil metadata
- `type_aggregators.py` - Type analysis
- New file for new categories

**2. Implement class**

```python
from aggregators.base import Aggregator

class MyAggregator(Aggregator):
    """Brief description of what this aggregates."""

    def __init__(self):
        super().__init__(
            name="my_aggregator",
            display_name="My Aggregator",
            description="Longer description for users"
        )
        self.column_defs = [
            {"field": "name", "headerName": "Card Name"},
            {"field": "value", "headerName": "Value"},
        ]
        self.data = []

    def process_card(self, card: dict[str, Any]) -> None:
        """Process a single card."""
        # Extract relevant data
        # Update internal state
        pass

    def get_sorted_data(self) -> list[dict[str, Any]]:
        """Return sorted data for display."""
        return sorted(self.data, key=lambda x: x["value"])
```

**3. Register aggregator**

Add to `create_all_aggregators()` in `card_aggregator.py`:
```python
return [
    # ... existing aggregators
    MyAggregator(),
]
```

**4. Write tests**

Create `tests/aggregators/test_my_aggregator.py`:
```python
from aggregators.my_aggregators import MyAggregator

def test_my_aggregator():
    """Test aggregator processes cards correctly."""
    agg = MyAggregator()
    agg.process_card({"name": "Test", "value": 5})
    data = agg.get_sorted_data()
    assert len(data) == 1
    assert data[0]["name"] == "Test"
```

**5. Test locally**
```bash
uv run python card_aggregator.py run --serve
```

## Common Tasks

### Running Local Server

```bash
uv run python card_aggregator.py run --serve
```
Opens browser to view generated reports.

### Updating Test Data

```bash
uv run python card_aggregator.py download
```

### Debugging Tests

```bash
# Run with verbose output
uv run pytest -vv

# Run specific test
uv run pytest tests/test_card_utils.py::test_extract_types -v

# Drop into debugger on failure
uv run pytest --pdb
```

### Checking Coverage

```bash
uv run pytest --cov --cov-report=html
open htmlcov/index.html
```

## Getting Help

- Review [CLAUDE.md](CLAUDE.md) for architecture details
- Check [existing issues](https://github.com/patrickgaskill/mtg/issues)
- Open new issue for bugs or feature requests
- Refer to [README.md](README.md) for usage information

## License

By contributing, you agree your contributions will be licensed under the MIT License.
