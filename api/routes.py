"""api/routes.py — Register all API blueprints on the Flask app."""

from api.sensors    import bp as sensors_bp
from api.weather    import bp as weather_bp
from api.irrigation import bp as irrigation_bp
from api.predict    import bp as predict_bp
from api.system     import bp as system_bp
from api.chat       import bp as chat_bp
from api.auth       import bp as auth_bp


def register_routes(app):
    app.register_blueprint(sensors_bp,    url_prefix="/api")
    app.register_blueprint(weather_bp,    url_prefix="/api/weather")
    app.register_blueprint(irrigation_bp, url_prefix="/api/irrigation")
    app.register_blueprint(predict_bp,    url_prefix="/api/predict")
    app.register_blueprint(system_bp,     url_prefix="/api")
    app.register_blueprint(chat_bp,       url_prefix="/api")
    app.register_blueprint(auth_bp,       url_prefix="/api")
