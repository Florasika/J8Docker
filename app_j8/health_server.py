"""
Serveur HTTP minimal pour les health checks Docker.
Endpoint GET /health → JSON avec statut de la BDD.
"""

import os, json, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from sqlalchemy import create_engine, text

DB_URL = (f"postgresql://{os.getenv('DB_USER','admin')}:"
          f"{os.getenv('DB_PASSWORD','secret123')}@"
          f"{os.getenv('DB_HOST','postgres')}:5432/"
          f"{os.getenv('DB_NAME','ventes_db')}")

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL)
    return _engine


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/health':
            self._health()
        elif self.path == '/metrics':
            self._metrics()
        else:
            self.send_response(404)
            self.end_headers()

    def _health(self):
        try:
            with get_engine().connect() as c:
                c.execute(text("SELECT 1"))
            payload = {'status':'healthy','db':'connected',
                       'timestamp':datetime.now().isoformat()}
            code = 200
        except Exception as e:
            payload = {'status':'unhealthy','error':str(e),
                       'timestamp':datetime.now().isoformat()}
            code = 503

        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(body)

    def _metrics(self):
        try:
            with get_engine().connect() as c:
                row = c.execute(text(
                    "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM ventes"
                )).fetchone()
            payload = {'nb_ventes':row[0],'ca_total':float(row[1]),
                       'timestamp':datetime.now().isoformat()}
        except Exception as e:
            payload = {'error':str(e)}

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Silencer les logs HTTP par défaut


if __name__ == '__main__':
    port   = int(os.getenv('PORT', 8081))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Health server démarré sur :{port}")
    server.serve_forever()
