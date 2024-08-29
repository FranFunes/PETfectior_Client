import logging, threading, os, traceback
from time import sleep
from shutil import copy
from app_pkg import application, db
from app_pkg.db_models import Task, AppConfig

# Configure logging
logger = logging.getLogger('__main__')

class SeriesDownloader():

    def __init__(self, input_queue, next_step = 'unpacker'):

        self.input_queue =  input_queue
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
            return "Downloader can't be started: database not available"
        
        # Create the output directory if it doesn't exist
        try:
            os.makedirs(config.download_path, exist_ok = True)
            logger.debug('output directory created successfully')
        except:
            logger.error('output directory could not be created')  
            return "Downloader can't be started: output directory can't be created"
        # Check if the shared folder exists
        try:             
            assert os.path.isdir(config.shared_mount_point)
            
            # Create "processed" folder if it doesn't exist
            os.makedirs(os.path.join(config.shared_mount_point, 'processed'), exist_ok = True)

            if not self.get_status() == 'Corriendo':
                # Start the thread
                self.main_thread = threading.Thread(target = self.main, args = ())        
                self.main_thread.start()
                logger.info('started')
                return "Downloader inició exitosamente"
            else:
                return "Downloader ya está corriendo"
            
        except AssertionError:
            logger.error(f"Downloader can't start ({config.shared_mount_point} is not a valid directory or is not existent)")
            return f"Downloader can't start ({config.shared_mount_point} is not a valid directory or is not existent)"
        except Exception as e:
            logger.error(f"Downloader can't start ({os.path.join(config.shared_mount_point, 'processed')} can't be created)")
            logger.error(traceback.format_exc())
            return f"Downloader can't start ({os.path.join(config.shared_mount_point, 'processed')} can't be created)"

    
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
            return "Downloader detenido"
        except Exception as e:
            logger.error("Downloader could not be stopped")
            logger.error(traceback.format_exc())
            return "Downloader no pudo ser detenido"

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
            with application.app_context():
                if not self.input_queue.empty():
                    task = Task.query.get(self.input_queue.get())
                    config = AppConfig.query.first()

                    # Reconstruct the filename from task_id and client_id
                    fname = task.id + '_' + config.client_id + '.zip'
                    task.status_msg = 'descargando'
                    db.session.commit()

                    # Download fname                
                    try:
                        fpath = os.path.join(os.path.join(config.shared_mount_point, 'processed'), fname)
                        local_fname = os.path.join(config.download_path, fname)                    
                        logger.info(f"downloading {fpath} over vpn")     
                        db.session.commit()               
                        copy(fpath, local_fname)
                    except FileNotFoundError as e:
                        logger.error('Download error: file ' + fpath + ' not found')
                        task.status_msg = 'descarga fallida'
                        task.full_status_msg = """Error al descargar el archivo procesado del servidor remoto: la aplicación no
                        recibió los archivos esperados del servidor remoto. Verificar los mensajes de error del Downloader para
                        mayor información"""                        
                        task.step_state = -1                        
                    except Exception as e:
                        logger.error('Unknown error during download')
                        logger.error(traceback.format_exc())
                        task.status_msg = 'descarga fallida'
                        task.full_status_msg = """Error desconocido al descargar el archivo procesado del servidor remoto.
                        Mensaje de error completo:\n\n """ + repr(e)
                        task.step_state = -1
                    else:                    
                        # If download was successful, flag step as completed
                        task.current_step = self.next_step
                        task.status_msg = 'descarga ok'
                        task.step_state = 1
                        logger.info(f"{fname} downloaded successfully")
                        # Delete file from vpn shared folder
                        try:
                            os.remove(fpath)
                            logger.info(f"{fpath} deleted from vpn shared folder")
                        except Exception as e:
                            logger.error(f"Unknown error when trying to delete {fpath} from vpn shared folder")
                            logger.error(traceback.format_exc()) 

                    db.session.commit()
            
                else:
                    sleep(1)

    
