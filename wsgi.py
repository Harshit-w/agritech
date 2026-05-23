"""
wsgi.py — Production WSGI entry point.

Usage with Gunicorn:
    gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 wsgi:application

Usage with uWSGI:
    uwsgi --http 0.0.0.0:5000 --module wsgi:application --processes 4
"""

from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run()
