"""Routes for the WebUI."""

import os
import json
from pathlib import Path
from flask import render_template, request, jsonify
from flask_socketio import emit

from repo_tools.webui import app, socketio
from repo_tools.utils.git import find_git_repos, get_repo_name
from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast
from repo_tools.modules import process_repository_files, extract_github_repo_url, clone_github_repo

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
    
    # Set default to parent directory if available (one directory back)
    default_path = str(current_dir.parent) if current_dir.parent != current_dir else str(current_dir)
    
    return jsonify({
        "paths": path_options,
        "default": default_path
    })

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
        # Use the API layer to process repository files
        files_with_content, ignored_files = process_repository_files(repo_path)
        
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    
    # Extract clean GitHub URL using the API layer
    clean_url = extract_github_repo_url(url)
    if not clean_url:
        emit('github_error', {'message': 'Invalid GitHub repository URL'})
        return
    
    emit('github_clone_start', {'url': clean_url})
    
    try:
        # Clone the repository using the API layer
        repo_path = clone_github_repo(clean_url)
        if not repo_path:
            emit('github_error', {'message': 'Failed to clone repository'})
            return
            
        # Get repository name from URL
        repo_name = clean_url.split('/')[-1]
        
        # Get all relevant files with content using the API layer
        files_with_content, ignored_files = process_repository_files(repo_path)
        
        # Format files for the frontend
        included_files = []
        for file_path, content in files_with_content:
            included_files.append({
                "path": str(file_path),
                "content": content
            })
        
        ignored_files_list = [str(f) for f in ignored_files]
        
        # Return the results
        emit('github_clone_complete', {
            'name': repo_name,
            'url': clean_url,
            'included': included_files,
            'ignored': ignored_files_list,
            'includedCount': len(included_files),
            'ignoredCount': len(ignored_files_list)
        })
        
        # Clean up the temporary directory
        import subprocess
        subprocess.run(["rm", "-rf", str(repo_path)], check=False)
        
    except Exception as e:
        emit('github_error', {'message': f'Error processing repository: {str(e)}'})
        return

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500