from app_pkg import application, db
from app_pkg.db_models import User

with application.app_context():
    u = User.query.first()
    if not u:     
        u =  User(username = 'petfectior', password = 'petfectior')
        db.session.add(u)

    db.session.commit()
    