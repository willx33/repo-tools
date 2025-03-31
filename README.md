# Repo Tools

A collection of tools to streamline AI-assisted development workflows.

## Features

- **Local Repo Code Context Copier**: Copies relevant code context from local git repos to your clipboard for use with AI assistants.
- **GitHub Repo Code Context Copier**: Extracts and copies code context from GitHub repositories by URL (no local clone needed beforehand).
- **WebUI Interface**: Access all functionality through a modern web interface that runs alongside the CLI.

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

> **Note**: The WebUI requires Flask and Flask-SocketIO, which are included in the requirements.txt file. These will be installed automatically when you run the commands above.

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

### WebUI Interface

The tool includes a modern web interface that provides the same functionality as the CLI:

1. Select "Start WebUI" from the main menu
2. The web interface will open automatically in your default browser at `http://127.0.0.1:5000/`
3. You can continue using the CLI while the web interface is running
4. Navigate between tabs to access different tools
5. Use the "Refresh Repository Files" button to update any selected repositories with the latest changes
6. When you exit the CLI, the web interface will also shut down automatically

The WebUI uses a dark theme and provides a more visual way to interact with the tools, particularly helpful for visualizing file selections.

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
7. After selecting repositories, use the "Refresh repository files" option to update any repositories with the latest changes

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
7. Use the "Refresh repository files" option to update any repositories with the latest changes from GitHub

## WebUI Architecture

The WebUI component uses the following architecture:

- **Backend**: Flask and Flask-SocketIO
- **Frontend**: Pure HTML, CSS, and JavaScript (no frontend frameworks required)
- **Communication**: RESTful API endpoints + real-time WebSocket for long-running tasks
- **Threading**: The WebUI runs in a background thread, allowing the CLI to remain fully functional

### Key Components:

1. **Flask Server**: Handles HTTP requests and renders the HTML templates
2. **SocketIO**: Provides real-time communication for tasks like repository scanning
3. **Background Thread**: Ensures the web interface doesn't block the CLI
4. **Daemon Thread**: Automatically shuts down when the main program exits

### Design Principles:

- **Non-intrusive**: The WebUI runs alongside the CLI without affecting its functionality
- **Modern UI**: Dark theme with a clean, minimalist interface
- **Responsive**: Works on various screen sizes
- **Feature Parity**: Provides the same functionality as the CLI but with a visual interface

The WebUI is entirely self-contained within the application - no external services or databases are required. It's designed to spin up instantly when selected from the menu and shut down cleanly when the program exits.
