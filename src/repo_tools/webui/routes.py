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
from repo_tools.modules import process_xml_changes, preview_xml_changes, XMLParserError

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

@app.route('/xml-parser')
def xml_parser():
    """Render the XML parser page."""
    return render_template('xml_parser.html')
    
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
    
    # Handle direct text content
    if 'text' in data:
        formatted_content = data['text']
        copy_to_clipboard(formatted_content)
        return jsonify({
            "success": True, 
            "message": "Content copied to clipboard"
        })
    
    # Handle repository content
    selected_repos = data.get('selectedRepos', [])
    
    if selected_repos:
        # Format content for clipboard
        formatted_content = ""
        
        # Add file tree structure
        formatted_content += "FILE TREE STRUCTURE:\n"
        formatted_content += "=" * 80 + "\n\n"
        
        total_files = 0
        
        for repo in selected_repos:
            # Get the tree data which includes selection state
            tree_data = repo.get('treeData', {})
            if not tree_data:
                continue
                
            # Count selected files
            selected_files = sum(1 for f in repo['files'] if f.get('selected', True))
            total_files += selected_files
            
            # Add repository name as root with total file count
            formatted_content += f"{repo['name']}\n"
            formatted_content += f"{selected_files} files\n\n"
            
            # Build tree structure recursively
            def build_tree(node, prefix='', is_last=False):
                nonlocal formatted_content
                
                if not node:
                    return
                
                # Skip if this node is completely deselected (not selected and not indeterminate)
                if not node.get('selected', True) and not node.get('indeterminate', False):
                    return
                
                # For directories
                if node.get('type') == 'directory':
                    # Add directory entry (without file count)
                    formatted_content += f"{prefix}{'└── ' if is_last else '├── '}{node['name']}\n"
                    
                    # Process children
                    if node.get('children'):
                        children = sorted(
                            node['children'].values(),
                            key=lambda x: (x.get('type') != 'directory', x.get('name', ''))
                        )
                        
                        for i, child in enumerate(children):
                            is_last_child = i == len(children) - 1
                            build_tree(
                                child,
                                prefix + ('    ' if is_last else '│   '),
                                is_last_child
                            )
                
                # For files
                elif node.get('type') == 'file' and node.get('selected', True):
                    formatted_content += f"{prefix}{'└── ' if is_last else '├── '}{node['name']}\n"
            
            # Start building tree from root's children
            if tree_data.get('children'):
                children = sorted(
                    tree_data['children'].values(),
                    key=lambda x: (x.get('type') != 'directory', x.get('name', ''))
                )
                
                for i, child in enumerate(children):
                    build_tree(child, '', i == len(children) - 1)
            
            formatted_content += "\n"
        
        formatted_content += "=" * 80 + "\n\n"
        
        # Add file contents
        for repo in selected_repos:
            formatted_content += f"REPOSITORY: {repo['name']}\n"
            formatted_content += "=" * 80 + "\n\n"
            
            for file in repo['files']:
                if file.get('selected', True):  # Only include selected files
                    formatted_content += f"{file['path']}:\n{file.get('content', '')}\n\n"
        
        # Copy to clipboard
        copy_to_clipboard(formatted_content)
        
        return jsonify({
            "success": True, 
            "message": f"Copied {total_files} files from {len(selected_repos)} repositories to clipboard"
        })
    
    return jsonify({"error": "No content provided"}), 400

def format_token_count(count):
    """Format token count with K/M suffix."""
    if count < 1000:
        return str(count)
    elif count < 1000000:
        return f"{count/1000:.1f}k"
    else:
        return f"{count/1000000:.1f}M"

def get_file_icon(extension):
    """Get appropriate icon for file type."""
    icon_map = {
        'py': '🐍',
        'md': '📝',
        'txt': '📝',
        'json': '⚙️',
        'yml': '⚙️',
        'yaml': '⚙️',
        'toml': '⚙️',
        'html': '📄',
        'css': '📄',
        'js': '📄',
        'jsx': '📄',
        'ts': '📄',
        'tsx': '📄',
    }
    return icon_map.get(extension.lower(), '📄')

@app.route('/api/copy-file-to-clipboard', methods=['POST'])
def copy_file_content():
    """Copy a single file's content to clipboard."""
    data = request.json
    file_path = data.get('filePath')
    file_content = data.get('fileContent')
    repo_name = data.get('repoName', '')
    
    if not file_path or not file_content:
        return jsonify({"error": "File path or content not provided"}), 400
    
    # Format content for clipboard
    formatted_content = ""
    if repo_name:
        formatted_content += f"REPOSITORY: {repo_name}\n"
        formatted_content += f"{'=' * 80}\n\n"
    
    formatted_content += f"{file_path}:\n{file_content}\n"
    
    # Copy to clipboard
    copy_to_clipboard(formatted_content)
    
    # Show toast notification
    show_toast(f"File copied to clipboard: {os.path.basename(file_path)}")
    
    return jsonify({"success": True, "message": f"Copied {file_path} to clipboard"})

@app.route('/api/parse-xml', methods=['POST'])
def parse_xml():
    """Parse XML and return preview of changes."""
    data = request.json
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        return jsonify({"error": "No XML content provided"}), 400
    
    if not repo_path:
        return jsonify({"error": "No repository path provided"}), 400
    
    try:
        # Generate preview of changes
        previews = preview_xml_changes(xml_string, repo_path)
        
        return jsonify({
            "success": True,
            "changes": previews,
            "changeCount": len(previews)
        })
    
    except XMLParserError as e:
        return jsonify({"error": f"XML parsing error: {str(e)}"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Error previewing changes: {str(e)}"}), 500

@app.route('/api/apply-xml', methods=['POST'])
def apply_xml():
    """Apply XML changes to a repository."""
    data = request.json
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        return jsonify({"error": "No XML content provided"}), 400
    
    if not repo_path:
        return jsonify({"error": "No repository path provided"}), 400
    
    try:
        # Apply changes and get results
        results = process_xml_changes(xml_string, repo_path)
        
        # Format results for response
        formatted_results = []
        successful_changes = 0
        
        for change, success, error_message in results:
            result = {
                "operation": change.operation,
                "path": change.path,
                "success": success
            }
            
            if error_message:
                result["error"] = error_message
            
            if success:
                successful_changes += 1
            
            formatted_results.append(result)
        
        # Show toast notification
        show_toast(f"Applied {successful_changes} of {len(results)} changes to repository")
        
        return jsonify({
            "success": True,
            "results": formatted_results,
            "totalChanges": len(results),
            "successfulChanges": successful_changes
        })
    
    except XMLParserError as e:
        return jsonify({"error": f"XML parsing error: {str(e)}"}), 400
    
    except Exception as e:
        return jsonify({"error": f"Error applying changes: {str(e)}"}), 500

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

@socketio.on('github_scan')
def handle_github_scan(data):
    """Handle GitHub repo scanning via WebSockets."""
    repo_path = data.get('repoPath')
    if not repo_path:
        emit('github_error', {'message': 'No repository path provided'})
        return
    
    emit('github_scan_start', {'path': repo_path})
    
    try:
        # Process repository files using the API layer
        files_with_content, ignored_files = process_repository_files(repo_path)
        
        # Format response
        included_files = []
        for file_path, content in files_with_content:
            included_files.append({
                "path": str(file_path),
                "content": content
            })
        
        ignored_files_list = [str(f) for f in ignored_files]
        
        emit('github_scan_complete', {
            "included": included_files,
            "ignored": ignored_files_list,
            "includedCount": len(included_files),
            "ignoredCount": len(ignored_files_list)
        })
    except Exception as e:
        emit('github_error', {'message': f"Error scanning repository: {str(e)}"})

@socketio.on('xml_parse')
def handle_xml_parse(data):
    """Handle XML parsing via WebSockets."""
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        emit('xml_error', {'message': 'No XML content provided'})
        return
    
    if not repo_path:
        emit('xml_error', {'message': 'No repository path provided'})
        return
    
    emit('xml_parse_start', {'repoPath': repo_path})
    
    try:
        # Generate preview of changes
        previews = preview_xml_changes(xml_string, repo_path)
        
        emit('xml_parse_complete', {
            "success": True,
            "changes": previews,
            "changeCount": len(previews)
        })
    
    except XMLParserError as e:
        emit('xml_error', {'message': f"XML parsing error: {str(e)}"})
    
    except Exception as e:
        emit('xml_error', {'message': f"Error previewing changes: {str(e)}"})

@socketio.on('xml_apply')
def handle_xml_apply(data):
    """Handle applying XML changes via WebSockets."""
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        emit('xml_error', {'message': 'No XML content provided'})
        return
    
    if not repo_path:
        emit('xml_error', {'message': 'No repository path provided'})
        return
    
    emit('xml_apply_start', {'repoPath': repo_path})
    
    try:
        # Apply changes and get results
        results = process_xml_changes(xml_string, repo_path)
        
        # Format results for response
        formatted_results = []
        successful_changes = 0
        
        for change, success, error_message in results:
            result = {
                "operation": change.operation,
                "path": change.path,
                "success": success
            }
            
            if error_message:
                result["error"] = error_message
            
            if success:
                successful_changes += 1
            
            formatted_results.append(result)
        
        # Show toast notification
        show_toast(f"Applied {successful_changes} of {len(results)} changes to repository")
        
        emit('xml_apply_complete', {
            "success": True,
            "results": formatted_results,
            "totalChanges": len(results),
            "successfulChanges": successful_changes
        })
    
    except XMLParserError as e:
        emit('xml_error', {'message': f"XML parsing error: {str(e)}"})
    
    except Exception as e:
        emit('xml_error', {'message': f"Error applying changes: {str(e)}"})

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500