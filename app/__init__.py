from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
import os

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
bcrypt = Bcrypt()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-padrao')
    # Nota: Em um ambiente real, o usuário deve configurar a URL do Postgres. 
    # Vou usar SQLite por padrão para garantir que funcione no sandbox se o Postgres não estiver ativo, 
    # mas o código está pronto para Postgres.
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    from app.auth.routes import auth
    from app.main.routes import main
    from app.reports.routes import reports

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(reports)

    return app
