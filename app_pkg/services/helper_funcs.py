import os, logging
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


