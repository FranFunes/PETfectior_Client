import queue, logging, json, os, requests, threading

from services.loggers import app_logger
from services.task_manager import TaskManager
from services.store_scp import StoreSCP
from services.compilator import Compilator
from services.packer import SeriesPacker
from services.uploader_vpn import SeriesUploader
from services.downloader_queue import SeriesDownloader
from services.unpacker import SeriesUnpacker
from services.store_scu import StoreSCU
from services.server_monitor import ServerMonitor

# Setup logging
app_logger()
logger = logging.getLogger('__main__')

# Initialize queues for different processes
queue_scp = queue.Queue()
packing_queue = queue.Queue()
upload_queue = queue.Queue()
download_queue = queue.Queue()
unpacking_queue = queue.Queue()
queue_scu = queue.Queue()

# Task Manager
task_manager = TaskManager()

# DICOM Store SCP    
store_scp = StoreSCP(scp_queue = queue_scp)

# Compilator       
server_url = os.environ["SERVER_URL"]
compilator = Compilator(queue_scp, packing_queue, task_manager, server_url)

# Packer
packer = SeriesPacker(packing_queue, upload_queue, task_manager)

# Uploader    
mount_point = os.environ["SHARED_MOUNT_POINT"]
uploader = SeriesUploader(upload_queue, task_manager, mount_point)

# Downloader
downloader = SeriesDownloader(download_queue, unpacking_queue, task_manager, mount_point)

# Unpacker
unpacker = SeriesUnpacker(unpacking_queue, queue_scu, task_manager)

# Store SCU
store_scu = StoreSCU(queue_scu, task_manager)

# Server Monitor
monitor =  ServerMonitor(server_url, 'check_ping', 1)

# Initialize services
services = {'Dicom Listener': store_scp, 
            'Compilator': compilator, 
            'Packer': packer, 
            'Uploader': uploader,
            'Downloader': downloader,
            'Unpacker': unpacker,
            'Dicom Send': store_scu,
            'Server Monitor': monitor}

# Initialize local config file
try:
    with open(os.path.join("data", "local.json"), "r") as jsonfile:         
        config = json.load(jsonfile)
    ae_title = config['ae_title']
    mirror_mode = config['mirror_mode'] 

except Exception as e:
    logger.error("failed when reading local config file. ")
    logger.error(repr(e))
    logger.error("trying to start store scp with default configuration. ")
    try:
        with open(os.path.join("data", "local.json"), "w") as jsonfile:      
            json.dump({'ae_title':'PETFECTIOR',
                       'mirror_mode': False}, 
                       jsonfile, indent = 2)
    except:
        logger.error("failed when writing local config file. ")
        logger.error(repr(e))
        raise IOError

# Initialize DICOM peers file
try:
    with open(os.path.join("data", "peers.json"), "r") as jsonfile:         
        pass
except Exception as e:
    logger.error("failed when reading peers file. ")
    logger.error(repr(e))
    logger.error("peers file will be initialized. ")
    try:
        with open(os.path.join("data", "peers.json"), "w") as jsonfile:      
            json.dump({}, jsonfile, indent = 2)
    except:
        logger.error("failed when writing peers file. ")
        logger.error(repr(e))
        raise IOError


# Start services
for name, service in services.items():
    try:
        if name == 'Dicom Listener':
            service.start(ae_title)
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


# And another comment here