import logging, threading, os, json
from time import sleep
from shutil import copy

# Configure logging
logger = logging.getLogger('__main__')

class SeriesDownloader():

    def __init__(self, output_queue, task_manager, shared_mount_point, output_folder = 'SeriesToUnpack'):

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

        while not self.stop_event.is_set():

            # Read shared folder contents
            try:
                file_list = os.listdir(self.shared)
            except Exception as e:
                logger.error(f"Unknown error when trying to list {self.shared} folder from vpn storage")
                logger.error(repr(e))
                file_list = []

            if not file_list:
                logger.debug(f"shared folder empty")
            
            for file in file_list:

                # Check if the file name matches a task in the database
                fpath = os.path.join(self.shared, file)
                task_id = os.path.basename(fpath).split('_')[0]
                tasks_list = [task['task_id'] for task in self.task_manager.get_tasks_table()]    
                match = task_id in tasks_list                

                if not match:
                    logger.debug(f"file {fpath} does not match a task_id")
                else:
                    # Update info in frontend
                    self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'downloading'})

                    # Wait until filesize is not changing for 5 seconds                    
                    try:
                        waiting = self.static_file_size(fpath)
                    except:
                        logger.error('static file failed')
                        self.task_manager.manage_task(action = 'update', task_id = task_id, task_data = {'status': 'download failed'})
                    else:
                        # Download file                
                        try:
                            local_fname = os.path.join(self.output_folder, file)                    
                            logger.info(f"downloading {fpath} over vpn")                    
                            copy(fpath, local_fname)
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
                                logger.error(f"Unknown error when trying to delete {fpath} from cloud storage")
                                logger.error(repr(e))      
            
            sleep(5)

    def static_file_size(self, fpath):
        
        filesize = os.path.getsize(fpath)
        changed = True
        waiting = 0
        while changed:
            sleep(5)
            waiting += 5
            newsize = os.path.getsize(fpath)
            changed = newsize != filesize
            filesize = newsize
        
        logger.info(f"waiting time {waiting} seconds")

        return waiting
