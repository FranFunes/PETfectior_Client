import os
basedir = os.path.abspath(os.path.dirname(__file__))

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
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True