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
                
        if not self.get_status() == 'Running':
            # Create and start the thread if all conditions are fullfilled
            self.main_thread = threading.Thread(target = self.main, args = ())        
            self.main_thread.start()
            logger.info('SeriesPacker started')
            return "Packer started successfully"
        else:
            return "Packer is already running"

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("SeriesPacker stopped")
            return "Packer stopped!"
        except Exception as e:
            logger.error("SeriesPacker stop failed")
            logger.error(traceback.format_exc())
            return "Packer could not be stopped!"
    
    def get_status(self):

        try:
            assert self.main_thread.is_alive()            
        except AttributeError:
            return 'Not started'
        except AssertionError:
            return 'Stopped'
        except:
            return 'Unknown'
        else:
            return 'Running'

    def main(self):

        while not self.stop_event.is_set() or not self.input_queue.empty():
            with application.app_context():
                    
                # If there are any elements in the input queue, read them.
                if not self.input_queue.empty():                    
                    task = Task.query.get(self.input_queue.get())
                    task.status_msg = 'compressing'
                    db.session.commit()
                    config = AppConfig.query.first()
                                        
                    try:
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
                            'task_id': task.id,
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
                        zip_fname = task.id + '_' + config.client_id
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
                        task.status_msg = 'packed'
                        task.step_state = 1
                        logger.info(f"Task {task.id} packed.")

                    except Exception as e:
                        logger.info(f'compressing failed for task {task.id}')
                        logger.error(traceback.format_exc())
                        task.status_msg = 'compression failed'
                        task.step_state = -1
                        task.full_status_msg = """An unknown error ocurred while trying to compress image data to send to the
                        remote processing server. Full error message follows: \n\n""" + repr(e)    
                                    
                    db.session.commit()
                else:   
                    sleep(1)
    
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