# AI Workflow

A collection of tools to streamline AI-assisted development workflows.

## Features

- **Repo Code Context Copier**: Copies relevant code context from git repos to your clipboard for use with AI assistants.

## Installation

### Option 1: Using requirements.txt (simpler)
```bash
# Clone the repository
git clone [your-repo-url]
cd ai-workflow

# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Option 2: Using pyproject.toml
```bash
# Clone the repository
git clone [your-repo-url]
cd ai-workflow

# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode (will install dependencies automatically)
pip install -e .
```

## Usage

Run the tool with:

```bash
repo-tools
```

Use arrow keys to navigate through the menu, and Enter to select an option.

### Repo Code Context Copier

This tool helps you copy code context from a git repository to your clipboard, respecting .gitignore rules. Perfect for providing context to AI assistants.

1. Select "Repo Code Context Copier" from the main menu
2. Choose a directory path to scan for repositories (paths from current directory up to the root will be shown)
3. Select a repository from the discovered list
4. The content will be copied to your clipboard with the following format:
   ```
   /absolute/path/to/file.ext:
   file content here...
   ```
5. A toast notification will confirm when the copy is complete
6. You'll be returned to the repository selection menu where you can select another repository