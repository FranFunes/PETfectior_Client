# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import os
from app_pkg import application, db
from app_pkg.db_models import User, Study, Series, Radiopharmaceutical, FilterSettings, AppConfig
from app_pkg.functions.task_actions import clear_database

with application.app_context():
    u = User.query.first()
    if not u:     
        u =  User(username = 'petfectior', password = 'petfectior')
        db.session.add(u)

    c = AppConfig.query.first()
    if c:
        # Patch server url to use the URL instead of a fixed IP address.
        c.server_url = os.getenv('SERVER_ADDRESS') + ':' + os.getenv('SERVER_PORT')
        
    rf = Radiopharmaceutical.query.first()
    if not rf:
        rf = Radiopharmaceutical(name = 'FDG', synonyms = 'FDG, fluorodeoxyglucose', half_life = 109.8)
        db.session.add(rf)

    for fs in FilterSettings.query.filter_by(radiopharmaceutical = None):
        fs.radiopharmaceutical = 'all'
    
    for fs in FilterSettings.query.filter_by(model = None):
        fs.model = 'all'
        
    db.session.commit()

    # Delete empty studies and series
    clear_database()

    # Initialize stored_in attribute (for database back-compatibility)
    for st in Study.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(os.path.dirname(st.instances.first().filename))

    for st in Series.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(st.instances.first().filename)
    