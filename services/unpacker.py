import threading, logging, os, json
from shutil import unpack_archive
from time import sleep
import numpy as np
from pydicom import dcmread
from pydicom.uid import generate_uid
from datetime import datetime

# Configure logging
logger = logging.getLogger('__main__')

class SeriesUnpacker():

    def __init__(self, input_queue, output_queue, task_manager, 
                 template_path = 'dcm_templates', 
                 unzipDir = 'unpackedSeries'):

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.unzipDir = unzipDir
        self.task_manager = task_manager
        self.template_path = template_path

        # Create store directory if it does not exist.
        try:
            os.makedirs(unzipDir, exist_ok = True)
            logger.debug('Destination directory created successfully')
        except:
            logger.error('Destination directory could not be created')


    def start(self):

        """
        
            Starts the process thread.            

        """

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()        

        try:
            assert os.path.isdir(self.unzipDir)
        except:
            logger.error(f"SeriesUnpacker can't start: {self.unzipDir} does not exist")
            return "Packer can't be started: an error ocurred when creating a temporary folder"
        else:                
            if not self.get_status() == 'Running':
                # Create and start the thread
                self.main_thread = threading.Thread(target = self.main, args = ())        
                self.main_thread.start()
                logger.info('SeriesUnpacker started')

                if not os.path.isdir(self.template_path):
                    logger.warning(f"{self.template_path} does not exist")
                    return "Unpacker started but a required directory is missing"
                else:
                    return "Unpacker started successfully"
            else:
                return "Unpacker is already running"



    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("SeriesUnpacker stopped")
            return "SeriesUnpacker stopped"            
        except Exception as e:
            logger.error("SeriesUnpacker stop failed")
            logger.error(repr(e))
            return "SeriesUnpacker could not be stopped"

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

            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():
                # Get zip filename and task id from the queue
                element = self.input_queue.get()
                filename = element['filename']
                task_id = element['task_id']

                # Build zip filename
                zip_fname = os.path.splitext(os.path.basename(filename))[0]               

                # Decompress files                
                extract_dir = os.path.join(self.unzipDir, zip_fname)
                logger.info(f"Decompressing {filename} to {extract_dir}")
                self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'decompressing'})    
                try:
                    unpack_archive(filename, extract_dir)
                    logger.info(f"{filename} decompressed successfully")
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'decompressed ok'})    
                except Exception as e:
                    logger.error(f"Could not decompress file {filename}")
                    logger.error(repr(e))
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'decompressed failed'})    
                else:
                    
                    # List decompressed files
                    filelist = os.listdir(extract_dir)

                    # Keep .npy files only
                    npy_files = [file for file in filelist if os.path.splitext(file)[1] == '.npy']
                    
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'building dicoms'})    
                    success = 0
                    datasets = []
                    for idx, npy_file in enumerate(npy_files):                        
                        # Build dicom files
                        try:
                            datasets.extend(self.build_dicom_files(os.path.join(extract_dir, npy_file), task_id, idx))
                            success += 1
                            logger.info(f"Building dicoms for {npy_file} successful")
                        except Exception as e:
                            logger.error(f"Failed when building dicoms for {npy_file}")
                            logger.error( repr(e))
                                            
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': f"building dicoms {success}/{len(npy_files)}"})    
                    
                    # Put datasets in the output queue to be sent through DICOM interface
                    content = {'datasets': datasets, 'task_id': task_id}         
                    logger.info(f"{len(datasets)} dicoms put on queue for task {task_id}")           
                    
                    self.output_queue.put(content)

            else:
                sleep(1)

    def build_dicom_files(self, npy_file_path, task_id, idx):

        # Load and process voxels
        try:
            v = np.load(npy_file_path)            
        except:
            logger.error(f"Failed when loading voxels from {npy_file_path}")
            raise FileNotFoundError

        # Transpose to make for loops easier
        v = np.array(v).transpose([2,1,0])
        # Calculate rescale slopes for each slice
        slopes = (v.max(axis = (1,2)) / (2**15 - 1)).reshape((v.shape[0],1,1))        
        # Normalize each slice to 2**16 - 1 as max value and convert to uint16
        v = (v / slopes).astype(np.uint16)   

        # Load templates
        templates = []        
        filenames = os.listdir(os.path.join(self.template_path, task_id))
        for file in filenames:
            templates.append(dcmread(os.path.join(self.template_path, task_id, file)))            
            
        # Sort by slice location
        z = [ds.ImagePositionPatient[2] for ds in templates]
        order = np.argsort(z)
        templates = [templates[idx] for idx in order]
        
        # Replace voxel values on templates
        for idx, ds in enumerate(templates):
            ds.PixelData = v[idx].tobytes()
            ds.RescaleSlope = slopes[idx]
        
        # Get original SeriesDescription from database
        base = self.task_manager.data.loc[task_id, 'description']

        # Use .npy file as sufix for the SeriesDescription        
        sufix = '_'.join(os.path.splitext(os.path.basename(npy_file_path))[0].split('_')[1:])
        series_description = base + '_' + sufix
        series_uid = generate_uid()
        series_number = 1101 + idx
        timenow = datetime.now().strftime('%H%M%S')
        for ds in templates:
            ds.InstanceCreationTime = timenow
            ds.SOPInstanceUID = generate_uid()
            ds.ContentTime = timenow
            ds.SeriesInstanceUID = series_uid
            ds.SeriesNumber = series_number
            ds.SeriesDescription = series_description

        return templates




