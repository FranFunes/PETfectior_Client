import logging, threading, os, requests, psutil, json
from time import sleep
from shutil import copy
from pydicom.dataset import Dataset

# Configure logging
logger = logging.getLogger('__main__')

class SeriesUploader():

    def __init__(self, input_queue, task_manager, shared_mount_point):

        self.input_queue = input_queue  
        self.task_manager = task_manager
        self.shared_mount_point = shared_mount_point

    def start(self):

        """
        
            Starts the process thread.            

        """

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        try:             
            # Check if the shared folder exists
            assert os.path.isdir(self.shared_mount_point)
            
            # Create "to_process folder" if it doesn't exist
            self.shared = os.path.join(self.shared_mount_point, 'to_process')
            os.makedirs(self.shared, exist_ok = True)

            if not self.get_status() == 'Running':
                # Start the thread
                self.main_thread = threading.Thread(target = self.main, args = ())        
                self.main_thread.start()
                logger.info('Uploader started')
                return "Uploader started successfully"
            else:
                return "Uploader is already running"
            
        except AssertionError:
            logger.error(f"Uploader can't start ({self.shared_mount_point} is not a valid directory or is not existent)")
            return "Uploader can't be started: an error ocurred when creating a temporary folder"
        except Exception as e:
            logger.error(f"Uploader can't start ({os.path.join(self.shared_mount_point, 'to_process')} can't be created)")
            logger.error(f"Uploader - {repr(e)}")
            return "Uploader can't be started: an error ocurred when creating a temporary folder"

    
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

            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():
                # Get filenames from the queue
                element = self.input_queue.get()
                filename = element['filename']
                task_id = element['task_id']
                recon_settings = element['recon_settings']

                # Read and copy file to the shared folder
                try:                    
                    logger.info(f"Uploading {filename}")    
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'uploading'})      
                    basename = os.path.basename(filename)
                    copy(filename, self.shared)
                except Exception as e:
                    logger.error('Unknown error occurred during upload')
                    logger.error(repr(e))
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'upload failed'})  
                else:
                    # If upload was succesful, delete file and send a message to the server                    
                    logger.info(f"Upload successful for task {task_id}")
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'upload ok'})  
                    
                    if self.send_message(basename, recon_settings):
                        self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'processing'})  
                    else:
                        self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'commit to server failed'})  
                    os.remove(filename)
            else:
                sleep(1)

    def send_message(self, filename, metadata):
        
        if os.environ["SERVER_INTERACTION"] == "True":
            # Get the IP address for each network interface available
            interfaces = psutil.net_if_addrs()
            ips = []
            [[ips.append(item.address) for item in interface 
            if item.family.name == 'AF_INET' and not item.address == '127.0.0.1'] 
            for interface in interfaces.values()]

            # Read the client_id from a configuration file
            try:
                with open(os.path.join("data", "client.json"), "r") as jsonfile:        
                    client_id = json.load(jsonfile)["client_id"]                
            except:
                client_id = 'Unknown'
            
            # Send the post
            data = {
                'input_file': filename,
                'client_port':os.environ["FLASK_RUN_PORT"],  
                'client_id': client_id,
                'metadata': self.parse_metadata(metadata)
            }                                
            
            try:
                post_rsp = requests.post('http://' + os.environ['SERVER_URL'] + '/processing', json = data)
                assert post_rsp.json()['response'] == 'Processing'
                logger.info(f"post to /processing on succesful.")  
                return True
            except Exception as e:
                logger.error(f"post to /processing on server failed.")                
                logger.error(repr(e))
                return False
                
            

    def parse_metadata(self, ss: Dataset) -> dict:

        """
        
        Esta función toma el diccionario contenido en el archivo metadata.json que está dentro del .zip que escribe el cliente
        y devuelve un diccionario con las siguientes keys:

        'ManufacturerModelName'
        'ReconstructionMethod'
        'Iteraciones'
        'Subsets'
        'VoxelSpacing'
        'SliceThickness'
        'Radiofarmaco'
        'HalfLife'

        """
        
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

        return data
        
