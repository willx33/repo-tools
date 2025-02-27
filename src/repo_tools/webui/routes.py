"""Routes for the WebUI."""

import os
import json
from pathlib import Path
from flask import render_template, request, jsonify
from flask_socketio import emit

from repo_tools.webui import app, socketio
from repo_tools.utils.git import find_git_repos, get_repo_name, get_relevant_files_with_content
from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast

# Routes
@app.route('/')
def index():
    """Render the main landing page."""
    return render_template('index.html')

@app.route('/local-repo')
def local_repo():
    """Render the local repo context copier page."""
    return render_template('local_repo.html')

@app.route('/github-repo')
def github_repo():
    """Render the GitHub repo context copier page."""
    return render_template('github_repo.html')
    
@app.route('/settings')
def settings():
    """Render the settings page."""
    return render_template('settings.html')

# API Routes
@app.route('/api/paths')
def get_paths():
    """Get paths from current directory to root."""
    current_dir = Path.cwd()
    path_options = []
    current = current_dir.absolute()
    
    # Add current and all parent paths until root
    while current != current.parent:
        path_options.append({"display": str(current), "path": str(current)})
        current = current.parent
    
    # Add root
    path_options.append({"display": str(current), "path": str(current)})
    
    return jsonify({"paths": path_options})

@app.route('/api/repos')
def get_repos():
    """Get repositories in the specified path."""
    path = request.args.get('path', str(Path.cwd()))
    
    # Find git repositories
    repos = find_git_repos(path)
    
    # Format repos for JSON response
    formatted_repos = []
    for repo in repos:
        formatted_repos.append({
            "name": get_repo_name(repo),
            "path": str(repo)
        })
    
    return jsonify({"repos": formatted_repos})

@app.route('/api/repo-files', methods=['POST'])
def get_repo_files():
    """Get repository files."""
    data = request.json
    repo_path = data.get('repoPath')
    
    if not repo_path:
        return jsonify({"error": "No repository path provided"}), 400
    
    try:
        # Try the new version first (returns a tuple)
        files_with_content, ignored_files = get_relevant_files_with_content(repo_path)
    except ValueError:
        # Fallback for old version (returns just one value)
        files_with_content = get_relevant_files_with_content(repo_path)
        ignored_files = []
    
    # Format response
    included_files = []
    for file_path, content in files_with_content:
        included_files.append({
            "path": str(file_path),
            "content": content
        })
    
    ignored_files_list = [str(f) for f in ignored_files]
    
    return jsonify({
        "included": included_files,
        "ignored": ignored_files_list,
        "includedCount": len(included_files),
        "ignoredCount": len(ignored_files_list)
    })

@app.route('/api/copy-to-clipboard', methods=['POST'])
def copy_repo_content():
    """Copy repository content to clipboard."""
    data = request.json
    repos = data.get('repos', [])
    
    if not repos:
        return jsonify({"error": "No repositories provided"}), 400
    
    # Format content for clipboard
    formatted_content = ""
    
    for repo in repos:
        repo_name = repo.get('name')
        repo_url = repo.get('url', '')  # GitHub repos have URLs, local repos don't
        included_files = repo.get('included', [])
        
        # Add a repository header with separator
        formatted_content += f"\n{'=' * 80}\n"
        if repo_url:
            formatted_content += f"REPOSITORY: {repo_name} ({repo_url})\n"
        else:
            formatted_content += f"REPOSITORY: {repo_name}\n"
        formatted_content += f"{'=' * 80}\n\n"
        
        # Add all files from this repo
        for file in included_files:
            file_path = file.get('path')
            content = file.get('content')
            formatted_content += f"{file_path}:\n{content}\n\n"
    
    # Copy to clipboard
    copy_to_clipboard(formatted_content)
    
    # Show toast notification
    repo_names = ', '.join([repo.get('name') for repo in repos])
    show_toast(f"Repositories copied to clipboard: {repo_names}")
    
    return jsonify({"success": True, "message": f"Copied {len(repos)} repositories to clipboard"})

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    pass

@socketio.on('scan_repos')
def handle_scan_repos(data):
    """Handle repository scanning via WebSockets."""
    path = data.get('path', str(Path.cwd()))
    emit('scan_start', {'path': path})
    
    try:
        # Check if path is valid
        path_obj = Path(path)
        if not path_obj.exists():
            emit('error', {"message": f"Path '{path}' does not exist"})
            return
        
        if not path_obj.is_dir():
            emit('error', {"message": f"Path '{path}' is not a directory"})
            return
            
        # Find git repositories
        repos = find_git_repos(path)
        
        # Format repos for response
        formatted_repos = []
        for repo in repos:
            formatted_repos.append({
                "name": get_repo_name(repo),
                "path": str(repo)
            })
        
        emit('scan_complete', {'repos': formatted_repos})
    except Exception as e:
        emit('error', {"message": f"Error scanning path: {str(e)}"})

@socketio.on('github_clone')
def handle_github_clone(data):
    """Handle GitHub repo cloning via WebSockets."""
    url = data.get('url')
    if not url:
        emit('github_error', {'message': 'No URL provided'})
        return
    
    emit('github_clone_start', {'url': url})
    
    # This would be handled by the actual cloning function
    # For now, we'll just emit an error since we need to implement the full GitHub clone logic
    emit('github_error', {'message': 'GitHub cloning not yet implemented in WebUI'})

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500