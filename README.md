# Repo Tools

A collection of tools I made to streamline my AI-assisted dev workflows.

## What it does

- **Copy code from local repos** - Grabs context from local git repos, respecting gitignores
- **Copy code from GitHub repos** - Extracts code from GitHub URLs without cloning
- **WebUI Interface** - Modern web interface that's actually nice to use

## Install it

```bash
# Clone & cd into the repo
git clone [your-repo-url]
cd repo-tools

# Venv is always a good idea
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in dev mode
pip install -e .
```

## Use it

Run it one of two ways:

```bash
# Full CLI with menu
repo-tools

# Jump straight to the WebUI
repo-web
```

The WebUI has these cool features:
- Dark mode (obviously)
- Search and sort repos/files
- Copy individual files or whole directories 
- Collapsible file trees
- Shows token counts for LLM context limits

## Local Repo Copier

This grabs code from your local repos:

1. Choose a repo from the list
2. Select files you want (or let it handle things automatically)
3. Click "Copy Selected" or copy individual files
4. Paste directly to your AI assistant

## GitHub Repo Copier

Same deal but for GitHub repos:

1. Paste a GitHub URL
2. Select what you need
3. Copy & paste to your AI

## Command Line Options

If you're running the WebUI directly with `repo-web`:

```bash
# Run in debug mode
repo-web --debug

# Don't auto-open the browser
repo-web --no-browser

# Run in the background
repo-web --background
```
## Coming Soon
- Custom prompt saving and prompt customization, including built in prompts like output as XML Whole prompt.
- Built in XML Diff applicator, using repository selector then directly applying changes.

That's it! Made by me with ❤️
