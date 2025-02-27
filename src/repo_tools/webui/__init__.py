"""WebUI module for repo tools."""

import os
import threading
import webbrowser
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
webui_thread = None
webui_running = False

def start_webui(debug=False, open_browser=True):
    """Start the WebUI server in a background thread."""
    global webui_thread, webui_running
    
    if webui_running:
        console.print("[yellow]WebUI is already running![/yellow]")
        return
    
    def run_server():
        host = '127.0.0.1'
        port = 5000
        
        console.print(f"[green]Starting WebUI at http://{host}:{port}/[/green]")
        socketio.run(app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)
    
    # Start the server in a daemon thread
    webui_thread = threading.Thread(target=run_server)
    webui_thread.daemon = True  # This ensures the thread will exit when the main program exits
    webui_thread.start()
    webui_running = True
    
    # Open browser automatically if requested
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:5000/")

def stop_webui():
    """Stop the WebUI server."""
    global webui_running
    
    if not webui_running:
        console.print("[yellow]WebUI is not running![/yellow]")
        return
    
    console.print("[yellow]Shutting down WebUI...[/yellow]")
    
    # This is handled via daemon thread, which will exit when main program exits
    webui_running = False

# Add context processor to include current year in templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.now().year}

# Import routes after defining app and socketio to avoid circular imports
from repo_tools.webui import routes