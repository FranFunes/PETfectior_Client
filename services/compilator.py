import json, threading, logging, os, requests
from time import sleep
from datetime import datetime
import numpy as np
from services.helper_funcs import delete_series
from pydicom import Dataset

# Configure logging
logger = logging.getLogger('__main__')

class Compilator():

    """
    
        This class is used to read DICOM SOP Instances (images) received by the StoreSCP
        and compile them in whole series. Instances are read from input_queue.
        The number of instances present in each series is found through a dedicated function.
        
        When the process has been sleeping during a predefined time, each series is checked to
        find if it should be put in the output queue, discarded or keep waiting. This is 
        done by another predefined function.
    
    """

    def __init__(self, input_queue, output_queue, task_manager, server_url, series_timeout = 30, 
                 min_instances_in_series = 47, slice_gap_tolerance = 0.025):
              
        self.input_queue = input_queue      
        self.output_queue = output_queue
        self.task_manager = task_manager
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
            · Reads elements from the input queue.
            · Instances are grouped by its SeriesInstanceUID and source device.
            · If the instance was already received for the series, it is assigned to a new
              occurrence of the same series (to handle the case when user sends the same series multiple times).
            
            When there are no elements in the queue, sends each series to an independent function that checks it for
            completeness. Then:
            · If the series is complete, it is put in the output queue.
            · If not, checks if the waiting period for this series has expired and deletes it in that case. Else, waits for
              more instances.                

        """
        # Initialize placeholders for received data       
        series = {} 

        # Inactive timer to know if series status should be checked or not.
        inactive_time = 0        

        while not self.stop_event.is_set() or not self.input_queue.empty():
        
            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():

                # Reset inactivity timer
                inactive_time = 0

                # Read element from queue
                queue_element = self.input_queue.get()
                dataset = queue_element['dataset']
                fname = queue_element['filename']
                series_uid = dataset.SeriesInstanceUID
                sop_uid = dataset.SOPInstanceUID
                recon_settings = queue_element['recon_ds']
                ip = queue_element['address']
                ae_title = queue_element['ae_title']

                # Check if there exists a known device with this ip address.
                with open(os.path.join("data",'peers.json')) as jsonfile:
                    peers = json.load(jsonfile)
                try:
                    source = [key for key, device in peers.items() if device['address'] == ip][0]
                except IndexError:
                    source = None
                    
                # Check if this SOP should be appended to an existing or new series
                matching_rows = {key:value for key,value in series.items() if 
                                 value['series_uid'] == series_uid and
                                 value['requestor_ip'] == ip and
                                 sop_uid not in value['sops']}

                if not matching_rows:
                    uid_exists = any({key:value for key,value in series.items() if value['series_uid'] == series_uid})
                    if not uid_exists:
                        logger.info(f"New series {series_uid} received from {ip}")
                    else:                        
                       logger.info(f"Instance {sop_uid} already in series {series_uid}. Creating new occurrence of this series.")

                    # Append to new series                    
                    expected = self.instances_in_series(dataset)
                    destinations = self.set_destinations(ip, ae_title)
                    timing = datetime.now()
                    task_id = timing.strftime('%Y%m%d%H%M%S%f')[:-2]
                    row = {'series_uid': series_uid, 'sops':[sop_uid], 'datasets': [dataset], 'recon_settings':[recon_settings],
                           'timing_first': timing, 'timing_last': timing, 'expected': expected, 'filenames': [fname], 'source': source,
                           'requestor_ip': ip, 'requestor_aet': ae_title, 'destinations': destinations}
                    series[task_id] = row

                    # Create new task in task manager
                    try:
                        studydate = datetime.strptime(dataset.StudyDate,'%Y%m%d').strftime('%d/%m/%Y')
                    except:
                        studydate = 'unknown'
                    task_data = {
                        'task_id': task_id,
                        'source': source or ip,
                        'PatientName': str(dataset.get('PatientName','unknown')),
                        'StudyDate': studydate,
                        'description': dataset.get('SeriesDescription', 'unknown'),
                        'started': timing.strftime('%d/%m/%Y %H:%M:%S'),
                        'updated': timing.strftime('%d/%m/%Y %H:%M:%S'),
                        'status': 'receiving',
                        'imgs': f"1/{expected or ' '}",
                        'destinations': '/'.join(destinations)
                    }
                    self.task_manager.manage_task(action = 'new', task_data = task_data)                                        

                else:
                    # Append to existing series
                    id, matching = list(matching_rows.items())[0]
                    matching['sops'].append(sop_uid)
                    matching['datasets'].append(dataset)
                    matching['filenames'].append(fname)
                    matching['recon_settings'].append(recon_settings)
                    matching['timing_last'] = datetime.now()
                    self.task_manager.manage_task(action = 'update', task_id = id, task_data = {'imgs': f"{len(matching['datasets'])}/{matching['expected'] or ' '}"})
                    
                    # Update source if it changed from None
                    if not matching['source'] and source:
                        matching['source'] = source                                                             
                        self.task_manager.manage_task(action = 'update', task_id = id, task_data = {'source': source})
                            
                    logger.debug(f"Append instance {sop_uid} to series {row['series_uid']}")
            
            # If there are no elements in the queue and the thread has been inactive for 5 seconds, check
            # series status.
            elif inactive_time >= 5 and any(series):

                logger.info(f"Inactive, checking series...")
                # Reset inactivity timer
                inactive_time = 0
                to_delete = []
                for key, row in series.items():

                    # Check series status
                    status = self.series_status(row['datasets'], row['expected'], row['timing_last'])

                    if status == 'abort':
                        logger.info(f"Series {row['series_uid']} timed out") 
                        to_delete.append(key)
                        self.task_manager.manage_task(action = 'update', task_id = key, task_data = {'status': 'failed - timeout'})        
                    
                    elif status == 'wait':
                        logger.info(f"Waiting for series {row['series_uid']} with {len(row['sops'])} instances to complete.")

                    elif status == 'completed':

                        # Update valid destinations for the processed series.
                        try:
                            row['destinations'] = self.set_destinations(row['requestor_ip'], row['requestor_aet'])
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
                                delete_series(row['filenames'])
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
                            to_delete.append(key)
                
                # Delete series
                for key in to_delete:
                    del series[key]
            else:
                sleep(1)
                inactive_time += 1
                        
    def set_destinations(self, ip, aet):

        destinations = []
        
        # Check if there are any fixed destinations configured
        try:
            with open(os.path.join("data",'peers.json'),'r') as jsonfile:
                devices = json.load(jsonfile)
            fixed_dest = [key for key, value in devices.items() if value['is_destination']]
            destinations.extend(fixed_dest)
        except Exception as e:
            logger.error(f"peers file could not be read.")
            logger.error(repr(e))
        else:
            # Check if mirror mode is activated and there are any devices matching the requestor's IP
            try:
                with open(os.path.join("data","local.json"),'r') as jsonfile:
                    mirror_mode = json.load(jsonfile)['mirror_mode']
            except:
                logger.error(f"config file could not be read.")
                logger.error(repr(e))
            else:
                if mirror_mode:                    
                    matching_ip = {key:value for key, value in devices.items() if value['address'] == ip}
                    
                    if len(matching_ip) == 1:
                        destinations.extend(matching_ip.keys())
                    else:
                        # If there are more than one devices that matches IP, check if any matches both IP and AE title
                        matching_aet = {key:value for key, value in matching_ip.items() if value['ae_title'] == aet}
                        if not matching_aet:
                            destinations.extend(matching_ip.keys())
                        else:
                            destinations.extend(matching_aet.keys())
        
        # Remove duplicated
        destinations = list(set(destinations))

        return destinations

    def series_status(self, datasets, n_imgs, last_received):

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