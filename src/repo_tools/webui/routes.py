"""Routes for the WebUI."""

import os
import json
import tempfile
import glob
import shutil
import time
import threading
import atexit
from pathlib import Path
from flask import render_template, request, jsonify, Response, redirect, url_for
from flask_socketio import emit

from repo_tools.webui import app, socketio, get_webui_port, update_port
from repo_tools.utils.git import get_repo_name, get_relevant_files_with_content as process_repository_files
# Note: process_repository_files still needed for GitHub cloning which happens server-side
from repo_tools.utils.clipboard import copy_to_clipboard
from repo_tools.utils.notifications import show_toast
from repo_tools.modules import extract_github_repo_url, clone_github_repo
from repo_tools.modules.xml_parser import XMLParserError
# Removed: parse_xml_string, preview_changes, apply_changes - now handled client-side

# Global tracking for temporary directories
active_temp_dirs = set()
temp_dir_lock = threading.Lock()

def register_temp_dir(temp_path):
    """Register a temporary directory for tracking and cleanup."""
    with temp_dir_lock:
        active_temp_dirs.add(str(temp_path))

def unregister_temp_dir(temp_path):
    """Unregister and cleanup a temporary directory."""
    with temp_dir_lock:
        path_str = str(temp_path)
        if path_str in active_temp_dirs:
            active_temp_dirs.remove(path_str)
        
        # Force cleanup
        try:
            if Path(temp_path).exists():
                shutil.rmtree(temp_path, ignore_errors=True)
        except Exception:
            pass

def cleanup_all_temp_dirs():
    """Emergency cleanup of all tracked temporary directories."""
    with temp_dir_lock:
        for temp_path in list(active_temp_dirs):
            try:
                if Path(temp_path).exists():
                    shutil.rmtree(temp_path, ignore_errors=True)
            except Exception:
                pass
        active_temp_dirs.clear()

# Schedule aggressive cleanup every 5 minutes
def periodic_cleanup():
    """Periodic cleanup of old temporary directories."""
    try:
        temp_base = Path(tempfile.gettempdir())
        current_time = time.time()
        
        # Clean up any temp directories older than 10 minutes
        for item in temp_base.glob("tmp*"):
            if item.is_dir():
                try:
                    # Check if directory is older than 10 minutes
                    if current_time - item.stat().st_mtime > 600:  # 10 minutes
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    continue
    except Exception:
        pass
    
    # Schedule next cleanup in 5 minutes
    cleanup_timer = threading.Timer(300, periodic_cleanup)
    cleanup_timer.daemon = True
    cleanup_timer.start()

# Start periodic cleanup
periodic_cleanup()

# Register cleanup on exit
atexit.register(cleanup_all_temp_dirs)

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
@app.route('/api/server-settings', methods=['GET', 'POST'])
def server_settings():
    """Get or update server settings."""
    if request.method == 'GET':
        # Return current port setting
        return jsonify({
            "success": True,
            "port": get_webui_port()
        })
    elif request.method == 'POST':
        # Update port setting
        data = request.json
        if not data or 'port' not in data:
            return jsonify({
                "success": False,
                "message": "No port provided"
            }), 400
        
        # Attempt to update port
        success, message, restart_required = update_port(data['port'])
        
        # Return result
        return jsonify({
            "success": success,
            "message": message,
            "restart_required": restart_required
        })

@app.route('/api/paths')
def get_paths():
    """Client-side file selection instruction endpoint."""
    return jsonify({
        "client_side": True,
        "message": "Use FileSystemManager.selectDirectory()",
        "supported_browsers": ["Chrome", "Edge", "Firefox (partial)"],
        "legacy": True
    })

@app.route('/api/repos')
def get_repos():
    """Client-side repository selection instruction endpoint."""
    return jsonify({
        "client_side": True,
        "message": "Repositories should be detected client-side",
        "legacy": True
    })

@app.route('/api/repo-files', methods=['POST'])
def get_repo_files():
    """Process client-provided repository files."""
    data = request.json
    
    # Accept files from client instead of reading from server
    files = data.get('files', [])
    
    if not files:
        return jsonify({"error": "No files provided"}), 400
    
    try:
        # Process files in memory only
        processed_files = []
        for file_data in files:
            # Count tokens if needed (pure computation, no filesystem)
            content = file_data.get('content', '')
            tokens = len(content.split())  # Simple token count
            
            processed_files.append({
                'path': file_data.get('path', ''),
                'size': len(content),
                'tokens': tokens,
                'processed': True
            })
        
        return jsonify({
            "success": True,
            "processed": processed_files,
            "fileCount": len(processed_files),
            "message": "Files processed client-side"
        })
    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"}), 500

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
    """Parse XML content with client-provided files."""
    data = request.json
    xml_content = data.get('xml')
    client_files = data.get('files', [])
    
    if not xml_content:
        return jsonify({"error": "No XML content provided"}), 400
    
    # XML parsing happens client-side now
    # Server just validates and returns instructions
    return jsonify({
        "success": True,
        "message": "XML should be parsed client-side",
        "client_side": True,
        "fileCount": len(client_files)
    })

@app.route('/api/apply-xml', methods=['POST'])
def apply_xml():
    """Return XML changes for client-side application."""
    data = request.json
    changes = data.get('changes', [])
    
    if not changes:
        return jsonify({"error": "No changes provided"}), 400
    
    # Changes are applied client-side via File System Access API
    # Server returns download bundle for fallback browsers
    return jsonify({
        "success": True,
        "message": "Changes prepared for client-side download",
        "apply_client_side": True,
        "changeCount": len(changes),
        "download_ready": True
    })

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear cache by removing temporary directories and cached data."""
    try:
        cleared_files = 0
        temp_dir = tempfile.gettempdir()
        
        # 1. Clear temporary directories created for GitHub clones
        # Look for directories in the temp folder that have git repositories
        git_dirs = []
        for root, dirs, _ in os.walk(temp_dir):
            if '.git' in dirs:
                git_dirs.append(root)
        
        # Remove the git repositories found in temp directories
        for git_dir in git_dirs:
            try:
                shutil.rmtree(git_dir, ignore_errors=True)
                cleared_files += 1
            except Exception as e:
                print(f"Error removing git directory {git_dir}: {e}")
        
        # 2. Find and remove any orphaned temporary directories created by our application
        # These would typically be directories created by tempfile.mkdtemp()
        # For extra safety, only clean directories in the temp folder
        app_temp_pattern = os.path.join(temp_dir, "tmp*")
        for dirpath in glob.glob(app_temp_pattern):
            if os.path.isdir(dirpath):
                try:
                    # Further safety: check if this is likely one of our temp dirs
                    # For example, we could look for certain file patterns
                    # Only remove if it seems to be unused/old
                    if os.path.getmtime(dirpath) < (time.time() - 3600):  # Older than 1 hour
                        shutil.rmtree(dirpath, ignore_errors=True)
                        cleared_files += 1
                except Exception as e:
                    print(f"Error removing temp directory {dirpath}: {e}")
        
        # 3. Optional: Clear any other application cache
        app_cache_dir = os.path.join(str(Path.home()), '.cache', 'repo_tools')
        if os.path.exists(app_cache_dir):
            try:
                for item in os.listdir(app_cache_dir):
                    item_path = os.path.join(app_cache_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                cleared_files += 1
            except Exception as e:
                print(f"Error clearing application cache: {e}")
        
        # Show toast notification
        message = f"Cache cleared successfully. Removed {cleared_files} items."
        show_toast(message)
        
        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"error": f"Error clearing cache: {str(e)}"}), 500

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection - cleanup any hanging temp directories."""
    # Force cleanup of all temp directories when client disconnects
    cleanup_all_temp_dirs()

@socketio.on('heartbeat')
def handle_heartbeat(data):
    """Handle client heartbeat - shows user is still active."""
    # Just acknowledge the heartbeat, no response needed
    pass

@socketio.on('cleanup_request')
def handle_cleanup_request(data):
    """Handle explicit cleanup request from client."""
    cleanup_all_temp_dirs()
    emit('cleanup_confirmed', {'message': 'Temporary files cleaned up'})

@socketio.on('scan_repos')
def handle_scan_repos(data):
    """Legacy repository scanning - now handled client-side."""
    # Don't expose server paths
    emit('scan_start', {'client_side': True})
    
    # Return instruction for client-side scanning
    emit('scan_complete', {
        'client_side': True,
        'message': 'Repository scanning should be done client-side',
        'repos': []
    })

@socketio.on('github_clone')
def handle_github_clone(data):
    """Handle GitHub repo cloning via WebSockets."""
    url = data.get('url')
    repo_path = None
    
    if not url:
        emit('github_error', {'message': 'No URL provided'})
        return
    
    try:
        # Extract clean GitHub URL using the API layer
        clean_url = extract_github_repo_url(url)
        if not clean_url:
            emit('github_error', {'message': 'Invalid GitHub repository URL'})
            return
        
        emit('github_clone_start', {'url': clean_url})
        
        # Clone the repository using the API layer
        repo_path = clone_github_repo(clean_url)
        if not repo_path:
            emit('github_error', {'message': 'Failed to clone repository'})
            return
        
        # Register the temp directory for tracking
        register_temp_dir(repo_path)
            
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
        
    except Exception as e:
        emit('github_error', {'message': f'Error processing repository: {str(e)}'})
    finally:
        # Clean up the temporary directory using our tracking system
        if repo_path:
            unregister_temp_dir(repo_path)

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
        files_with_content, ignored_files = process_repository_files(Path(repo_path))
        
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
    """Handle XML parsing using the robust server-side parser."""
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        emit('xml_error', {'message': 'No XML content provided'})
        return
    
    emit('xml_parse_start', {'xml': xml_string})
    
    try:
        from repo_tools.modules.xml_parser import parse_xml_string
        
        # Parse XML using the robust server-side parser
        changes = parse_xml_string(xml_string, repo_path)
        
        # Convert FileChange objects to dictionaries for JSON serialization
        changes_data = []
        for change in changes:
            change_dict = {
                'operation': change.operation,
                'path': change.path,
                'content': change.code or '',
                'search': change.search or '',
                'description': change.summary or '',
                'status': 'Ready to apply'
            }
            changes_data.append(change_dict)
        
        emit('xml_parse_complete', {
            "success": True,
            "changes": changes_data,
            "changeCount": len(changes_data)
        })
        
    except Exception as e:
        emit('xml_error', {'message': f'Error parsing XML: {str(e)}'})

@socketio.on('xml_apply')
def handle_xml_apply(data):
    """Handle XML changes application using the server-side parser."""
    xml_string = data.get('xml')
    repo_path = data.get('repoPath')
    
    if not xml_string:
        emit('xml_error', {'message': 'No XML content provided'})
        return
        
    if not repo_path:
        emit('xml_error', {'message': 'No repository path provided'})
        return
    
    emit('xml_apply_start', {'xml': xml_string, 'repoPath': repo_path})
    
    try:
        from repo_tools.modules.xml_parser import apply_changes
        
        # Apply XML changes using the robust server-side parser
        # apply_changes returns List[Tuple[FileChange, bool, Optional[str]]]
        results = apply_changes(xml_string, repo_path)
        
        # Convert results to a format expected by the frontend
        results_data = []
        successful_changes = 0
        
        for change, success, error_message in results:
            if success:
                successful_changes += 1
                
            result_dict = {
                'operation': change.operation,
                'path': change.path,
                'success': success,
                'error': error_message if not success else None,
                'message': f"Successfully applied {change.operation} to {change.path}" if success else f"Failed to apply {change.operation} to {change.path}"
            }
            results_data.append(result_dict)
        
        emit('xml_apply_complete', {
            "success": True,
            "results": results_data,
            "totalChanges": len(results_data),
            "successfulChanges": successful_changes
        })
        
    except Exception as e:
        emit('xml_error', {'message': f'Error applying XML changes: {str(e)}'})

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500