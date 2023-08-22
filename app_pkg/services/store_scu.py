from pynetdicom import AE
from pynetdicom.sop_class import PositronEmissionTomographyImageStorage
from pydicom import dcmread
from pydicom.dataset import Dataset
import os, threading, logging, json
from time import sleep
from typing import List, Union, Callable
from pathlib import Path

from app_pkg import application, db
from app_pkg.db_models import Task

# Configure logging
logger = logging.getLogger('__main__')

class StoreSCU(AE):    

    """ The main class for creating and managing DICOM Store Service Class User.
        Inherits from pynetdicom AE class, so it has similar functionality.
        Some properties and methods are added to simplify its usage as a DICOM Store SCU:
    
        Properties:
            · work_dir: the working directory. All DICOM files put in this directory and all its subdirectories
              will be sent (when operated in server mode)
            · dest_nodes: a list of dict with following keys for each destination node:
                'ae_title': str with ae_title of peer AE
                'ip': str with ip of peer AE
                'port': int with TCP port of peer AE                   
            
        Methods:
            · start: starts the SCP in server mode as a thread. It will constantly read the working directory and all its subdirectories,
              and send all DICOM files present to the dest_nodes. Successfully sent files will be deleted if this option is enabled.
            · stop: stops the server.
            · send_list_of_dicoms: sends a list of dicom files to the dest_nodes.
            · send_dicoms_in_dir: sends all dicom files present in the working directory to the dest_nodes.
    
    """

    def __init__(self, input_queue, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Set class properties
        self.input_queue = input_queue

        # Add requested contexts
        self.add_requested_context(PositronEmissionTomographyImageStorage)

    def send_datasets(self, device: dict, datasets: List[Union[Dataset, str, Path]]) -> List[dict]:
        
        """

            Sends a C-STORE request to a remote (destination) device or application, to store a list of pydicom.Dataset.
            
            Args:
                · datasets: a list of pydicom.dataset.Dataset, str or pathlib.Path
                    The list of DICOM datasets to send to the peer or the file path to the
                    datasets to be sent. If a file path then the datasets will be read
                    and decoded using :func:`~pydicom.filereader.dcmread`.
                · device: a dict with the following fields for the destination:
                    - ae_title: the source ae_title (str)
                    - address: ip address of the source AE (str)
                    - port: port of the source AE (int)

            Returns: a list with equal size as datasets. Each element is a boolean, indicating if store was succesful.

        """
        # Create association
        association = self.associate(device['address'], device['port'], ae_title = device['ae_title'])     
        
        # Send the C-STORE
        results = []      
        
        for dataset in datasets:
            try:
                status = association.send_c_store(dataset)
                if status and status.Status == 0:
                    results.append(True)
                else:
                    results.append(False)
            except RuntimeError:
                results.append(False)
                logger.error(f"Association with {device['ae_title']}@{device['address']}:{device['port']} is not stablished")     
            except Exception as e:
                results.append(False)
                logger.error(f"c-store failed")     
                logger.error(repr(e))     

        return results
    
    def main(self):
        
        while not self.stop_event.is_set() or not self.input_queue.empty():

            if not self.input_queue.empty():
                with application.app_context():
                    
                    # Read task from input queue and datasets from database
                    task = Task.query.get(self.input_queue.get())                    
                    datasets = []
                    for result in task.result_series.all():
                        for instance in result.instances.all():
                            datasets.append(instance.filename)

                    logger.info(f'sending DICOMs for task {task.id}')
                    task.status_msg = 'sending DICOMs'
                    db.session.commit()
                    
                    # Send datasets to each destination
                    dest = {d.name: {'ae_title':d.ae_title,'address':d.address,'port':d.port} for d in task.destinations}                  
                    msg = []
                    for name, device in dest.items():
                        succesful = self.send_datasets(device, datasets)
                        msg.append(f"{name}: {sum(succesful)}/{len(datasets)}")
                    logger.info(f'sending DICOMs task {task.id} ' + ' '.join(msg))
                    status = '<br>'.join(msg)
                    task.status_msg = status   
                    task.step_state = 2             
                
                    db.session.commit()
            else:
                sleep(1)


    def start(self):

        """
        
            Starts the process thread.            

        """
    
        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        if not self.get_status() == 'Running':
            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, args = ())        
            self.main_thread.start()        
            logger.info('StoreSCU started')
            return "Dicom send started successfully"
        else:
            return "Dicom send is already running"

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("StoreSCU stopped")
            return "StoreSCU stopped"
        except:
            logger.error("StoreSCU could not be stopped")
            return "StoreSCU could not be stopped"

    def restart(self):

        self.stop()
        self.start()

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