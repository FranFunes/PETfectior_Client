from dotenv import load_dotenv
load_dotenv()

import os
from app_pkg import application, db
from app_pkg.db_models import User, Study, Series, Radiopharmaceutical, FilterSettings, AppConfig, Task
from app_pkg.functions.task_actions import clear_database

with application.app_context():
    # Crear el usuario admin si no existe
    u = User.query.first()
    if not u:     
        u =  User(username = 'petfectior', password = 'petfectior')
        db.session.add(u)

    # Resetear URL del server y el puerto Store SCP a sus valores en .env
    c = AppConfig.query.first()
    if c:        
        c.server_url = os.getenv('SERVER_ADDRESS') + ':' + os.getenv('SERVER_PORT')        
        c.store_scp_port = os.getenv('DICOM_LISTENER_PORT')
    
    # Crear al menos un radiofármaco (FDG)
    rf = Radiopharmaceutical.query.first()
    if not rf:
        rf = Radiopharmaceutical(name = 'FDG', synonyms = 'FDG, fluorodeoxyglucose', half_life = 109.8)
        db.session.add(rf)

    # Inicializar el campo radiofármaco para los FilterSettings
    for fs in FilterSettings.query.filter_by(radiopharmaceutical = None):
        fs.radiopharmaceutical = 'all'

    # Inicializar el campo model para los FilterSettings
    for fs in FilterSettings.query.filter_by(model = None):
        fs.model = 'all'

    # Eliminar estudios y series vacíos
    clear_database()

    # Inicializar el atributo stored_in para series y estudios
    for st in Study.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(os.path.dirname(st.instances.first().filename))
    for st in Series.query.filter_by(stored_in = None).all():
        st.stored_in = os.path.dirname(st.instances.first().filename)

    # Inicializar el atributo visible en True para las tareas
    for task in Task.query.filter_by(visible = None).all():
        task.visible = True
    
    db.session.commit()

    # Eliminar estudios y series vacíos
    clear_database()