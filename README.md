# AI Workflow

A collection of tools to streamline AI-assisted development workflows.

## Features

- **Local Repo Code Context Copier**: Copies relevant code context from local git repos to your clipboard for use with AI assistants.
- **GitHub Repo Code Context Copier**: Extracts and copies code context from GitHub repositories by URL (no local clone needed beforehand).

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

### Local Repo Code Context Copier

This tool helps you copy code context from a local git repository to your clipboard, respecting .gitignore rules. Perfect for providing context to AI assistants.

1. Select "Local Repo Code Context Copier" from the main menu
2. Choose a directory path to scan for repositories (paths from current directory up to the root will be shown)
3. Select a repository from the discovered list
4. The content will be copied to your clipboard with the following format:
   ```
   /absolute/path/to/file.ext:
   file content here...
   ```
5. A toast notification will confirm when the copy is complete
6. You'll be returned to the repository selection menu where you can select another repository

### GitHub Repo Code Context Copier

This tool fetches code context from GitHub repositories directly via their URL and copies it to your clipboard.

1. Select "GitHub Repo Code Context Copier" from the main menu
2. Enter a GitHub repository URL (the tool can extract the repo URL even if you provide a longer URL with additional paths)
3. The tool will clone the repository to a temporary directory and analyze its files
4. The content will be copied to your clipboard with the following format:
   ```
   path/to/file.ext:
   file content here...
   ```
5. A toast notification will confirm when the copy is complete
6. You can choose to add another repository or return to the main menu