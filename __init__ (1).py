from flask import Flask
from extensions import db, migrate, bcrypt, login_manager, jwt
from config import Config


login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        
        from routes import main_bp
        from api_routes import api_bp
        
        
        app.register_blueprint(main_bp)
        app.register_blueprint(api_bp)

        import models

    return app