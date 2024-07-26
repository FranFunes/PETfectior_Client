import json, threading, logging, os, requests
from requests import ConnectionError
from time import sleep
from datetime import datetime
import numpy as np
from pydicom import Dataset

from typing import List

from app_pkg import application, db
from app_pkg.db_models import Device, Task, PetModel, AppConfig

# Configure logging
logger = logging.getLogger('__main__')

class Validator():

    """
    
        This class is used to verify that a Task is ready to be packed and uploaded to the server.
        It checks three conditions:
        - The Task has at least one destination assigned
        - The information about the reconstruction settings for the instances associated with the task
         are enough to be processed by the server.
        - A model exists in the server for the recon settings of this task.
                
    
    """

    def __init__(self, input_queue, next_step = 'packer'):
              
        self.input_queue = input_queue   
        self.next_step = next_step   

    def start(self):

        """
        
            Starts the process thread.            

        """

        try:
            # Check if AppConfig is available
            with application.app_context():
                config = AppConfig.query.first()
        except Exception as e:
            logger.error("can't start, AppConfig not available")            
            return "Validator can't be started: database not available"

        if not self.get_status() == 'Running':
            # Set an event to stop the thread later 
            self.stop_event = threading.Event()

            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, 
                                                args = (), name = 'Validator')        
            self.main_thread.start()
            logger.info('started')
            return 'Validator started successfully'
        else:
            return 'Validator is already running'

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("stopped")
            return "Validator stopped"
        except:
            logger.info("stopped")
            return "Validator could not be stopped"


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

        """
        
            The main processing function that is called when thread is started.
            · Reads a task id from the input queue
            · Tries to find an appropiate destination for the Task, and flags it as failed if
            it couldn't
            · Checks if recon settings (available as serialized JSON in Task.recon_settings)
            is enough to complete
            · Sends a POST to the server to check if there exists a model for these recon settings         
               

        """

        while not self.stop_event.is_set() or not self.input_queue.empty():
            
            with application.app_context():

                timing = datetime.now()
                # If there are any elements in the input queue, read them.
                if not self.input_queue.empty():

                    # Read task id from the input queue
                    task = Task.query.get(self.input_queue.get())
                    task.status_msg = 'validating'
                    db.session.commit()

                    # Set destinations for this task
                    destinations = self.set_destinations(task.id)
                    if not destinations:
                        logger.error(f"task {task.id} destination is unknown.")
                        task.status_msg = 'failed - no destination'
                        task.step_state = -1                        
                    else:
                        for dest in destinations:
                            if not dest in task.destinations:
                                task.destinations.append(dest)
                        # Check if dicom information is complete
                        recon_settings = Dataset.from_json(task.recon_settings)
                        if not self.check_dicom_parameters(recon_settings):
                            logger.info(f"task {task.id} completed but there is missing dicom information.")
                            task.status_msg = 'failed - missing info'
                            task.step_state = -1                            
                        else:
                            # Check if a model exists in the remote processing server for this model                            
                            try:
                                assert self.check_model(recon_settings)
                            except AssertionError:                            
                                logger.error(f"task {task.id} completed but no model found for these recon settings: {recon_settings.to_json()}")
                                task.status_msg = 'failed - no model'
                                task.step_state = -1  
                            except ConnectionError as e:                            
                                logger.error(f"server connection failed.")
                                logger.error(repr(e))
                                task.status_msg = 'failed - server connection'
                                task.step_state = -1
                            except AttributeError as e:
                                logger.error(f"missing dicom information for task {task.id}.")
                                logger.error(repr(e))
                                task.status_msg = 'failed - missing info'
                                task.step_state = -1                  
                            else:
                                # Add this PET device name to the database
                                names = [m.name for m in PetModel.query.all()]
                                if not recon_settings.ManufacturerModelName in names:
                                    model = PetModel(name = recon_settings.ManufacturerModelName)
                                    db.session.add(model)                          

                                # Flag step as completed                                
                                task.current_step = self.next_step
                                task.status_msg = 'validated'
                                task.step_state = 1
                                logger.info(f"Task {task.id} validated.")
                                
                    db.session.commit()
                                            
                else:
                    sleep(1)

                        
    def set_destinations(self, task_id: str) -> List[Device]:

        destinations = []
        
        # Add devices with "is_destination" == True
        destinations.extend(Device.query.filter_by(is_destination = True).all())        
        # Check if mirror mode is activated and there are any devices matching the source IP/AET
        mirror_mode = AppConfig.query.first().mirror_mode
        if mirror_mode:       
            src_id = Task.query.get(task_id).source       
            aet, ip = src_id.split('@')
            matching_ip = Device.query.filter_by(address = ip).all()         
            if len(matching_ip) == 1:
                destinations.extend(matching_ip)
            else:
                # If there are more than one devices that match IP, check if any matches both IP and AE title
                matching_aet = Device.query.filter_by(address = ip, ae_title = aet)
                if not matching_aet:
                    destinations.extend(matching_ip)
                else:
                    destinations.extend(matching_aet)
        
        # Remove duplicated
        destinations = list(set(destinations))

        return destinations
    
    def check_dicom_parameters(self, dataset: Dataset) -> bool:

        """
        
            Checks if dataset has the required fields to be sent to the server

        """
        fields = ['PixelSpacing','SliceThickness','Manufacturer','RadiopharmaceuticalInformationSequence']
        for field in fields:
            try:
                dataset[field]
            except:
                logger.error(field + " unavailable")
                return False
        try:
            dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
        except:
            logger.error("Radiopharmaceutical unavailable")
            return False
        
        try:
            assert dataset.Manufacturer in ['SIEMENS','GE MEDICAL SYSTEMS']
        except:
            logger.error(dataset.Manufacturer + " not valid")
            return False
        
        if dataset.Manufacturer=='SIEMENS':  
            try:
                dataset.ConvolutionKernel
            except:
                logger.error("SIEMENS dataset does not have the ConvolutionKernel field")
                return False  
            try:
                dataset.ReconstructionMethod
            except:
                logger.error("SIEMENS dataset does not have the ReconstructionMethod field")
                return False                
        elif dataset.Manufacturer=='GE MEDICAL SYSTEMS':        
            try:
                dataset[0x000910B2]
            except Exception as e:
                logger.error("GE MEDICAL SYSTEMS dataset does not have the 0x000910B2 field")
                logger.error(repr(e))

                return False        
            try:
                dataset[0x000910B3]
            except:
                logger.error("GE MEDICAL SYSTEMS dataset does not have the 0x000910B3 field")
                return False                   
            try:
                dataset[0x000910BA]
            except:
                logger.error("GE MEDICAL SYSTEMS dataset does not have the 0x000910BA field")
                return False          
            
            if type(dataset[0x000910BA].value) == bytes:
                isfiltered = int.from_bytes(dataset[0x000910BA].value, "little")  
            else:
                isfiltered = dataset[0x000910BA].value    
            if isfiltered:
                try:
                    dataset[0x000910BB]
                except:
                    logger.error("GE MEDICAL SYSTEMS dataset is filtered and  does not have the 0x000910BB field")
                    return False
                try:
                    dataset[0x000910DC]
                except:
                    logger.error("GE MEDICAL SYSTEMS dataset is filtered and does not have the 0x000910DC field")
                    return False
        
        return True

    def check_model(self, ss: Dataset) -> bool:
                
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
            logger.info(f"no models for manufacturer {ss.Manufacturer}")      
            return False
        
        data = {
                'ManufacturerModelName': str(ss.ManufacturerModelName),
                'ReconstructionMethod': str(ss.ReconstructionMethod),
                'Iteraciones': iterations,
                'Subsets': subsets,
                'VoxelSpacing': str(ss.PixelSpacing),
                'SliceThickness': ss.SliceThickness,
                'Radiofarmaco': ss.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical,
                'HalfLife': ss.RadiopharmaceuticalInformationSequence[0].RadionuclideHalfLife
            }           

        if not os.environ["SERVER_INTERACTION"] == "True":
            return True
    
        server_url = AppConfig.query.first().server_url
        post_rsp = requests.post('http://' + server_url + '/check_model', json = data)
        if not post_rsp.json()['response']:
            logger.error(f"model not found.")   
            return False             
        else:
            logger.info(f"model found.")  
            return True       