import logging, threading, os, json
from time import sleep
from shutil import copy

# Configure logging
logger = logging.getLogger('__main__')

class SeriesDownloader():

    def __init__(self, input_queue, output_queue, task_manager, shared_mount_point, output_folder = 'SeriesToUnpack'):

        self.input_queue =  input_queue
        self.output_queue = output_queue
        self.shared_mount_point = shared_mount_point
        self.output_folder = output_folder
        self.task_manager = task_manager

        # Create output directory if it does not exist.
        try:
            os.makedirs(output_folder, exist_ok = True)
            logger.debug('output directory created successfully')
        except:
            logger.error('output directory could not be created')  

        # Get ClientID from configuration file
        config_file = os.path.join("data",'client.json')
        try:
            with open(config_file,"r") as filename:
                config = json.load(filename)
                self.client_id = config['client_id']
        except:
            self.client_id = None
            logger.error(f'client_id could not be read from {config_file}.')

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
            logger.error("Series Downloader can't start: client_id not set")
            return "Downloader can't be started: client ID is not set"
        else:
            try:

                # Check if the shared folder exists
                assert os.path.isdir(self.shared_mount_point)
                
                # Create "to_process folder" if it doesn't exist
                self.shared = os.path.join(self.shared_mount_point, 'processed')
                os.makedirs(self.shared, exist_ok = True)

                if not self.get_status() == 'Running':
                    # Start the thread
                    self.main_thread = threading.Thread(target = self.main, args = ())        
                    self.main_thread.start()
                    logger.info('Downloader started')
                    return "Downloader started successfully"
                else:
                    return "Downloader is already running"
            
            except AssertionError:
                logger.error(f"can't start ({self.shared_mount_point} is not a valid directory or is not existent)")
                return "Downloader can't be started: an error ocurred when creating a temporary folder"
            except:
                logger.error(f"can't start ({os.path.join(self.shared_mount_point, 'processed')} can't be created)")
                return "Downloader can't be started: an error ocurred when creating a temporary folder"

    
    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            # Event to interrupt processing        
            self.stop_event.set()
            # Stop the thread
            self.main_thread.join()
            logger.info("Downloader stopped")
            return "Downloader stopped"
        except Exception as e:
            logger.error("Downloader could not be stopped")
            logger.error(repr(e))
            return "Downloader could not be stopped"

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

            if not self.input_queue.empty():

                # Read task_id to process from the input queue
                task_id = self.input_queue.get()

                # Reconstruct the filename from task_id and client_id
                file = task_id + '_' + self.client_id + '.zip'

                # Update info in frontend
                self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'downloading'})                                

                # Download file                
                try:
                    fpath = os.path.join(self.shared, file)
                    local_fname = os.path.join(self.output_folder, file)                    
                    logger.info(f"downloading {fpath} over vpn")                    
                    copy(fpath, local_fname)
                except FileNotFoundError as e:
                    logger.error('Download error: file ' + fpath + ' not found')
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'download failed'})
                except Exception as e:
                    logger.error('Unknown error during download')
                    logger.error(repr(e))
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'download failed'})
                else:                    
                    # If download was successful, put filename in queue for further processing
                    content = {'filename': local_fname, 'task_id': task_id}
                    self.output_queue.put(content)  
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'download ok'})
                    logger.info(f"{file} downloaded successfully")
                    logger.info(f"{local_fname} put on queue")
                    # Delete file from vpn shared folder
                    try:
                        os.remove(fpath)
                        logger.info(f"{fpath} deleted from vpn shared folder")
                    except Exception as e:
                        logger.error(f"Unknown error when trying to delete {fpath} from vpn shared folder")
                        logger.error(repr(e))      
            
            else:
                sleep(1)

    
