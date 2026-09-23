import os
import sys
from urllib.parse import parse_qs, urlencode

# Add the root directory to Python's module search path so we can import app.py correctly on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelQueryPathMiddleware:
    """Extracts original route path passed via __path query parameter on Vercel."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        if '__path=' in qs:
            params = parse_qs(qs, keep_blank_values=True)
            if '__path' in params and params['__path']:
                target_path = params.pop('__path')[0]
                if not target_path.startswith('/'):
                    target_path = '/' + target_path
                environ['PATH_INFO'] = target_path
                environ['QUERY_STRING'] = urlencode(params, doseq=True)
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelQueryPathMiddleware(app.wsgi_app)


