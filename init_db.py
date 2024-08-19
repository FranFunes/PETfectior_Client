from app_pkg import application, db
from app_pkg.db_models import User, Study, Series
from app_pkg.functions.task_actions import clear_database
import os

with application.app_context():
    u = User.query.first()
    if not u:     
        u =  User(username = 'petfectior', password = 'petfectior')
        db.session.add(u)
    db.session.commit()

    # Delete empty studies and series
    clear_database()

    # Initialize stored_in attribute (for database back-compatibility)
    for st in Study.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(os.path.dirname(st.instances.first().filename))

    for st in Series.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(st.instances.first().filename)
    