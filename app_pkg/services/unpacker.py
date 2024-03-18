import threading, logging, os
from shutil import unpack_archive, rmtree
from copy import deepcopy
from time import sleep
import numpy as np
from pydicom import dcmread
from pydicom.uid import generate_uid
from datetime import datetime
from app_pkg.functions.db_store_handler import store_dataset
from app_pkg.functions.helper_funcs import filter_3D


from app_pkg import application, db
from app_pkg.db_models import AppConfig, Task, Series, FilterSettings

# Configure logging
logger = logging.getLogger('__main__')

class SeriesUnpacker():

    def __init__(self, input_queue, next_step = 'store_scu'):

        self.input_queue = input_queue
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
            return "Unpacker can't be started: database not available"    

        # Create temporary directory if it does not exist.
        try:
            os.makedirs(config.unzip_dir, exist_ok = True)
            logger.info(f'destination {config.unzip_dir} directory created successfully')
        except:
            logger.error(f'destination {config.unzip_dir} directory could not be created')
            return "Unpacker can't be started: storage access error"
         
        if not self.get_status() == 'Running':
            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, args = ())        
            self.main_thread.start()
            logger.info('Unpacker started')
            return "Unpacker started successfully"
        else:
            return "Unpacker is already running"


    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("SeriesUnpacker stopped")
            return "SeriesUnpacker stopped"            
        except Exception as e:
            logger.error("SeriesUnpacker stop failed")
            logger.error(repr(e))
            return "SeriesUnpacker could not be stopped"

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
            with application.app_context():
                    
                # If there are any elements in the input queue, read them.
                if not self.input_queue.empty():
                    # Get zip filename and task id from the queue
                    task = Task.query.get(self.input_queue.get())
                    config = AppConfig.query.first()
                    templates = [dcmread(i.filename) for i in task.instances]  

                    filename = os.path.join(config.download_path, task.id + '_' + config.client_id + '.zip')

                    # Build zip filename
                    zip_fname = os.path.splitext(os.path.basename(filename))[0]               

                    # Decompress files                
                    extract_dir = os.path.join(config.unzip_dir, zip_fname)
                    logger.info(f"Decompressing {filename} to {extract_dir}")
                    task.status_msg = 'decompressing'    
                    db.session.commit()
                    try:
                        unpack_archive(filename, extract_dir)
                        logger.info(f"{filename} decompressed successfully")
                        task.status_msg = 'decompression ok'
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Could not decompress file {filename}")
                        logger.error(repr(e))
                        task.status_msg = 'decompression failed'     
                        task.step_state = -1                   
                    else:                        
                        # List decompressed files
                        filelist = os.listdir(extract_dir)

                        # Apply postfilters
                        task.status_msg = 'applying postfilters'
                        db.session.commit()                        
                        try:
                            voxel_size = np.array([templates[0].PixelSpacing[0],templates[0].PixelSpacing[1],templates[0].SliceThickness])
                            series = self.apply_postfilter(extract_dir, templates[0], voxel_size)
                        except FileNotFoundError as e:
                            logger.error(f"Failed when reading {extract_dir}")
                            logger.error(repr(e))                                                        
                            task.status_msg = f"failed - .npy not found"
                            task.step_state = -1 
                        except Exception as e:
                            logger.error(f"Failed when filtering {extract_dir}")
                            logger.error(repr(e))                                                        
                            task.status_msg = f"failed - postfilter" 
                            task.step_state = -1
                        else:
                            task.status_msg = 'building dicoms' 
                            db.session.commit()                            
                            success = 0
                            stored_ok = 0
                            for ss in series:
                                # Build dicom files
                                try:
                                    series_uid, datasets = self.build_dicom_files(ss, templates)
                                    # Add datasets to the database 
                                    for ds in datasets:
                                        stored_ok += store_dataset(ds, 'incoming') == 0
                                    # Link this series as a result for this task
                                    s = Series.query.get(series_uid)
                                    task.result_series.append(s)
                                    success += 1
                                    logger.info(f"Building dicoms for {extract_dir} successful")
                                except Exception as e:
                                    logger.error(f"Failed when building dicoms for {extract_dir}")
                                    logger.error(repr(e))

                            logger.info(f"{stored_ok} dicoms stored succesfully")                        
                            task.status_msg = f"building dicoms {success}/{len(series)}" 
                            db.session.commit()

                            # Check if all the expected instances have been correctly stored
                            # in the database
                            if stored_ok == len(series) * len(task.instances):
                                # Flag step as completed
                                logger.info(f"{task.id}: all expected instances succesfully stored in database")                              
                                task.current_step = self.next_step
                                task.step_state = 1    
                                task.status_msg = f"storing results ok"

                                # Delete temporary files
                                os.remove(filename)
                                rmtree(extract_dir)
                            else:
                                # Flag step as failed
                                logger.info(f"{task.id}: not all expected instances stored")
                                logger.info(f"{task.id}: expected {len(series) * len(task.instances)}, stored {stored_ok}")
                                task.status_msg = f"failed - dicom storage failed"                             
                                task.step_state = -1    

                    db.session.commit()
                else:
                    sleep(1)

    def apply_postfilter(self, extract_dir, original_series, voxel_size):

        # Load and process voxels
        try:
            v = np.load(os.path.join(extract_dir, 'denoised.npy'))
        except Exception as e:
            logger.error(f"Failed when loading voxels from {os.path.join(extract_dir, 'denoised.npy')}")
            logger.error(repr(e))
            raise FileNotFoundError
        
        try:            
            noise = np.load(os.path.join(extract_dir, 'noise.npy'))            
        except Exception as e:
            logger.error(f"Failed when loading noise from {os.path.join(extract_dir, 'noise.npy')}")
            logger.error(repr(e))
            raise FileNotFoundError
        
        try:
            with application.app_context():
                recons = [r for r in FilterSettings.query.all() if r.enabled]            
            assert recons
        except: 
            return [{'voxels': v,
                     'series_description':'PETFECTIOR',
                     'series_number':1001}]
        # Only apply filter settings valid for this pet model
        recons = [r for r in recons if r.model == 'all' or r.model == original_series.ManufacturerModelName]
        if not recons:
            raise ValueError(f'No postfilter settings found for pet model {original_series.ManufacturerModelName}')
        series = []

        series_description = original_series.SeriesDescription
        for r in recons:
            voxels = v + r.noise/100 * noise
            voxels = filter_3D(voxels, r.fwhm, voxel_size)
            series.append({
                'voxels': voxels,
                'series_description': series_description + '_' + r.description if r.mode=='append' else r.description,
                'series_number':r.series_number
            })
        return series

    def build_dicom_files(self, input_dict, templates):

        v = input_dict['voxels']

        # Create new deep copy of templates
        datasets = [deepcopy(ds) for ds in templates]

        # Transpose to make for loops easier
        v = np.array(v).transpose([2,1,0])
        # Calculate rescale slopes for each slice
        slopes = (v.max(axis = (1,2)) / (2**15 - 1)).reshape((v.shape[0],1,1))        
        # Normalize each slice to 2**16 - 1 as max value and convert to uint16
        v = (v / slopes).astype(np.uint16)          
            
        # Sort by slice location
        z = [ds.ImagePositionPatient[2] for ds in datasets]
        order = np.argsort(z)
        datasets = [datasets[idx] for idx in order]
        
        # Replace voxel values on templates
        for idx, ds in enumerate(datasets):
            ds.PixelData = v[idx].tobytes()
            ds.RescaleSlope = slopes[idx]

        # Use .npy file as SeriesDescription
        series_uid = generate_uid()
        timenow = datetime.now().strftime('%H%M%S')
        for ds in datasets:            
            ds.InstanceCreationTime = timenow
            ds.SOPInstanceUID = generate_uid()
            ds.ContentTime = timenow
            ds.SeriesInstanceUID = series_uid
            ds.SeriesNumber = input_dict['series_number']
            ds.SeriesDescription = input_dict['series_description']

        return [series_uid, datasets]




