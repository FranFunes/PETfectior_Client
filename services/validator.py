import json, threading, logging, os, requests, pickle
from time import sleep
from datetime import datetime
import numpy as np
from services.helper_funcs import delete_series
from pydicom import Dataset

from app_pkg import application, db
from app_pkg.db_models import Device, Task, Series, Instance, task_instance, Source

# Configure logging
logger = logging.getLogger('__main__')

class Validator():

    """
    
        This class is used to verify that a Task is ready to be packed and uploaded to the server.
        It checks three conditions:
        - The Task has at least one destination assigned
        - The dicom headers for the instances associated with the task have enough information to
        be processed by the server.
        - A model exists in the server for the recon settings of this task.
                
    
    """

    def __init__(self, input_queue, output_path, task_manager, server_url, next_step = 'processor', series_timeout = 30, 
                 min_instances_in_series = 47, slice_gap_tolerance = 0.025):
              
        self.input_queue = input_queue   
        self.next_step = next_step   
        self.task_manager = task_manager
        self.output_path = output_path
        self.server_url = server_url
        self.series_timeout = series_timeout
        self.min_instances_in_series = min_instances_in_series
        self.slice_gap_tolerance =  slice_gap_tolerance

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
        # Initialize placeholders for received data (harder to keep in the database)      
        task_data = {} 

        # Inactive timer to know if task status should be checked or not.
        inactive_time = 0        

        while not self.stop_event.is_set() or not self.input_queue.empty():
        
            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():

                # Reset inactivity timer
                inactive_time = 0

                # Read element from queue
                queue_element = self.input_queue.get()
                dataset = queue_element['dataset']
                series_uid = dataset.SeriesInstanceUID
                sop_uid = dataset.SOPInstanceUID
                recon_settings = queue_element['recon_ds']
                ip = queue_element['address']
                ae_title = queue_element['ae_title']
                timing = datetime.now()

                # Record this source in the database if it doesn't exist
                src_id = f"{ae_title}@{ip}"
                source = Source.query.get(src_id).first()
                if not source:
                    source = Source(identifier = src_id)
                    db.session.add(source)
                    
                # Check if this SOP should be appended to an existing or new Task.                
                matching_task = (Task.query.join(Source).filter_by(identifier=src_id).
                                join(Series).filter_by(SeriesInstanceUID = series_uid).
                                outerjoin(task_instance).outerjoin(Instance).
                                filter(Instance.SOPInstanceUID != sop_uid)).first()
                
                if not matching_task:

                    # Create a new task          
                    logger.info('creating new task')
                    task_id = timing.strftime('%Y%m%d%H%M%S%f')[:-2]

                    # Create new Task in the database
                    task = Task(
                        task_id = task_id,
                        started = timing,
                        updated = timing,
                        current_step = 'compilator',
                        current_step_filename = '',
                        status_msg = 'receiving',
                        state = 0,
                        expected_imgs = self.instances_in_series(dataset),
                        task_series = Series.query.get(series_uid),
                        destinations = self.set_destinations(source),
                        instances = [Instance.query.get(sop_uid)],
                        task_source = source
                    )
                    db.session.add(task)
                    logger.info(f'created new task {task}')
                      
                    # Keep data that can't be stored in the database in a dedicated dict
                    row = {'datasets': [dataset], 'recon_settings':[recon_settings]}
                    task_data[task_id] = row
                else:
                    # Append to existing series                    
                    logger.debug(f"Appending instance {sop_uid} to task {matching_task}")
                    matching_task.updated = timing
                    matching_task.instances.append(Instance.query.get(sop_uid))
                    task_data[matching_task.id]['datasets'].append(dataset)
                    task_data[matching_task.id]['recon_settings'].append(recon_settings)
            
            # If there are no elements in the queue and the thread has been inactive for 5 seconds, check
            # tasks status
            elif inactive_time >= 5 and any(series):

                logger.info(f"Inactive, checking series...")
                # Reset inactivity timer
                inactive_time = 0
                for task in Task.query.all():
                    
                    # Check task status
                    status = self.task_status(task_data[task.id]['datasets'], 
                                              task.expected, 
                                              task.updated)

                    if status == 'abort':
                        logger.info(f"Task {task.id} timed out")
                        task.status_msg(f"Failed - timed out")
                        task.state = -1                        
                    
                    elif status == 'wait':
                        logger.info(f"Waiting for task {task.id} with {len(task.instances)} instances to complete.")

                    elif status == 'completed':

                        logger.info(f"Task {task.id} completed.")
                        
                        # Write task_data to a file
                        fname = os.path.join(self.output_path, task.id + '_compilator.pickle')
                        try:
                            with open(fname, 'w') as fname:
                                pickle.dump(task_data[task.id], fname, protocol=pickle.HIGHEST_PROTOCOL)
                            logger.info(f"Task {task.id} data written to file.")
                        except Exception as e:
                            logger.error(f"Task {task.id} data write failed. {repr(e)}")
                            task.status_msg(f"Failed - write error")  
                            task.state = -1    
                        else:
                            # Pass to next step
                            task.current_step = self.next_step
                            task.current_step_filename = fname
                            self.task_manager.done(task.id)

                        






                        # Update valid destinations for the processed series.
                        try:
                            task.destinations.extend(self.set_destinations(row['requestor_ip'], row['requestor_aet']))
                            self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'destinations': '/'.join(row['destinations'])})
                        except Exception as e:
                            logger.error(f"Could not update destinations")
                            logger.error(repr(e))                            

                        if not row['destinations']:
                            logger.info(f"Series {row['series_uid']} with {len(row['filenames'])} instances completed, but destination is unknown .")
                            self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'destination not set!'})  

                        # Check if dicom information is complete
                        elif not self.check_dicom_parameters(row['recon_settings'][0]):
                            # Alert in task_manager
                            logger.info(f"Series {row['series_uid']} completed but there are missing dicom information.")
                            self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'failed - missing info'})
                            to_delete.append(key)   
                            delete_series(row['filenames'])
                        
                        else:
                            # Keep only one dataset as recon_setting (the one with the highest ActualFrameDuration)
                            try:
                                max_idx = np.argmax([ds.ActualFrameDuration for ds in row['recon_settings']])
                                max_value = row['recon_settings'][max_idx].ActualFrameDuration
                                logger.info(f"Index {max_idx} has max ActualFrameDuration of {max_value}")
                            except Exception as e:
                                max_idx = 0
                                logger.error(f"Could not select max ActualFrameDuration. Using first element")
                                logger.error(repr(e))                                
                            row['recon_settings'] = row['recon_settings'][max_idx]
                            
                            # Find SpacingBetweenSlices information
                            try:
                                z = [ds.ImagePositionPatient[2] for ds in row['datasets']]
                                spacing = np.diff(np.sort(z)).mean()
                                row['recon_settings'].SpacingBetweenSlices = spacing
                                logger.info(f"spacing {spacing:.2f}")
                            except Exception as e:
                                logger.error(f"series {row['series_uid']} completed but spacing could not be calculated")
                                logger.error(repr(e))
                                self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'failed - slice spacing'})
                                
                            else:
                                # Check if a model exists in the remote processing server for this model
                                self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'checking'})  
                                valid_model = self.check_model(row['recon_settings'])
                                if valid_model:
                                    # Put this series in the output queue
                                    content = {'filenames': row['filenames'], 'task_id': key, 
                                            'recon_settings':row['recon_settings'], 'source':row['source']}
                                    self.output_queue.put(content)
                                    logger.info(f"series {row['series_uid']} completed. {len(content['filenames'])} instances put in queue.")
                                    
                                    # Update status in task_manager
                                    self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'compiled'})    
                                else:
                                    # Alert in task_manager
                                    logger.info(f"series {row['series_uid']} completed but no model found for this recon settings {row['recon_settings']}.")
                                    self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'failed - no model'})    
                                    delete_series(row['filenames'])
                            
                
            else:
                sleep(1)
                inactive_time += 1
                        
    def set_destinations(self, source):

        destinations = []
        
        # Add devices with "is_destination" == True
        destinations.extend(Device.query.filter_by(is_destination = True).all())        
        # Check if mirror mode is activated and there are any devices matching the source IP/AET
        mirror_mode = os.environ['MIRROR_MODE_ENABLED'] == 'True'
        aet, ip = source.identifier.split('@')
        if mirror_mode:                    
            matching_ip = Device.query.filter_by(address = ip)            
            if len(matching_ip) == 1:
                destinations.extend(matching_ip)
            else:
                # If there are more than one devices that matches IP, check if any matches both IP and AE title
                matching_aet = Device.query.filter_by(address = ip, ae_title = aet)
                if not matching_aet:
                    destinations.extend(matching_ip)
                else:
                    destinations.extend(matching_aet)
        
        # Remove duplicated
        destinations = list(set(destinations))

        return destinations

    def task_status(self, datasets, n_imgs, last_received):

        """
        
            Checks the received status of a series. The status can be one of four:
            · 'completed': the series is complete and can be packed to further processing.
            · 'wait': the series is incomplete, but more time should be given to receive the missing instances.
            · 'abort': the series is incomplete and should be discarded.
            · 

            Args:
            · datasets: a list of pydicom datasets, corresponding to the same series, and with no duplicated instances.
            · n_imgs: the number of images expected for this series.
            · last_received: datetime object with the moment when the last instance of the series was received.
        
        """

        series_timed_out = (datetime.now() - last_received).total_seconds() > self.series_timeout
                
        if n_imgs and n_imgs == len(datasets):
            if n_imgs >= self.min_instances_in_series:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances completed by n_imgs criteria.")
                status = 'completed'
            elif series_timed_out:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria and waiting period has expired.")
                status = 'abort'
            else:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria, but we can wait for more instances.")
                status = 'wait'
            
        elif self.check_for_contiguity(datasets):

            logger.info("series {datasets[0].SeriesInstanceUID} meets contiguity criteria.")

            if series_timed_out:
                if len(datasets) >= self.min_instances_in_series:
                    logger.info(f"series {datasets[0].SeriesInstanceUID} completed by contiguity criteria.")
                    status = 'completed'
                else:
                    logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria and waiting period has expired.")
                    status = 'abort'
            else:
                if len(datasets) >= self.min_instances_in_series:
                    logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances meets minimum instances criteria, but we can wait for more instances.")
                else:
                    logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet minimum instances criteria, but we can wait for more instances.")
                status = 'wait'

        else:
            if series_timed_out:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances didn't meet contiguity criteria and waiting period has expired.")
                status = 'abort'
            else:
                logger.info(f"series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances doesn't meet contiguity criteria but we can wait for more instances.")
                status = 'wait'

        return status
    
    def check_for_contiguity(self, datasets):

        """
        
        Checks if a set of dicom images have regular spatial sampling in the z direction.

        Args:
            · datasets: a list of pydicom.datasets corresponding to the same series.
        
        """
        
        logger.info(f"checking for series {datasets[0].SeriesInstanceUID} with {len(datasets)} instances")

        slice_positions = [ds.ImagePositionPatient[2] for ds in datasets]
                
        slice_positions = np.sort(slice_positions)        
        slice_gaps = np.diff(slice_positions)               
        
        # Check if minimin and maximum slice gaps are within tolerance      
        lim_inf =  (1 - self.slice_gap_tolerance) * slice_gaps.mean()
        lim_sup =  (1 + self.slice_gap_tolerance) * slice_gaps.mean()

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

    def check_model(self, ss):
        
        if not os.environ["SERVER_INTERACTION"] == "True":
            return True
        try:
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
            post_rsp = requests.post('http://' + self.server_url + '/check_model', json = data)
            if not post_rsp.json()['response']:
                logger.error(f"model not found.")                
            else:
                logger.info(f"model found.")  

            return post_rsp.json()['response']

        except Exception as e:
            
            logger.error(f"error " + repr(e))  
            return False