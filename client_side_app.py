import signal, logging, os

from app_pkg import application
from init_services import services
from shutil import rmtree

logger = logging.getLogger('__main__')

# Handle sigterm
def terminate_processes(signalNumber, frame):
    # Stop threads
    logger.error(f"stopping processes...")
    for name, service in services.items():
        try:
            service.stop()
        except Exception as e:
            logger.error(f"failed when stopping {name}")            
            logger.error(repr(e))
    
    # Clear temporary folders
    to_clear = ['incoming','dcm_templates','packed','SeriesToUnpack','unpackedSeries']
    for folder in to_clear:
        try:
            logger.info(f"removing {folder}")  
            rmtree(folder)
        except Exception as e:
            logger.error(f"failed when deleting {folder}")            
            logger.error(repr(e))

    # Clear shared folder
    try:
        mount_point = os.environ["SHARED_MOUNT_POINT"]
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

signal.signal(signal.SIGINT, terminate_processes)