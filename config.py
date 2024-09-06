"""

    Configuración inicial de la aplicación flask.   
    
    ffunes
    6/9/2024 

"""

import os
basedir = os.path.abspath(os.path.dirname(__file__))

# Use sqlite for development
if os.environ.get('MYSQL_ACTIVE') == 'True':
    print('Using mysql...')
    db_url = "mysql+pymysql://" + os.environ['MYSQL_USER'] + ':'
    db_url += os.environ['MYSQL_PASSWORD'] + '@'
    db_url += os.environ['MYSQL_HOST'] + ':3306/'
    db_url += os.environ['MYSQL_DATABASE']    
else:
    print('Using sqlite...')
    db_url = 'sqlite:///' + os.path.join(basedir, 'app.db')

class Config(object):
    
    """

        Objeto de configuración de Flask, ver:
         * `Flask Configuration Handling <https://flask.palletsprojects.com/en/3.0.x/config/>`_ y
         * `Flask-SQLAlchemy Configuration Handling <https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/>`_).

    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True