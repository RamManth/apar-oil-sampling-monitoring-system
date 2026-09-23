import os
import sys

# Add the root directory to Python's module search path so we can import app.py correctly on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        headers = {k: v for k, v in environ.items() if k.startswith('HTTP_')}
        print(f"[VERCEL WSGI] PATH_INFO={environ.get('PATH_INFO')}, REQUEST_URI={environ.get('REQUEST_URI')}, RAW_URI={environ.get('RAW_URI')}")
        print(f"[VERCEL HEADERS] {headers}")
        matched_path = environ.get('HTTP_X_MATCHED_PATH')
        if matched_path:
            environ['PATH_INFO'] = matched_path
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)


