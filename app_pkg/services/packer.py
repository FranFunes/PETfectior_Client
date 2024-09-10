import threading, logging, os, json, traceback
from shutil import make_archive, rmtree
from simple_file_checksum import get_checksum
from time import sleep
from pydicom import dcmread
import numpy as np

from app_pkg import application, db
from app_pkg.db_models import Task, AppConfig

# Configure logging
logger = logging.getLogger('__main__')

class SeriesPacker():

    def __init__(self, input_queue, next_step = 'uploader'):

        self.input_queue = input_queue
        self.next_step = next_step

    def start(self):

        """
        
            Starts the process thread.            

        """

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        try:
            # Check if AppConfig is available
            with application.app_context():
                config = AppConfig.query.first()
        except Exception as e:
            logger.error("can't start, AppConfig not available")            
            return "Packer can't be started: database not available"
        
        # Create temporary directory if it does not exist.
        try:
            os.makedirs(config.zip_dir, exist_ok = True)
            logger.info(f'destination {config.zip_dir} directory created successfully')
        except:
            logger.error(f'destination {config.zip_dir} directory could not be created')
            return "Packer can't be started: storage access error"
                
        if not self.get_status() == 'Corriendo':
            # Create and start the thread if all conditions are fullfilled
            self.main_thread = threading.Thread(target = self.main, args = ())        
            self.main_thread.start()
            logger.info('SeriesPacker started')
            return "Packer inició exitosamente"
        else:
            return "Packer ya está corriendo"

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("SeriesPacker stopped")
            return "Packer detenido"
        except Exception as e:
            logger.error("SeriesPacker stop failed")
            logger.error(traceback.format_exc())
            return "Packer no pudo ser detenido"
    
    def get_status(self):

        try:
            assert self.main_thread.is_alive()            
        except AttributeError:
            return 'No iniciado'
        except AssertionError:
            return 'Detenido'
        except:
            return 'Desconocido'
        else:
            return 'Corriendo'

    def main(self):

        while not self.stop_event.is_set() or not self.input_queue.empty():            
                            
                if not self.input_queue.empty():
                    task_id = self.input_queue.get()
                    with application.app_context():
                        reprocess = self.task_step_handler(task_id)
                    while reprocess and not self.stop_event.is_set():
                        logger.info(f'reprocessing {task_id}')   
                        with application.app_context():                     
                            reprocess = self.task_step_handler(task_id)
                        sleep(5)
                else:
                    sleep(1)

    def task_step_handler(self, task_id):
                            
        try:
            task = Task.query.get(task_id)
            task.status_msg = 'comprimiendo'
            db.session.commit()
        except:
            logger.error(f"task {task_id} status can't be updated")
            logger.error(traceback.format_exc())   
            return True

        try:
            config = AppConfig.query.first()

            # Get filenames for the instances of this task
            filenames = [i.filename for i in task.instances]

            # Extract voxel values
            voxels = self.extract_voxels(filenames)           

            # Save voxel values to disk
            os.makedirs('temp_series_packer', exist_ok = True)
            np.save(os.path.join('temp_series_packer', 'voxels'), voxels)
                                
            # Save neccesary metadata
            metadata = {
                'client_id': config.client_id,
                'task_id': task_id,
                'recon_settings': json.loads(task.recon_settings),
                'PatientWeight': task.task_series.study.PatientWeight,
                'PatientSize': task.task_series.study.PatientSize,
                'PatientAge': task.task_series.study.PatientAge,
                'StudyInstanceUID': task.task_series.study.StudyInstanceUID,
                'SeriesInstanceUID': task.series,
                'SeriesNumber': task.task_series.SeriesNumber,
                'SeriesDate': task.task_series.SeriesDate.strftime('%Y-%m-%d'),
                'SeriesTime': task.task_series.SeriesDate.strftime('%H:%M:%S'),
                'sha256':get_checksum(os.path.join('temp_series_packer', 'voxels.npy'), algorithm="SHA256")
            }
            with open(os.path.join("temp_series_packer", "metadata.json"), "w") as jsonfile:  
                json.dump(metadata, jsonfile, indent = 2)     

            # Zip voxels and metadata in a file with the task id and client id as name
            zip_fname = task_id + '_' + config.client_id
            archive_name = os.path.join(config.zip_dir, zip_fname)           
            logger.info('zipping files to ' + archive_name)         
            make_archive(archive_name, 'zip', "temp_series_packer")
            
            # Delete temporary folder
            try:
                logger.info('removing temp folder')
                rmtree('temp_series_packer')
            except Exception as e:
                logger.info('could not remove temporary folder')
                logger.info(traceback.format_exc())
            
            # Flag step as completed                                
            task.current_step = self.next_step
            task.status_msg = 'comprimido'
            task.step_state = 1
            logger.info(f"Task {task_id} packed.")
            db.session.commit()
            return False

        except Exception as e:
            logger.info(f'compressing failed for task {task_id}')
            logger.error(traceback.format_exc())
            try:
                task.status_msg = 'falló la compresión'
                task.step_state = -1
                task.full_status_msg = """Ocurrió un error desconocido al intentar comprimir los datos de imagen para
                    enviar al servidor remoto. Mensaje completo de error:\n\n""" + repr(e)
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True
    
    def extract_voxels(self, filenames):

        datasets = []
        for file in filenames:
            try:
                datasets.append(dcmread(file))
            except:
                pass
            
        # Sort by slice location
        z = [ds.ImagePositionPatient[2] for ds in datasets]
        order = np.argsort(z)
        datasets = [datasets[idx] for idx in order]

        # Extract voxel values in floating point
        v = [ds.pixel_array.astype(np.float32) * ds.RescaleSlope + ds.RescaleIntercept for ds in datasets]
        v = np.array(v).transpose([2,1,0])
        
        return v