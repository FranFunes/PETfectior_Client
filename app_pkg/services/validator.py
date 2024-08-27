import threading, logging, os, requests, json, traceback
from requests import ConnectionError, JSONDecodeError
from time import sleep
from datetime import datetime
from pydicom import Dataset

from typing import List

from app_pkg import application, db
from app_pkg.db_models import Device, Task, PetModel, AppConfig, Radiopharmaceutical

# Configure logging
logger = logging.getLogger('__main__')

class Validator():

    """
    
        This class is used to verify that a Task is ready to be packed and uploaded to the server.
        It checks three conditions:
        - The Task has at least one destination assigned
        - The information about the reconstruction settings for the instances associated with the task
         are enough to be processed by the server.
        - A model exists in the server for the recon settings of this task.
                
    
    """

    def __init__(self, input_queue, next_step = 'packer'):
              
        self.input_queue = input_queue   
        self.next_step = next_step   

    def start(self):

        """
        
            Starts the process thread.            

        """

        try:
            # Check if AppConfig is available
            with application.app_context():
                config = AppConfig.query.first()
        except Exception as e:
            logger.error("can't start, AppConfig not available")            
            return "Validator can't be started: database not available"

        if not self.get_status() == 'Running':
            # Set an event to stop the thread later 
            self.stop_event = threading.Event()

            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, 
                                                args = (), name = 'Validator')        
            self.main_thread.start()
            logger.info('started')
            return 'Validator started successfully'
        else:
            return 'Validator is already running'

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("stopped")
            return "Validator stopped"
        except:
            logger.info("stopped")
            return "Validator could not be stopped"


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
            · Reads a task id from the input queue
            · Tries to find an appropiate destination for the Task, and flags it as failed if
            it couldn't
            · Checks if recon settings (available as serialized JSON in Task.recon_settings)
            is enough to complete
            · Sends a POST to the server to check if there exists a model for these recon settings         
               

        """

        while not self.stop_event.is_set() or not self.input_queue.empty():
            
            with application.app_context():

                # If there are any elements in the input queue, read them.
                if not self.input_queue.empty():

                    # Read task id from the input queue
                    task = Task.query.get(self.input_queue.get())
                    task.status_msg = 'validando'
                    db.session.commit()

                    # Set destinations for this task
                    destinations = self.set_destinations(task)
                    if not destinations:
                        logger.error(f"task {task.id} destination is unknown.")
                        task.status_msg = 'failed - destino desconocido'
                        task.step_state = -1
                        task.full_status_msg = """El procesamiento de esta tarea no puede continuar porque no hay destinos
                        configurados para las series resultantes. Por favor verifique la configuración de los dispositivos
                        DICOM remotos y asegúrese de que al menos un dispositivo esté marcado como destino, o que el modo
                        espejo esté activo y que el dispositivo origen de esta tarea esté declarado en PETfectior."""
                    else:
                        for dest in destinations:
                            if not dest in task.destinations:
                                task.destinations.append(dest)
                        # Check if dicom information is complete
                        recon_settings = Dataset.from_json(task.recon_settings)
                        valid, msg = self.check_dicom_parameters(recon_settings)
                        if not valid:
                            logger.info(f"task {task.id} completed but there is missing dicom information.")
                            task.status_msg = 'fallo - info DICOM'
                            task.step_state = -1
                            task.full_status_msg = """El procesamiento de esta tarea no puede continuear porque hay
                            información faltante o inválida en el encabezado DICOM. """ + msg                  
                        else:
                            # Check if the radiopharmaceutical is known and use it for this task
                            rf_str = recon_settings.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
                            rf = [r for r in Radiopharmaceutical.query.all() 
                                  if rf_str in r.synonyms]
                            if not rf:
                                logger.info(f"unknown radiopharmaceutical {rf_str} for task {task.id}")
                                task.status_msg = 'fallo - radiofármaco desconocido'
                                task.step_state = -1    
                                task.full_status_msg = f"""El encabezado DICOM de esta tarea tiene un valor desconocido ({rf_str})
                                en el campo Radiopharmaceutical. Por favor, use el menú Config para añadir un nuevo radiofármaco incluyendo
                                esta identificación en el encabezado DICOM, o añada esta identificación a un radiofármaco ya existente 
                                (usar valores separados por coma), y luego reintente este paso.                                
                                """    
                            else:
                                task.task_radiopharmaceutical = rf[0]
                                db.session.commit()

                                # Check if a model exists in the remote processing server for this model                            
                                try:
                                    model_available, message = self.check_model(task)
                                    assert model_available
                                except AssertionError:                            
                                    logger.info(f"server rejected the task {task.id}: " + message)
                                    task.status_msg = 'fallo - rechazada'
                                    task.step_state = -1    
                                    task.full_status_msg = "El servidor remoto rechazó esta tarea por la siguiente razón:\n" + message                                    
                                except ConnectionError as e:                            
                                    logger.info(f"server connection failed.")
                                    logger.info(traceback.format_exc())
                                    task.status_msg = 'fallo - conexión con el servidor'    
                                    task.full_status_msg = """No hay conexión con el servidor remoto. Por favor verifique
                                    la conexión a internet del dispositivo donde corre esta aplicación. Si tiene conexión
                                    y este mensaje sigue apareciendo, contacte a soporte."""
                                    task.step_state = -1
                                except (JSONDecodeError, KeyError) as e:                           
                                    logger.info(f"the server returned an incorrect JSON object during /check_model.")
                                    logger.info(traceback.format_exc())
                                    task.status_msg = 'fallo - servidor'    
                                    task.full_status_msg = """El servidor remoto envío un mensaje que no pudo ser
                                    entendido. Por favor contacte a soporte."""
                                    task.step_state = -1 
                                except AttributeError as e:
                                    logger.info(f"missing dicom information for task {task.id}.")
                                    logger.info(traceback.format_exc())
                                    task.status_msg = 'fallo - info DICOM'    
                                    task.full_status_msg = """El procesamiento de esta tarea no puede continuar porque hay 
                                    información faltante o inválida en el encabezado DICOM. """
                                    task.step_state = -1 
                                except Exception as e:
                                    logger.error(f"unknown error during check_model.")                                
                                    logger.error(traceback.format_exc())
                                    task.status_msg = 'fallo - servidor'    
                                    task.full_status_msg = """Ocurrió un error desconocido al verificar la tarea con el
                                    servidor remoto. Por favor contacte a soporte."""
                                    task.step_state = -1   

                                else:
                                    # Add this PET device name to the database
                                    names = [m.name for m in PetModel.query.all()]
                                    if not recon_settings.ManufacturerModelName in names:
                                        model = PetModel(name = recon_settings.ManufacturerModelName)
                                        db.session.add(model)                          

                                    # Flag step as completed                                
                                    task.current_step = self.next_step
                                    task.status_msg = 'validada'
                                    task.step_state = 1
                                    logger.info(f"Task {task.id} validated.")
                                
                    db.session.commit()
                                            
                else:
                    sleep(1)

                        
    def set_destinations(self, task: Task) -> List[Device]:

        destinations = []
        
        # Add devices with "is_destination" == True
        destinations.extend(Device.query.filter_by(is_destination = True).all())        
        # Check if mirror mode is activated and there are any devices matching the source IP/AET
        mirror_mode = AppConfig.query.first().mirror_mode
        if mirror_mode:       
            src_id = task.source       
            aet, ip = src_id.split('@')
            matching_ip = Device.query.filter_by(address = ip).all()         
            if len(matching_ip) == 1:
                destinations.extend(matching_ip)
            else:
                # If there are more than one devices that match IP, check if any matches both IP and AE title
                matching_aet = Device.query.filter_by(address = ip, ae_title = aet)
                if not matching_aet:
                    destinations.extend(matching_ip)
                else:
                    destinations.extend(matching_aet)
        
        # Remove duplicated
        destinations = list(set(destinations))

        return destinations
    
    def check_dicom_parameters(self, dataset: Dataset) -> bool:

        """
        
            Checks if dataset has the required fields to be sent to the server

        """
        fields = ['PixelSpacing','SliceThickness','Manufacturer','RadiopharmaceuticalInformationSequence']
        for field in fields:
            try:
                dataset[field]
            except:
                msg = field + " unavailable"
                logger.error(msg)
                return False, msg
        try:
            dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
        except:
            msg = "Falta el campo Radiopharmaceutical"
            logger.error(msg)
            return False, msg

        
        
        try:
            assert dataset.Manufacturer in ['SIEMENS','GE MEDICAL SYSTEMS']
        except:
            msg = "el fabricante " + dataset.Manufacturer + " no está soportado"
            logger.error(msg)
            return False, msg
        
        if dataset.Manufacturer=='SIEMENS':  
            try:
                dataset.ConvolutionKernel
            except:
                msg = "Falta el campo ConvolutionKernel en encabezado SIEMENS"
                logger.error(msg)
                return False, msg
            try:
                dataset.ReconstructionMethod
            except:
                msg = "Falta el campo ReconstructionMethod en encabezado SIEMENS"
                logger.error(msg)
                return False, msg            
        elif dataset.Manufacturer=='GE MEDICAL SYSTEMS':        
            try:
                dataset[0x000910B2]
            except Exception as e:
                msg = "Falta el campo 0x000910B2 en encabezado GE MEDICAL SYSTEMS"
                logger.error(msg)
                logger.error(traceback.format_exc())
                return False, msg
            try:
                dataset[0x000910B3]
            except:
                msg = "Falta el campo 0x000910B3 en encabezado GE MEDICAL SYSTEMS"
                logger.error(msg)
                return False, msg               
            try:
                dataset[0x000910BA]
            except:
                msg = "Falta el campo 0x000910BA en encabezado GE MEDICAL SYSTEMS"
                logger.error(msg)
                return False, msg          
            
            if type(dataset[0x000910BA].value) == bytes:
                isfiltered = int.from_bytes(dataset[0x000910BA].value, "little")  
            else:
                isfiltered = dataset[0x000910BA].value    
            if isfiltered:
                try:
                    dataset[0x000910BB]
                except:
                    msg = "Falta el campo 0x000910BB en encabezado GE MEDICAL SYSTEMS filtrado"                    
                    logger.error(msg)
                    return False, msg
                try:
                    dataset[0x000910DC]
                except:
                    msg = "Falta el campo 0x000910DC en encabezado GE MEDICAL SYSTEMS filtrado"
                    logger.error(msg)
                    return False, msg
        
        return True, ""

    def check_model(self, task: Task) -> bool:


        ss = Dataset.from_json(task.recon_settings)
                
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
            return False, f"{ss.Manufacturer} is not supported"
        
        c = AppConfig.query.first()
        data = {
                "id_client": c.client_id,
                "ManufacturerModelName": str(ss.ManufacturerModelName),
                "ReconstructionMethod": str(ss.ReconstructionMethod),
                "Iteraciones": iterations,
                "Subsets": subsets,
                "VoxelSpacing": str(ss.PixelSpacing),
                "SliceThickness": ss.SliceThickness,
                "Radiofarmaco": ss.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical,
                "HalfLife": ss.RadiopharmaceuticalInformationSequence[0].RadionuclideHalfLife
        }        
        logger.info('checking model for these reconstruction settings:\n' + json.dumps(data, indent = 2))

        if not os.getenv("SERVER_INTERACTION") == "True":
            return True, "Server interaction disabled"
        
        post_rsp = requests.post('http://' + c.server_url + '/check_model', json = data)

        messages = {
            "Ok": "The task has been validated by the server",
            "Radiopharmaceutical Inactive": f"""You don't have an active license for the radiopharmaceutical 
                                                {ss.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical}""",
            "Client Inactive": "You don't have an active license",
            "Not avialable Model": f"""There are no processing algorithms
                                        trained for these reconstruction settings 
                                        or radiopharmaceutical {ss.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical}."""
        }

        return post_rsp.json()['response'], messages[post_rsp.json()['reason']]