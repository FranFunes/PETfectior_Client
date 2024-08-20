import logging, threading, os, requests
from time import sleep
from shutil import copy
from pydicom.dataset import Dataset
from datetime import datetime

from app_pkg import application, db
from app_pkg.db_models import Task, AppConfig

# Configure logging
logger = logging.getLogger('__main__')

class SeriesUploader():

    def __init__(self, input_queue):

        self.input_queue = input_queue

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
            return "Uploader can't be started: database not available"

        # Check if the shared folder exists
        try:             
            assert os.path.isdir(config.shared_mount_point)
            
            # Create "to_process folder" if it doesn't exist
            os.makedirs(os.path.join(config.shared_mount_point, 'to_process'), exist_ok = True)

            if not self.get_status() == 'Running':
                # Start the thread
                self.main_thread = threading.Thread(target = self.main, args = ())        
                self.main_thread.start()
                logger.info('Uploader started')
                return "Uploader started successfully"
            else:
                return "Uploader is already running"
            
        except AssertionError:
            logger.error(f"Uploader can't start ({config.shared_mount_point} is not a valid directory or is not existent)")
            return f"Uploader can't start ({config.shared_mount_point} is not a valid directory or is not existent)"
        except Exception as e:
            logger.error(f"Uploader can't start ({os.path.join(config.shared_mount_point, 'to_process')} can't be created)")
            logger.error(f"Uploader - {repr(e)}")
            return f"Uploader can't start ({os.path.join(config.shared_mount_point, 'to_process')} can't be created)"

    
    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            # Event to interrupt processing        
            self.stop_event.set()
            # Stop the thread
            self.main_thread.join()
            logger.info("Uploader stopped")
            return "Uploader stopped"
        except Exception as e:
            logger.error("Uploader could not be stopped")
            logger.error(repr(e))
            return "Uploader could not be stopped"

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
                    config = AppConfig.query.first()
                    filename = os.path.join(config.zip_dir, task.id + '_' + config.client_id + '.zip')

                    # Read and copy file to the shared folder
                    try:                    
                        logger.info(f"Uploading {filename}")    
                        task.status_msg = 'uploading'
                        db.session.commit()
                        basename = os.path.basename(filename)
                        copy(filename, os.path.join(config.shared_mount_point, 'to_process'))
                    except Exception as e:
                        logger.error(f"Unknown error occurred while copying {filename} to {os.path.join(config.shared_mount_point, 'to_process')}")
                        logger.error(repr(e))
                        task.status_msg = 'upload failed'
                        task.step_state = -1
                        task.full_status_msg = """An unknown error occurred while trying to uploading task data to the remote
                        processing server. Full error message follows:\n\n""" + repr(e)   
                    else:
                        # If upload was succesful, delete file and send a message to the server                    
                        logger.info(f"copied {filename} to {os.path.join(config.shared_mount_point, 'to_process')} for task {task.id}")
                        task.status_msg = 'upload ok'
                        db.session.commit()
                        try:                                                        
                            assert self.send_message(basename, task, config)
                            os.remove(filename)
                            task.status_msg = 'processing'
                            logger.info('commit to server ok')
                            logger.info(f"File {filename} deleted")
                        except Exception as e:
                            logger.error('commit to server failed')
                            logger.error(repr(e))
                            task.status_msg = 'commit to server failed'
                            task.step_state = -1
                            task.full_status_msg = """An error occurred while trying to trigger processing on the remote server."""  
                    db.session.commit()
                else:
                    sleep(1)

    def send_message(self, filename, task, config):
        
        if not os.environ["SERVER_INTERACTION"] == "True":
            return True                        
                
        # Send the post
        data = {
            "input_file": filename,
            "client_port": os.environ["FLASK_RUN_PORT"],
            "client_id": config.client_id,
            "metadata": self.extract_metadata(task)
        }
        try:
            post_rsp = requests.post('http://' + config.server_url + '/processing', json = data)
            assert post_rsp.json()['response'] == 'Processing'
            logger.info(f"post to /processing on server succesful.")  
            return True
        except Exception as e:
            logger.error(f"post to /processing on server failed.")                
            logger.error(repr(e))
            return False

    def extract_metadata(self, task: Task) -> dict:

        """
        
        Esta función toma extrae de la tarea almacenada en la base de datos, 
        los siguientes campos, y genera un json para pasar al server:

        'ManufacturerModelName'
        'ReconstructionMethod'
        'Iteraciones'
        'Subsets'
        'VoxelSpacing'
        'SliceThickness'
        'Radiofarmaco'
        'HalfLife'
        'StudyInstanceUID'
        'SeriesInstanceUID'
        'StudyDate'
        'SeriesTime'
        'radiopharmaceutical_dose'
        'radiopharmaceutical_start'
        'weight'
        'height'
        'age'

        """
        
        ss = Dataset.from_json(task.recon_settings)

        if ss.Manufacturer == 'SIEMENS':
            recon_method = ss.ReconstructionMethod
            iterations_index = recon_method.find('i')
            subset_index = recon_method.find('s')
            space_index = recon_method.find(' ')
            iterations = int(recon_method[space_index+1:iterations_index])
            subsets = int(recon_method[iterations_index+1:subset_index])
            
        elif ss.Manufacturer == 'GE MEDICAL SYSTEMS':
            if type(ss[0x000910B2].value) == bytes:
                iterations = int.from_bytes(ss[0x000910B2].value, "little")  
            else:
                iterations = ss[0x000910B2].value            
            
            if type(ss[0x000910B3].value) == bytes:
                subsets = int.from_bytes(ss[0x000910B3].value, "little")  
            else:
                subsets = ss[0x000910B3].value

        else:        
            raise ValueError('Fabricante desconocido')
        
        series_date = task.task_series.SeriesDate
        rf_start_time = getattr(ss.RadiopharmaceuticalInformationSequence[0],
                                                 'RadiopharmaceuticalStartTime', '')
        try:
            rf_start_time = datetime.strptime(rf_start_time, "%H%M%S")
        except ValueError:
            rf_start_time = datetime.strptime(rf_start_time, "%H%M%S.%f")
        
        if rf_start_time:
            radiopharmaceutical_start = series_date.strftime("%Y-%m-%d") + ' ' + rf_start_time.strftime("%H:%M:%S")
        else:
            radiopharmaceutical_start = ''
            
        data = {
                'ManufacturerModelName': str(ss.ManufacturerModelName),
                'ReconstructionMethod': str(ss.ReconstructionMethod),
                'Iteraciones': iterations,
                'Subsets': subsets,
                'VoxelSpacing': str(ss.PixelSpacing),
                'SliceThickness': ss.SliceThickness,
                'Radiofarmaco': getattr(ss.RadiopharmaceuticalInformationSequence[0],'Radiopharmaceutical',''),
                'HalfLife': float(getattr(ss.RadiopharmaceuticalInformationSequence[0],'RadionuclideHalfLife',0)),
                'radiopharmaceutical_dose': round(float(getattr(ss.RadiopharmaceuticalInformationSequence[0],'RadionuclideTotalDose', 0)) / 37000000, 2),
                'radiopharmaceutical_start': radiopharmaceutical_start,
                'StudyInstanceUID': task.task_series.study.StudyInstanceUID,
                'SeriesInstanceUID': task.series,
                'StudyDate': task.task_series.study.StudyDate.strftime("%Y-%m-%d"),
                'SeriesTime': task.task_series.SeriesDate.strftime('%H:%M:%S'),
                'weight': task.task_series.study.PatientWeight,
                'height': task.task_series.study.PatientSize,
                'age': task.task_series.study.PatientAge
            }            

        return data
        
