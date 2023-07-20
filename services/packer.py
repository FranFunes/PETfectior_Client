import threading, logging, os, json
from shutil import make_archive, rmtree
from datetime import datetime
from time import sleep
from pydicom import dcmread
import numpy as np


# Configure logging
logger = logging.getLogger('__main__')


class SeriesPacker():

    def __init__(self, input_queue, output_queue, task_manager, 
                 template_path  = 'dcm_templates',
                 zipDir = 'packed'):

        self.task_manager = task_manager
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.zipDir = zipDir
        self.template_path = template_path

        # Get ClientID from configuration file
        config_file = os.path.join("data",'client.json')
        try:
            with open(config_file,"r") as filename:
                config = json.load(filename)
                self.client_id = config['client_id']
        except:
            self.client_id = None
            logger.error(f'client_id could not be read from {config_file}.')

        # Create store directory if it does not exist.
        try:
            os.makedirs(zipDir, exist_ok = True)
            logger.info(f'destination {zipDir} directory created successfully')
        except:
            logger.error(f'destination {zipDir} directory could not be created')

        # Create dcm templates directory if it does not exist.
        try:
            os.makedirs(template_path, exist_ok = True)
            logger.info(f'template path {template_path} directory created successfully')
        except:
            logger.error(f'template path {template_path} directory could not be created')


    def start(self):

        """
        
            Starts the process thread.            

        """

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        try:
            # Check if client_id is set
            assert self.client_id
        except:
            logger.error("SeriesPacker can't start: client_id not set")
            return "Packer can't be started: client ID is not set"
        else:
            try:
                # Check if temporary directory was created successfully
                assert os.path.isdir(self.zipDir)
            except:
                logger.error(f"SeriesPacker can't start: {self.zipDir} does not exist")
                return "Packer can't be started: an error ocurred when creating a temporary folder"
            else:
                try:
                    # Check if dicom templates directory was created successfully
                    assert os.path.isdir(self.template_path)
                except:
                    logger.error(f"SeriesPacker can't start: {self.template_path} does not exist")
                    return "Packer can't be started: an error ocurred when creating a temporary folder"
                else:
                    
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
            logger.error(repr(e))
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

            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():
                queue_element = self.input_queue.get()
                task_id = queue_element['task_id']
                self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'compressing'})    
                
                try:
                    # Get filenames from the queue
                    filenames = queue_element['filenames']

                    # Extract voxel values
                    voxels = self.extract_voxels(filenames)

                    # Move files to dedicated folder                    
                    os.makedirs(os.path.join(self.template_path, task_id), exist_ok = True)
                    logger.info('moving files')                    
                    for file in filenames:
                        name_only = os.path.basename(file)
                        os.rename(file, os.path.join(self.template_path, task_id, name_only))                

                    # Save voxel values to disk
                    os.makedirs('temp_series_packer', exist_ok = True)
                    np.save(os.path.join('temp_series_packer', 'voxels'), voxels)
                                        
                    # Save neccesary metadata
                    metadata = {
                        'client_id': self.client_id,
                        'task_id': task_id,
                        'recon_settings': queue_element['recon_settings'].to_json_dict()
                    }
                    with open(os.path.join("temp_series_packer", "metadata.json"), "w") as jsonfile:  
                        json.dump(metadata, jsonfile, indent = 2)     

                    # Zip voxels and metadata in a file with the task_id and client id as name
                    zip_fname = queue_element['task_id'] + '_' + self.client_id
                    archive_name = os.path.join(self.zipDir, zip_fname)           
                    logger.info('Zipping files to ' + archive_name)         
                    make_archive(archive_name, 'zip', "temp_series_packer")
                    
                    # Put it in the queue to be processed
                    contents = {
                        'filename': archive_name + '.zip',
                        'task_id': task_id,
                        'recon_settings': queue_element['recon_settings']
                    }
                    self.output_queue.put(contents)

                    # Update application database with task status
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'packed'}) 
                    
                    # Delete temporary folder
                    try:
                        logger.info('removing temp folder')
                        rmtree('temp_series_packer')
                    except Exception as e:
                        logger.info('could not remove temporary folder')
                        logger.info(repr(e))
                
                except Exception as e:
                    logger.info('compressing failed')
                    logger.info(repr(e))
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'failed - compressing'})                 
                                
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


        


        