# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import signal, logging, os, sys, traceback
from app_pkg import application
from app_pkg.db_models import AppConfig
from app_pkg.services import services

logger = logging.getLogger('__main__')


if os.getenv('FLASK_HTTP_LOGGGING') == 'False':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

# Handle sigterm if app was started with flask run command
def terminate_processes(signalNumber, frame):
    # Stop threads
    logger.info(f"stopping processes...")
    for name, service in services.items():
        try:
            service.stop()
        except Exception as e:
            logger.error(f"failed when stopping {name}")            
            logger.error(traceback.format_exc())    
            
    # Clear shared folder
    try:
        with application.app_context():
            c = AppConfig.query.first()
        mount_point = c.shared_mount_point
        filelist = os.listdir(os.path.join(mount_point,'processed'))
        for file in filelist:
            try:
                fpath = os.path.join(mount_point, 'processed', file)
                logger.info(f"deleting {fpath} shared file")  
                os.remove(fpath)
            except Exception as e:
                logger.error(f"{fpath} couldn't be deleted")  
                logger.error(traceback.format_exc())                  
    except Exception as e:
        logger.error(f"error while trying to clear shared folder {os.path.join(mount_point,'processed')}")                  
        logger.error(traceback.format_exc())                  
    
    exit(1)
    
if 'db' not in sys.argv and 'shell' not in sys.argv:
    signal.signal(signal.SIGINT, terminate_processes)