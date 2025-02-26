# CLAUDE.md - Repository Guidelines

## Build Commands
- Install: `pip install -e .`
- Run application: `repo-tools`
- Test: `pytest`

## Code Style Guidelines
- Formatting: Follow PEP 8 for Python code style
- Imports: Standard library first, third party second, local modules last
- Types: Use type annotations following PEP 484; prefer explicit typing
- Documentation: Document classes and functions with docstrings ("""triple quotes""")
- Error handling: Use try/except blocks with specific exceptions
- Variables: Use snake_case for variables and functions
- Classes: Use PascalCase for class names
- Constants: Use UPPER_CASE for constants

## Architecture
The application is structured as a Python CLI tool with a module-based approach:
- `cli.py`: Entry point
- `menu.py`: Interactive menu system
- `modules/`: Individual tool implementations
- `utils/`: Shared utility functions

Functions should be focused on a single responsibility. Prefer composition over inheritance.