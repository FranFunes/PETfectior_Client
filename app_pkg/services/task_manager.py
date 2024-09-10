import threading, logging, os, traceback
from time import sleep

from app_pkg import application, db
from app_pkg.db_models import Task
from app_pkg.functions.helper_funcs import process

# Configure logging
logger = logging.getLogger('__main__')

class TaskManager():

    """
    
        This thread finds the Tasks that are ready to initiate the next step
        and set them to continue.
        Arguments:
        - queues: a dictionary with keys equal to the name of each step in
            the processing pipeline. Each value is the corresponding input_queue 
            for that process.
    
    """

    def __init__(self, queues: dict):        
        
        self.input_queues = queues 

    def start(self):

        """
        
            Starts the process thread.            

        """
                
        if not self.get_status() == 'Corriendo':
            # Set an event to stop the thread later 
            self.stop_event = threading.Event()

            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, 
                                                args = (), name = 'task_manager')        
            self.main_thread.start()
            logger.info('task manager started')
            return 'Task Manager inició exitosamente'
        else:
            return 'Task Manager ya está corriendo'

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("stopped")
            return "Task Manager detenido"
        except:
            logger.info("stopped")
            return "Task Manager no pudo ser detenido"


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

        """
        
        A loop that continuously searches for those Task with step_state = 1.

        """
        
        while not self.stop_event.is_set():
            
            with application.app_context():
                # Find tasks with step_state = 1 (step completed) and
                # put them in the next step input queue
                try:
                    tasks = Task.query.filter_by(step_state = 1)
                except:
                    logger.error(f"can't access database")
                    logger.error(traceback.format_exc())
                    continue

                for task in tasks:
                    try:
                        # Update task_status
                        logger.info(f'passing task {task.id} to {task.current_step}')
                        task.step_state = 0
                        # Trigger next step by putting an element in its input queue
                        self.input_queues[task.current_step].put(task.id)
                        db.session.commit()
                    except:
                        logger.error(f"can't access database")
                        logger.error(traceback.format_exc())
                
                # If server interaction is disabled, simulate processing
                if not os.environ["SERVER_INTERACTION"] == "True":
                    try:
                        to_process = Task.query.filter_by(status_msg = 'procesando')
                    except:
                        logger.error(f"can't access database")
                        logger.error(traceback.format_exc())
                        continue
                    for task in to_process:
                        try:
                            task_id = task.id
                            process(task_id)
                            logger.info(f"simulated processing for task {task_id}")
                        except Exception as e:
                            logger.error(f"simulated processing failed")
                            logger.error(traceback.format_exc())
                
                if not tasks:
                    sleep(1)
           
