import threading, logging
from time import sleep
from datetime import datetime
import numpy as np
from pydicom import Dataset

from app_pkg import application, db
from app_pkg.db_models import Task, Series, Instance, Source, AppConfig
from app_pkg.functions.db_store_handler import extract_from_dataset

# Configure logging
logger = logging.getLogger('__main__')

class Compilator():

    """
    
        This class is used to read DICOM SOP Instances (images) received by the StoreSCP
        and compile them in whole series. Instances are read from input_queue.
        The number of instances present in each series is found through a dedicated function.
        For each series received, a Task is created in the database.
        
        When the process has been sleeping during a predefined time, each task is checked to
        find if it should be put in the output queue, discarded or keep waiting.
    
    """

    def __init__(self, input_queue, next_step = 'validator'):        
        
        self.input_queue = input_queue   
        self.next_step = next_step   

    def start(self):

        """
        
            Starts the process thread.            

        """
                
        if not self.get_status() == 'Running':
            # Set an event to stop the thread later 
            self.stop_event = threading.Event()

            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, 
                                                args = (), name = 'Compilator')        
            self.main_thread.start()
            logger.info('Compilator started')
            return 'Compilator started successfully'
        else:
            return 'Compilator is already running'

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("stopped")
            return "Compilator stopped"
        except:
            logger.info("stopped")
            return "Compilator could not be stopped"


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
            · Reads elements from the input queue, appends the SOPInstanceUID to a list
            of know SOPs and assigns it to a new or existent Task in the database, with the 
            following criteria:
                - If the instance was not in the list, and there is an existent task associated
                with its SeriesInstanceUID and with the same source device, append the instance
                to this Task.
                - Else, create a new Task and append the instance to it.
            
            When there are no elements in the input queue, each Task is sent to an independent
            function that checks it for completeness. Then:
            · If the series is complete, the output data is written to a file and passed to the
             task_manager, and the Task state is updated in the database.
            · If not, checks if the waiting period for this Task has expired and signals it in
            the database it in that case. Else, waits for more instances.               

        """
        # Inactive timer to know if task status should be checked or not.
        inactive_time = 0                

        while not self.stop_event.is_set() or not self.input_queue.empty():
            
            try:

                with application.app_context():
                    # If there are any elements in the input queue, read them.
                    if not self.input_queue.empty():
                        
                        # Reset inactivity timer
                        inactive_time = 0

                        # Read element from queue
                        queue_element = self.input_queue.get()
                        dataset = queue_element['dataset']
                        series_uid = dataset.SeriesInstanceUID
                        sop_uid = dataset.SOPInstanceUID
                        ip = queue_element['address']
                        ae_title = queue_element['ae_title']
                        timing = datetime.now()

                        # Record this source in the database if it doesn't exist
                        src_id = f"{ae_title}@{ip}"
                        source = Source.query.get(src_id)
                        if not source:
                            source = Source(identifier = src_id)
                            db.session.add(source)
                            
                        # Check if this SOP should be appended to an existing or new Task.          
                        tasks = (Task.query.filter_by(current_step = 'compilator').
                                filter_by(step_state = 0). 
                                filter_by(series = series_uid).
                                join(Source).filter_by(identifier=src_id)).all()
                        matching_task = None
                        i = Instance.query.get(sop_uid)
                        for task in tasks:
                            if not i in task.instances:
                                matching_task = task
                                break
                        
                        if not matching_task:

                            # Create a new task          
                            logger.info('creating new task')
                            task_id = timing.strftime('%Y%m%d%H%M%S%f')[:-2]

                            # Create new Task in the database
                            task = Task(
                                id = task_id,
                                started = timing,
                                updated = timing,
                                current_step = 'compilator',
                                status_msg = 'receiving',
                                step_state = 0,
                                expected_imgs = self.instances_in_series(dataset),
                                task_series = Series.query.get(series_uid),
                                instances = [Instance.query.get(sop_uid)],
                                task_source = source
                            )
                            db.session.add(task)
                            logger.info(f'created new task {task}')                        
                        else:
                            # Append to existing series                    
                            logger.debug(f"Appending instance {sop_uid} to task {matching_task}")
                            matching_task.instances.append(Instance.query.get(sop_uid))

                        db.session.commit()
                        
                    # If there are no elements in the queue and the thread has been inactive for 5 seconds, check
                    # tasks status
                    elif inactive_time >= 5:

                        logger.debug(f"Inactive, checking tasks status...")
                        # Reset inactivity timer
                        inactive_time = 0
                        for task in Task.query.filter((Task.current_step == 'compilator')&(Task.step_state==0)).all():
                            
                            # Check task status
                            try:
                                datasets, recon_settings = self.fetch_task_data(task.id)
                            except Exception as e:
                                logger.error(f"fetch_task_data failed for task {task.id}")
                                logger.error(repr(e))
                                task.status_msg = 'Failed - task data not found'
                                task.full_status_msg = """The original DICOM files of this task were not found. Please delete
                                the task and start it again by sending the original DICOM series from the remote device."""
                                task.step_state = -1    
                            else:
                                status, msg = self.task_status(datasets, 
                                                        task.expected_imgs, 
                                                        task.updated)
                                if status == 'abort':
                                    logger.info(f"Task {task.id} timed out")
                                    task.status_msg = 'Failed - timed out'
                                    task.full_status_msg = msg
                                    task.step_state = -1                        
                                
                                elif status == 'wait':
                                    logger.info(f"Waiting for task {task.id} with {len(task.instances)} instances to complete.")

                                elif status == 'completed':

                                    # From task_data, keep the required for the next step only
                                    recon_settings = self.summarize_data(recon_settings, datasets)
                                    
                                    # Write task_data to the database and pass the task to the next step
                                    task.recon_settings = recon_settings.to_json()
                                    task.current_step = self.next_step
                                    task.step_state = 1
                                    logger.info(f"Task {task.id} completed.")                       
                        
                        db.session.commit()
                    else:
                        sleep(1)
                        inactive_time += 1     
            except Exception as e:
                logger.error("error in main loop.")
                logger.error(repr(e))
                            

    def task_status(self, datasets, n_imgs, last_received):

        """
        
            Checks the received status of a task. The status can be one of four:
            · 'completed': the task is complete and can be packed to further processing.
            · 'wait': the task is incomplete, but more time should be given to receive the missing instances.
            · 'abort': the task is incomplete and should be discarded.
            · 

            Args:
            · datasets: a list of pydicom datasets, corresponding to the same series, and with no duplicated instances.
            · n_imgs: the number of images expected for this series.
            · last_received: datetime object with the moment when the last instance of the series was received.
        
        """
        config = AppConfig.query.first()
        min_instances = config.min_instances_in_series
        timeout = config.series_timeout
        series_timed_out = (datetime.now() - last_received).total_seconds() > timeout

                
        if n_imgs and n_imgs == len(datasets):
            if n_imgs >= min_instances:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances completed by n_imgs criteria.")
                return 'completed', ''
            elif series_timed_out:
                msg = f"""Only {len(datasets)} images were received after a waiting period of {timeout} seconds. 
                Only series with {min_instances} or more images can be processed."""
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria and waiting period has expired.")
                return 'abort', msg
            else:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria, but we can wait for more instances.")
                return 'wait', ''
        
        if series_timed_out:
            if len(datasets) <  min_instances:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria and waiting period has expired.")
                msg = f"""Only {len(datasets)} images were received after a waiting period of {timeout} seconds. Only series with {min_instances}
                or more images can be processed."""
                return 'abort', msg            
            if self.check_for_contiguity(datasets):
                logger.info(f"series {datasets[0].SeriesInstanceUID} completed by contiguity criteria.")
                return 'completed',''
            else:
                msg = f"""The series can't be processed because separation between consecutive slices
                is greater than {config.slice_gap_tolerance} (or there are missing slices)"""
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances didn't meet contiguity criteria and waiting period has expired.")
                return 'abort', msg
        else:            
            logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} waiting for more instances.")      
            return 'wait', ''
    
    def check_for_contiguity(self, datasets):

        """
        
        Checks if a set of dicom images have regular spatial sampling in the z direction.

        Args:
            · datasets: a list of pydicom.datasets corresponding to the same series.
        
        """
        
        logger.info(f"checking for series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances")

        tol = AppConfig.query.first().slice_gap_tolerance

        slice_positions = [ds.ImagePositionPatient[2] for ds in datasets]
                
        slice_positions = np.sort(slice_positions)        
        slice_gaps = np.diff(slice_positions)               
        
        # Check if minimin and maximum slice gaps are within tolerance      
        lim_inf =  (1 - tol) * slice_gaps.mean()
        lim_sup =  (1 + tol) * slice_gaps.mean()

        return slice_gaps.min() >= lim_inf and slice_gaps.max() <= lim_sup    

             
    def instances_in_series(self, dataset: Dataset) -> int:        

        """

            Extracts the number of instances expected in a series. Returns None if
            it fails.

        """

        try:
            n_imgs = dataset.NumberOfSlices
            logger.info(f"{n_imgs} instances expected for series {dataset.SeriesInstanceUID}")      
        except AttributeError as e:
            logger.info(f"failed: " + repr(e))            
            n_imgs = None

        return n_imgs    
    
    def summarize_data(self, recon_settings, datasets):

        # From recon_settings, keep the dataset with the max ActualFrameDuration        
        try:
            max_idx = np.argmax([ds.ActualFrameDuration for ds in recon_settings])
            max_value = recon_settings[max_idx].ActualFrameDuration
            logger.debug(f"Index {max_idx} has max ActualFrameDuration of {max_value}")
        except Exception as e:
            max_idx = 0
            logger.error(f"Could not select max ActualFrameDuration. Using first element")
            logger.error(repr(e))                                
        recon_settings = recon_settings[max_idx]
        
        # Find SpacingBetweenSlices information
        z = [ds.ImagePositionPatient[2] for ds in datasets]
        spacing = np.diff(np.sort(z)).mean()
        recon_settings.SpacingBetweenSlices = spacing
        logger.debug(f"spacing {spacing:.2f}")

        return recon_settings
        

    def fetch_task_data(self, task_id):

        logger.info(f"fetching datasets for task {task_id}")
        t = Task.query.get(task_id)        
        dss, recon = list(zip(*[extract_from_dataset(inst.filename) for inst in t.instances]))        

        return list(dss), list(recon)