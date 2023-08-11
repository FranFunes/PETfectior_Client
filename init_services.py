import queue, logging, json, os, requests, threading

from sqlalchemy.exc import OperationalError

from app_pkg import application, db
from app_pkg.db_models import AppConfig, Device

from services.loggers import app_logger, dicom_logger
from services.store_scp import StoreSCP
from services.db_store_handler import db_store_handler
from services.compilator import Compilator
from services.validator import Validator
from services.task_manager import TaskManager

# Disable warnings (only for developing)
import warnings
warnings.filterwarnings("ignore")

# Setup logging
app_logger()
dicom_logger()
logger = logging.getLogger('__main__')

# Initialize queues for different processes
queues = {
    'compilator': queue.Queue(),
    'validator': queue.Queue(),    
}
download_queue = queue.Queue()

# Task manager
task_manager = TaskManager()

# DICOM Store SCP    
store_scp = StoreSCP(input_queue = queues['compilator'], c_store_handler=db_store_handler)

# Compilator       
compilator = Compilator(input_queue = queues['compilator'], next_step = 'validator')

# Validator
validator = Validator(input_queue = queues['validator'], next_step = 'packer')

# Initialize services
services = {'Dicom Listener': store_scp,
            'Compilator': compilator,
            'Validator': validator}

# Get app configuration from database or initialize it
with application.app_context():
    try:
        config = AppConfig.query.first()
        assert config 
        logger.info('app config found in the database')
    except AssertionError:        
        logger.info('database is available but app config not found.')
        logger.info('initializing app config with default settings.')
        c = AppConfig()
        db.session.add(c)
        db.session.commit()
        config = AppConfig.query.first()
    except OperationalError as e:       
        logger.info("database is not available. App config can't be initialized")

# Start services
for name, service in services.items():
    try:
        if name == 'Dicom Listener':
            service.start(config.store_scp_aet, config.store_scp_port)
        else:
            service.start()
    except Exception as e:
        logger.error(f"failed when starting {name}")
        logger.error(repr(e))
