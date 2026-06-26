import os
import subprocess
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = 8000
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Set workspace root as directory for serving files
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

    def do_POST(self):
        if self.path == '/api/update':
            print("Received update request from UI. Running update_feed.py...")
            try:
                script_path = os.path.join(WORKSPACE_DIR, 'scripts', 'update_feed.py')
                # Run the update_feed script under python
                result = subprocess.run(['python', script_path], capture_output=True, text=True, check=True)
                
                print("Update script completed successfully.")
                print(result.stdout)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response_data = {
                    "status": "success",
                    "message": "Database updated successfully.",
                    "output": result.stdout
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except subprocess.CalledProcessError as e:
                print(f"Error executing update script: {e.stderr or e.stdout}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response_data = {
                    "status": "error",
                    "message": "Failed to update database.",
                    "error": e.stderr or e.stdout
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e:
                print(f"Server error: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def end_headers(self):
        # Inject CORS header to prevent any browser blocks
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, CustomHTTPRequestHandler)
    print(f"Starting custom PsychNews API server on http://localhost:{PORT} ...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
