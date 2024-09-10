import threading, logging, os, traceback
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
from app_pkg.db_models import AppConfig, Task, Series, FilterSettings, Radiopharmaceutical

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
         
        if not self.get_status() == 'Corriendo':
            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, args = ())        
            self.main_thread.start()
            logger.info('Unpacker started')
            return "Unpacker inició exitosamente"
        else:
            return "Unpacker ya está corriendo"


    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("SeriesUnpacker stopped")
            return "SeriesUnpacker detenido"            
        except Exception as e:
            logger.error("SeriesUnpacker stop failed")
            logger.error(traceback.format_exc())
            return "SeriesUnpacker no pudo ser detenido"

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
                            
                if not self.input_queue.empty():
                    task_id = self.input_queue.get()
                    with application.app_context():
                        reprocess = self.task_step_handler(task_id)
                    while reprocess and not self.stop_event.is_set():
                        logger.info(f'reprocessing {task_id}')   
                        with application.app_context():                     
                            reprocess = self.task_step_handler(task_id)
                        sleep(5)
                else:
                    sleep(1)

    def task_step_handler(self, task_id):
                
        try:
            task = Task.query.get(task_id)
            config = AppConfig.query.first()
            templates = [dcmread(i.filename) for i in task.instances]
        except:
            logger.error(f"task {task_id} status can't be updated")
            logger.error(traceback.format_exc())   
            return True 

        # Delete existent results series for this task
        try:
            for ss in task.result_series:
                db.session.delete(ss)
        except Exception as e:
            logger.error(f"Could not delete existent results")
            logger.error(traceback.format_exc())
            try:
                task.status_msg = 'falló - base de datos'     
                task.step_state = -1
                task.full_status_msg = """Ocurrió un error desconocido al intentar eliminar
                resultados preexistentes para esta tarea."""
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True  

        try:

            filename = os.path.join(config.download_path, task.id + '_' + config.client_id + '.zip')

            # Build zip filename
            zip_fname = os.path.splitext(os.path.basename(filename))[0]               

            # Decompress files                
            extract_dir = os.path.join(config.unzip_dir, zip_fname)
            logger.info(f"Decompressing {filename} to {extract_dir}")
            task.status_msg = 'descomprimiendo'    
            db.session.commit()

            unpack_archive(filename, extract_dir)
            logger.info(f"{filename} decompressed successfully")
        except Exception as e:
            logger.error(f"Could not decompress file {filename}")
            logger.error(traceback.format_exc())
            try:
                task.status_msg = 'falló la descompresión'     
                task.step_state = -1
                task.full_status_msg = """Ocurrió un error desconocido al intentar descomprimir los datos de imagen
                enviados por el servidor remoto. Mensaje de error completo: \n\n""" + repr(e)
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True    

        try:
            task.status_msg = 'aplicando postfiltros'
            db.session.commit()
            voxel_size = np.array([templates[0].PixelSpacing[0],templates[0].PixelSpacing[1],templates[0].SliceThickness])
            series = self.apply_postfilter(extract_dir, templates[0], voxel_size)
        except FileNotFoundError as e:
            logger.error(f"Failed when reading {extract_dir}")
            logger.error(traceback.format_exc())          
            try:                                              
                task.status_msg = f"fallo - .npy no encontrado"
                task.step_state = -1
                task.full_status_msg = """Se espera un archivo .npy en los datos enviados por el servidor, pero no
                fue encontrado. Por favor contacte a soporte."""
                db.session.commit()
                return False 
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True
        except ValueError as e:
            logger.info(e)
            logger.error(traceback.format_exc())
            try:
                task.status_msg = f"fallo - postfiltro "
                task.step_state = -1
                task.full_status_msg = """No hay ningún postfiltro configurado para esta combinación de equipo y
                radiofármaco. Por favor, configurar al menos uno en la pestaña Config."""
                db.session.commit()
                return False 
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True
        except Exception as e:
            logger.error(f"Failed when filtering {extract_dir}")
            logger.error(traceback.format_exc())     
            try:                                                   
                task.status_msg = f"fallo - postfiltro "
                task.step_state = -1
                task.full_status_msg = """Ocurrió un error inesperado al intentar aplicar el postfiltro a la imagen
                resultado. Mensaje de error completo:\n\n""" + repr(e)
                db.session.commit()
                return False 
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True
        
        try:
            task.status_msg = 'creando dicoms' 
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
                    logger.error(traceback.format_exc())

            logger.info(f"{stored_ok} dicoms stored succesfully")                        
            task.status_msg = f"creación dicoms {success}/{len(series)}" 
            db.session.commit()

            # Check if all the expected instances have been correctly stored
            # in the database
            if stored_ok == len(series) * len(task.instances):
                # Flag step as completed
                logger.info(f"{task.id}: all expected instances succesfully stored in database")                              
                task.current_step = self.next_step
                task.step_state = 1    
                task.status_msg = f"resultados guardados"
                db.session.commit()

                # Delete temporary files
                os.remove(filename)
                rmtree(extract_dir)
                return False
            else:
                # Flag step as failed
                logger.info(f"{task.id}: not all expected instances stored")
                logger.info(f"{task.id}: expected {len(series) * len(task.instances)}, stored {stored_ok}")
                try:
                    task.status_msg = f"fallo - escritura dicom"                             
                    task.step_state = -1
                    task.full_status_msg = f"""Se esperaban {len(series) * len(task.instances)} imágenes para esta tarea,
                    pero sólo {stored_ok} fueron escritas en el disco y en la base de datos."""
                    db.session.commit()   
                    return False
                except:
                    logger.error(f"task {task_id} status can't be updated")
                    logger.error(traceback.format_exc())   
                    return True
        except:
            logger.error(f"failed when building dicoms for task {task_id}")
            logger.error(traceback.format_exc())
            # Flag step as failed
            try:
                task.status_msg = f"fallo - creación dicom"                             
                task.step_state = -1
                task.full_status_msg = f"""Hubo un error desconocido al intentar crear los objetos
                DICOM con los resultados."""
                db.session.commit()   
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True

    def apply_postfilter(self, extract_dir, original_series, voxel_size):

        # Load and process voxels
        try:
            v = np.load(os.path.join(extract_dir, 'denoised.npy'))
        except Exception as e:
            logger.error(f"Failed when loading voxels from {os.path.join(extract_dir, 'denoised.npy')}")
            logger.error(traceback.format_exc())
            raise FileNotFoundError
        
        try:            
            noise = np.load(os.path.join(extract_dir, 'noise.npy'))            
        except Exception as e:
            logger.error(f"Failed when loading noise from {os.path.join(extract_dir, 'noise.npy')}")
            logger.error(traceback.format_exc())
            raise FileNotFoundError
        
        try:
            with application.app_context():
                recons = [r for r in FilterSettings.query.all() if r.enabled]    
            assert recons
        except: 
            logger.info(f"No post-filter settings found; the processed with no post-filter will be sent.")
            return [{'voxels': v,
                     'series_description':'PETFECTIOR',
                     'series_number':1001}]
        # Only apply filter settings valid for this pet model and radiopharmaceutical
        recons = [r for r in recons if r.model == 'all' or r.model == original_series.ManufacturerModelName]
        recons = [r for r in recons if r.radiopharmaceutical == 'all' or
                    original_series.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical 
                    in Radiopharmaceutical.query.get(r.radiopharmaceutical).synonyms]
        if not recons:
            raise ValueError(f'No postfilter settings found for pet model {original_series.ManufacturerModelName}')
        series = []

        series_description = original_series.SeriesDescription
        for r in recons:
            voxels = v + r.noise/100 * noise
            voxels = np.abs(voxels)
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




