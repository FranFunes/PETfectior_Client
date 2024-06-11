import queue, logging, sys

from sqlalchemy.exc import OperationalError, ProgrammingError

from app_pkg import application, db
from app_pkg.db_models import AppConfig, Task

from app_pkg.functions.loggers import app_logger, dicom_logger
from app_pkg.functions.db_store_handler import db_store_handler

from app_pkg.services.store_scp import StoreSCP
from app_pkg.services.compilator import Compilator
from app_pkg.services.validator import Validator
from app_pkg.services.task_manager import TaskManager
from app_pkg.services.packer import SeriesPacker
from app_pkg.services.uploader import SeriesUploader
from app_pkg.services.downloader import SeriesDownloader
from app_pkg.services.unpacker import SeriesUnpacker
from app_pkg.services.store_scu import StoreSCU
from app_pkg.services.server_monitor import ServerMonitor

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
    'packer': queue.Queue(),
    'uploader': queue.Queue(),
    'downloader': queue.Queue(),    
    'unpacker': queue.Queue(),
    'store_scu': queue.Queue()
}

# Task manager
task_manager = TaskManager(queues)

# DICOM Store SCP    
store_scp = StoreSCP(input_queue = queues['compilator'], c_store_handler=db_store_handler)

# Compilator       
compilator = Compilator(input_queue = queues['compilator'], next_step = 'validator')

# Validator
validator = Validator(input_queue = queues['validator'], next_step = 'packer')

# Packer
packer = SeriesPacker(input_queue = queues['packer'], next_step = 'uploader')

# Uploader
uploader = SeriesUploader(input_queue = queues['uploader'])

# Downloader
downloader = SeriesDownloader(input_queue = queues['downloader'], next_step = 'unpacker')

# Unpacker
unpacker = SeriesUnpacker(input_queue = queues['unpacker'], next_step = 'store_scu')

# Store SCU
store_scu = StoreSCU(input_queue = queues['store_scu'])

# Server Monitor
monitor =  ServerMonitor('check_ping', 1)

# Initialize services
services = {'Dicom Listener': store_scp,
            'Compilator': compilator,
            'Validator': validator,
            'Packer': packer,
            'Uploader': uploader,
            'Downloader': downloader,
            'Unpacker': unpacker,
            'StoreSCU': store_scu,
            'Task Manager': task_manager,
            'Server Monitor': monitor}

# Get app configuration from database or initialize it
app_config_available = False
with application.app_context():
    try:
        config = AppConfig.query.first()
        assert config 
        logger.info('app config found in the database')
        app_config_available = True
    except AssertionError:        
        logger.info('database is available but app config not found.')
        logger.info('initializing app config with default settings.')
        c = AppConfig()
        db.session.add(c)
        db.session.commit()
        config = AppConfig.query.first()
        app_config_available = True
    except OperationalError as e:       
        logger.info("database is not available. App config can't be initialized")
    except ProgrammingError as e:
        logger.info("database has not been initialized properly. App config can't be initialized")


if app_config_available:
    if 'db' not in sys.argv and 'shell' not in sys.argv and 'init_db.py' not in sys.argv:
        # Set all pending tasks state to failed (-1)
        with application.app_context():
            for task in Task.query.filter_by(step_state = 0).all():
                task.step_state = -1
                task.status_msg = 'aborted - app reset'
                db.session.commit()

        # Start services (except by Server Monitor)
        for name, service in services.items():
            if name != 'Server Monitor':
                try:
                    service.start()
                except Exception as e:
                    logger.error(f"failed when starting {name}")
                    logger.error(repr(e))

else:
    logger.error(f"services won't start as database is not available")
