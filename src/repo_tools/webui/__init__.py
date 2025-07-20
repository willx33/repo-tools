"""WebUI module for repo tools."""

import os
import threading
import webbrowser
import subprocess
import platform
import datetime
import json
import time
import signal
from flask import Flask, render_template
from flask_socketio import SocketIO
from pathlib import Path
from rich.console import Console

console = Console()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Global variables to track WebUI state
_webui_thread = None
_webui_running = False
_webui_host = '127.0.0.1'
_webui_port = 5000
_restart_requested = False
_restart_lock = threading.Lock()

# Settings file path
_settings_dir = os.path.join(os.path.expanduser('~'), '.repo_tools')
_settings_file = os.path.join(_settings_dir, 'settings.json')

def _ensure_settings_dir():
    """Ensure settings directory exists."""
    if not os.path.exists(_settings_dir):
        os.makedirs(_settings_dir, exist_ok=True)

def load_settings():
    """Load settings from disk."""
    global _webui_port
    
    _ensure_settings_dir()
    
    # Load settings if file exists
    if os.path.exists(_settings_file):
        try:
            with open(_settings_file, 'r') as f:
                settings = json.load(f)
                
            # Update port from settings if available
            if 'port' in settings:
                port = int(settings['port'])
                # Validate port is in valid range
                if 1024 <= port <= 65535:
                    _webui_port = port
        except (json.JSONDecodeError, ValueError, IOError) as e:
            console.print(f"[yellow]Error loading settings: {e}[/yellow]")

def save_settings(settings=None):
    """Save settings to disk.
    
    Args:
        settings: Optional dictionary of settings to save. If None, only saves current port.
    """
    _ensure_settings_dir()
    
    # Load existing settings if available
    current_settings = {}
    if os.path.exists(_settings_file):
        try:
            with open(_settings_file, 'r') as f:
                current_settings = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # Start with empty settings if file can't be loaded
    
    # Update with provided settings or just port
    if settings:
        current_settings.update(settings)
    else:
        current_settings['port'] = _webui_port
    
    # Save settings
    try:
        with open(_settings_file, 'w') as f:
            json.dump(current_settings, f, indent=2)
    except IOError as e:
        console.print(f"[yellow]Error saving settings: {e}[/yellow]")

def is_running_in_wsl():
    """Check if we're running in Windows Subsystem for Linux."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False

def open_url_in_browser(url):
    """
    Open URL in browser, with special handling for WSL.
    
    Args:
        url: The URL to open
    
    Returns:
        bool: True if successful, False otherwise
    """
    if is_running_in_wsl():
        try:
            # Try to use Windows browser through powershell
            subprocess.run([
                "powershell.exe", 
                "-Command", 
                f"Start-Process '{url}'"
            ], check=False)
            return True
        except Exception as e:
            console.print(f"[yellow]Could not open browser in WSL: {e}[/yellow]")
            console.print(f"[cyan]Please manually open {url} in your browser[/cyan]")
            return False
    else:
        # Regular browser opening for non-WSL environments
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            console.print(f"[yellow]Could not open browser: {e}[/yellow]")
            console.print(f"[cyan]Please manually open {url} in your browser[/cyan]")
            return False

def start_webui(debug=False, open_browser=True, block=False, host=None, port=None):
    """
    Start the WebUI server in a background thread.
    
    Args:
        debug: Whether to run the server in debug mode
        open_browser: Whether to open the browser automatically
        block: Whether to block and wait for the server to finish (CLI mode) or 
               return control to the caller (background mode)
        host: Host to bind to (overrides settings)
        port: Port to bind to (overrides settings)
    """
    global _webui_thread, _webui_running, _restart_requested, _webui_host, _webui_port
    
    # Load settings to get port
    load_settings()
    
    # Override with command line args if provided
    if host is not None:
        _webui_host = host
    if port is not None:
        _webui_port = port
    
    if _webui_running:
        console.print("[yellow]WebUI is already running![/yellow]")
        return
    
    def run_server():
        global _webui_running, _restart_requested
        
        console.print(f"[green]Starting WebUI at http://{_webui_host}:{_webui_port}/[/green]")
        socketio.run(app, host=_webui_host, port=_webui_port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)
        
        # Set running flag to False when server stops
        _webui_running = False
        console.print("[yellow]WebUI server has stopped[/yellow]")
        
        # Handle restart if requested
        with _restart_lock:
            if _restart_requested:
                _restart_requested = False
                console.print("[green]Restarting WebUI server...[/green]")
                # Wait a moment for the port to be released
                time.sleep(1)
                # Start the server again in a new thread
                start_webui(debug=debug, open_browser=False, block=block)
    
    # Start the server in a daemon thread
    _webui_thread = threading.Thread(target=run_server)
    _webui_thread.daemon = True  # This ensures the thread will exit when the main program exits
    _webui_thread.start()
    _webui_running = True
    
    # Open browser automatically if requested
    if open_browser:
        webui_url = get_webui_url()
        if webui_url:
            success = open_url_in_browser(webui_url)
            if not success:
                console.print(f"[yellow]Failed to open browser. Please manually navigate to {webui_url}[/yellow]")
        
    # If block is True, wait for the thread to complete (CLI mode)
    if block:
        try:
            # Wait for the thread to complete or until interrupted
            while (_webui_running or _restart_requested) and _webui_thread and _webui_thread.is_alive():
                _webui_thread.join(1)  # Check status every second
        except KeyboardInterrupt:
            console.print("[yellow]WebUI interrupted. Shutting down...[/yellow]")
            stop_webui()

def stop_webui():
    """Stop the WebUI server."""
    global _webui_running, _restart_requested
    
    if not _webui_running:
        return
    
    console.print("[yellow]Shutting down WebUI...[/yellow]")
    
    # Make sure we're not going to restart
    with _restart_lock:
        _restart_requested = False
    
    # This is handled via daemon thread, which will exit when main program exits
    _webui_running = False

def restart_webui():
    """Request a restart of the WebUI server.
    
    Note: Automatic restart may not work reliably in all environments.
    The server will attempt to restart, but manual restart may be required.
    
    Returns:
        bool: True if restart was requested, False if the server is not running
    """
    global _restart_requested
    
    if not is_webui_running():
        return False
    
    # Set restart flag
    with _restart_lock:
        _restart_requested = True
    
    # Trigger the server to stop - it will restart itself due to the restart flag
    stop_webui()
    return True

def update_port(new_port):
    """Update the server port.
    
    The port setting is saved to the settings file for future server starts.
    If the server is currently running, an attempt to restart it will be made,
    but manual restart may be required for the change to take effect.
    
    Args:
        new_port: The new port number
        
    Returns:
        tuple: (success, message, restart_required)
    """
    global _webui_port
    
    # Validate port
    try:
        port = int(new_port)
        if port < 1024 or port > 65535:
            return False, "Port must be between 1024 and 65535", False
    except ValueError:
        return False, "Port must be a valid number", False
    
    # If port is the same, no change needed
    if port == _webui_port:
        return True, "Port unchanged", False
    
    # Update port
    _webui_port = port
    
    # Save to settings file
    save_settings()
    
    # Determine if restart is needed
    restart_needed = is_webui_running()
    
    # If server is running, request restart
    if restart_needed:
        restart_webui()
        
    return True, f"Port updated to {port}. Changes will take effect after restart.", restart_needed

def is_webui_running():
    """Check if the WebUI is currently running.
    
    Returns:
        bool: True if the WebUI is running, False otherwise.
    """
    return _webui_running

def get_webui_url():
    """Get the URL of the running WebUI.
    
    Returns:
        str: The URL of the running WebUI, or None if not running.
    """
    if _webui_running:
        return f"http://{_webui_host}:{_webui_port}/"
    return None

def get_webui_port():
    """Get the current WebUI port.
    
    Returns:
        int: The current WebUI port
    """
    return _webui_port

# Add context processor to include current year in templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.now().year}

# Initialize settings
load_settings()

# Import routes after defining app and socketio to avoid circular imports
from repo_tools.webui import routes