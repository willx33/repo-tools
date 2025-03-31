"""WebUI module for repo tools."""

import os
import threading
import webbrowser
import subprocess
import platform
import datetime
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

def start_webui(debug=False, open_browser=True, block=False):
    """
    Start the WebUI server in a background thread.
    
    Args:
        debug: Whether to run the server in debug mode
        open_browser: Whether to open the browser automatically
        block: Whether to block and wait for the server to finish (CLI mode) or 
               return control to the caller (background mode)
    """
    global _webui_thread, _webui_running
    
    if _webui_running:
        console.print("[yellow]WebUI is already running![/yellow]")
        return
    
    def run_server():
        console.print(f"[green]Starting WebUI at http://{_webui_host}:{_webui_port}/[/green]")
        socketio.run(app, host=_webui_host, port=_webui_port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)
    
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
            while _webui_running and _webui_thread.is_alive():
                _webui_thread.join(1)  # Check status every second
        except KeyboardInterrupt:
            console.print("[yellow]WebUI interrupted. Shutting down...[/yellow]")
            stop_webui()

def stop_webui():
    """Stop the WebUI server."""
    global _webui_running
    
    if not _webui_running:
        return
    
    console.print("[yellow]Shutting down WebUI...[/yellow]")
    
    # This is handled via daemon thread, which will exit when main program exits
    _webui_running = False

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

# Add context processor to include current year in templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.now().year}

# Import routes after defining app and socketio to avoid circular imports
from repo_tools.webui import routes