"""

    Inicialización de la aplicación flask.
    Se importa la configuración de config.Config
    Se inicializa:
     * base de datos (Flask-SQLAlchemy) y gestor de migraciones (Flask-Migrate)
     * gestor de autenticación (Flask-Login)
     * endpoints (al importar routes)
    
    ffunes
    6/9/2024
    

"""

from flask import Flask
from config import Config
from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

application = Flask(__name__)
application.config.from_object(Config)

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(application, metadata=metadata)
migrate = Migrate(application, db)
login = LoginManager(application)
login.login_view = 'login'
login.login_message = "Inicie sesión como administrador para ver esta sección"

from app_pkg import routes
