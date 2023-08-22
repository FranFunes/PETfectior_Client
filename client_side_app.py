import signal, logging, os, sys
from app_pkg import application, db
from app_pkg.db_models import AppConfig
from app_pkg.services import services
from shutil import rmtree

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
            logger.error(repr(e))    
    
    # Clear temporary folders
    to_clear = ['packed_series','series_to_unpack','unpacked_series']
    for folder in to_clear:
        try:
            f = os.path.join('temp',folder)
            logger.info(f"removing {f}")  
            rmtree(f)
        except Exception as e:
            logger.error(f"failed when deleting {f}")            
            logger.error(repr(e))

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
                logger.error(repr(e))                  
    except Exception as e:
        logger.error(f"error while trying to clear shared folder {os.path.join(mount_point,'processed')}")                  
        logger.error(repr(e))                  
    
    exit(1)
    
if 'db' not in sys.argv:
    signal.signal(signal.SIGINT, terminate_processes)