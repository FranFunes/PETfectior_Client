import os, logging, subprocess
from app_pkg import application, db
from app_pkg.db_models import Task, AppConfig
from shutil import make_archive, unpack_archive, rmtree
import numpy as np

# Configure logging
logger = logging.getLogger('__main__')


def process(task_id):

    with application.app_context():

        task = Task.query.get(task_id)
        config = AppConfig.query.first()
        zip_filename = os.path.join(config.shared_mount_point,'to_process',task.id + '_' + config.client_id + '.zip')        
        unzip_folder = os.path.join('temp',task.id)
        os.makedirs(unzip_folder, exist_ok=True)
        unpack_archive(zip_filename, unzip_folder)
        voxels_file = os.path.join(unzip_folder, 'voxels.npy')

        array = np.load(voxels_file)
        shape = array.shape
        array[64:96,64:96,20:30] = 0
        
        np.save(os.path.join(unzip_folder, 'processed.npy'), array)
        os.remove(voxels_file)
        archive_name = os.path.join(config.shared_mount_point,'processed',task.id + '_' + config.client_id)        
        make_archive(archive_name, 'zip', unzip_folder)

        rmtree('temp')
        os.remove(zip_filename)

        # Flag step as completed     
        task.current_step = 'downloader'
        task.step_state = 1

        db.session.commit()

def ping(target_host, timeout = 100, count = 3):

    if os.name == "nt":
        command = ["ping", "-w", str(timeout), "-n", str(count), target_host]
    elif os.name == "posix":
        command = ["ping", "-W", str(timeout), "-c", str(count), target_host]
    else:
        return False

    try:
        completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = completed_process.stdout
        stderr = completed_process.stderr

        if completed_process.returncode == 0:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        return False
