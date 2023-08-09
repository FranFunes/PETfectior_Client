import queue, logging, json, os, requests, threading

from sqlalchemy.exc import OperationalError

from app_pkg import application, db
from app_pkg.db_models import Device

from services.loggers import app_logger, dicom_logger
from services.store_scp import StoreSCP
from services.db_store_handler import db_store_handler
from services.compilator import Compilator

from services.task_manager import TaskManager

# Setup logging
app_logger()
dicom_logger()
logger = logging.getLogger('__main__')

# Initialize queues for different processes
queue_scp = queue.Queue()
download_queue = queue.Queue()

# Task Manager
task_manager = TaskManager()

# DICOM Store SCP    
store_scp = StoreSCP(scp_queue = queue_scp, c_store_handler=db_store_handler)

# Compilator       
server_url = os.environ["SERVER_URL"]
compilator = Compilator(queue_scp, task_manager, server_url)

# Initialize services
services = {'Dicom Listener': store_scp}

# Get SCP AET and port from database or initialize it if not available
aet = os.environ.get('DEFAULT_STORE_SCP_AET','PETFECTIOR')
port = int(os.environ.get('DEFAULT_STORE_SCP_PORT', 11113))

with application.app_context():
    try:
        d = Device.query.get('__local_store_SCP__')                
        assert d
        logger.info('local device found in the database')
        aet = d.ae_title
        port = d.port
    except AssertionError:        
        logger.info('database is available but local device not found.')
        logger.info('creating local device with default settings.')
        d = Device(name = '__local_store_SCP__',
                ae_title = aet,
                address = '0.0.0.0',
                port = port)
        db.session.add(d)
        db.session.commit()
    except OperationalError as e:       
        logger.info('database is not available.')
        logger.info({repr(e)})
        logger.info('creating local device with default settings.') 

# Start services
for name, service in services.items():
    try:
        if name == 'Dicom Listener':
            service.start(aet, port)
        else:
            service.start()
    except Exception as e:
        logger.error(f"failed when starting {name}")
        logger.error(repr(e))

# Get the SHARED_PATH variable from the server, if available (in a separate thread):
def get_shared_path(server_url):
    try:
        get_rsp = requests.get('http://' + server_url + '/get_shared_path')    
        os.environ["SHARED_PATH"] = get_rsp.json()['path']
    except:
        os.environ["SHARED_PATH"] = "//10.87.141.15/Proyectos/PETfectior"
        
if os.environ["SERVER_INTERACTION"] == "True":

    shared_path_thread = threading.Thread(target = get_shared_path, 
                                                args = (server_url,), name = 'get_shared_path')        
    shared_path_thread.start()
