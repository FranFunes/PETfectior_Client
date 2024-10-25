import threading, logging, os, requests, json, traceback, re
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

        if not self.get_status() == 'Corriendo':
            # Set an event to stop the thread later 
            self.stop_event = threading.Event()

            # Create and start the thread
            self.main_thread = threading.Thread(target = self.main, 
                                                args = (), name = 'Validator')        
            self.main_thread.start()
            logger.info('started')
            return 'Validator inició exitosamente'
        else:
            return 'Validator ya está corriendo'

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("stopped")
            return "Validator detenido"
        except:
            logger.info("stopped")
            return "Validator no pudo ser detenido"

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

    def task_step_handler(self, task_id):
        
        try:
            task = Task.query.get(task_id)
            task.status_msg = 'validando'
            db.session.commit()
        except:
            logger.error(f"can't read task with {task_id} from database")
            logger.error(traceback.format_exc())
            return True

        # Set destinations for this task
        destinations = self.set_destinations(task)
        if not destinations:
            logger.error(f"task {task_id} destination is unknown.")
            try:
                task.status_msg = 'failed - destino desconocido'
                task.step_state = -1
                task.full_status_msg = """El procesamiento de esta tarea no puede continuar porque no hay destinos
                configurados para las series resultantes. Por favor verifique la configuración de los dispositivos
                DICOM remotos y asegúrese de que al menos un dispositivo esté marcado como destino, o que el modo
                espejo esté activo y que el dispositivo origen de esta tarea esté declarado en PETfectior."""
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())
                return True
        
        for dest in destinations:
            if not dest in task.destinations:
                task.destinations.append(dest)

        # Check if dicom information is complete
        valid, msg = self.check_dicom_parameters(task)
        if not valid:
            logger.info(f"task {task_id} completed but there is missing dicom information.")
            try:
                task.status_msg = 'fallo - info DICOM'
                task.step_state = -1
                task.full_status_msg = """El procesamiento de esta tarea no puede continuar porque hay
                información faltante o inválida en el encabezado DICOM. """ + msg   
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())            
                return True

        try:
            # Check if the radiopharmaceutical is known and use it for this task
            rf_str = Dataset.from_json(task.recon_settings).RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
            rf = [r for r in Radiopharmaceutical.query.all() 
                    if rf_str in r.synonyms]
        except:
            logger.error(f"task {task_id} can't check rf")
            logger.error(traceback.format_exc())            
            return True

        if not rf:
            logger.info(f"unknown radiopharmaceutical {rf_str} for task {task_id}")
            try:
                task.status_msg = 'fallo - radiofármaco desconocido'
                task.step_state = -1    
                task.full_status_msg = f"""El encabezado DICOM de esta tarea tiene un valor desconocido ({rf_str})
                en el campo Radiopharmaceutical. Por favor, use el menú Config para añadir un nuevo radiofármaco incluyendo
                esta identificación en el encabezado DICOM, o añada esta identificación a un radiofármaco ya existente 
                (usar valores separados por coma), y luego reintente este paso.                                
                """
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())            
                return True
        
        try:
            task.task_radiopharmaceutical = rf[0]
            db.session.commit()
        except:
            logger.error(f"task {task_id} rf can't be updated")
            logger.error(traceback.format_exc())   
            return True

        # Check if a model exists in the remote processing server for this model                            
        try:
            model_available, message = self.check_model(task)
            assert model_available
        except AssertionError:                            
            logger.info(f"server rejected the task {task_id}: " + message)
            try:
                task.status_msg = 'fallo - rechazada'
                task.step_state = -1    
                task.full_status_msg = "El servidor remoto rechazó esta tarea por la siguiente razón:\n" + message
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True

        except ConnectionError as e:
            logger.info(f"server connection failed.")
            logger.info(traceback.format_exc())
            try:
                task.status_msg = 'fallo - conexión con el servidor'    
                task.full_status_msg = """No hay conexión con el servidor remoto. Por favor verifique
                la conexión a internet del dispositivo donde corre esta aplicación. Si tiene conexión
                y este mensaje sigue apareciendo, contacte a soporte."""
                task.step_state = -1
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())   
                return True
        except (JSONDecodeError, KeyError) as e:
            try:
                logger.info(f"the server returned an incorrect JSON object during /check_model.")
                logger.info(traceback.format_exc())
                task.status_msg = 'fallo - servidor'    
                task.full_status_msg = """El servidor remoto envío un mensaje que no pudo ser
                entendido. Por favor contacte a soporte."""
                task.step_state = -1
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())  
                return True
        except AttributeError as e:
            logger.info(f"missing dicom information for task {task_id}.")
            logger.info(traceback.format_exc())
            try:
                task.status_msg = 'fallo - info DICOM'    
                task.full_status_msg = """El procesamiento de esta tarea no puede continuar porque hay 
                información faltante o inválida en el encabezado DICOM. """
                task.step_state = -1
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())
                return True
        except Exception as e:
            logger.error(f"unknown error during check_model.")                                
            logger.error(traceback.format_exc())
            try:
                task.status_msg = 'fallo - servidor'    
                task.full_status_msg = """Ocurrió un error desconocido al verificar la tarea con el
                servidor remoto. Por favor contacte a soporte."""
                task.step_state = -1
                db.session.commit()
                return False
            except:
                logger.error(f"task {task_id} status can't be updated")
                logger.error(traceback.format_exc())
                return True

        # Add this PET device name to the database
        try:
            names = [m.name for m in PetModel.query.all()]
            if not Dataset.from_json(task.recon_settings).ManufacturerModelName in names:
                model = PetModel(name = Dataset.from_json(task.recon_settings).ManufacturerModelName)
                db.session.add(model)        
                db.session.commit()        
        except:
            logger.error(f"pet models can't be updated")
            logger.error(traceback.format_exc())
            
        try:
            # Flag step as completed                                
            task.current_step = self.next_step
            task.status_msg = 'validada'
            task.step_state = 1
            logger.info(f"Task {task.id} validated.")
            db.session.commit()            
            return False
        except:
            logger.error(f"task {task_id} status can't be updated")
            logger.error(traceback.format_exc())
            return True
                        
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
    
    def check_dicom_parameters(self, task: Task) -> bool:

        """
        
            Checks if task recon settings has the required fields to be sent to the server

        """

        dataset = Dataset.from_json(task.recon_settings)
        fields = ['PixelSpacing','SliceThickness','Manufacturer','RadiopharmaceuticalInformationSequence']
        for field in fields:
            try:
                dataset[field]
            except:
                msg = field + " no disponible"
                logger.error(msg)
                return False, msg

        try:
            assert dataset.Manufacturer in ['SIEMENS', 'GE MEDICAL SYSTEMS', 'CPS', 'Mediso', 'UIH', 'Philips','Philips Medical Systems']
        except:
            msg = "el fabricante " + dataset.Manufacturer + " no está soportado"
            logger.error(msg)
            return False, msg

        # SIEMENS
        if dataset.Manufacturer=='SIEMENS':
            try:
                dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
            except:
                msg = "Falta el campo Radiopharmaceutical en encabezado SIEMENS"
                logger.error(msg)
                return False, msg
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
        
        # GE
        if dataset.Manufacturer=='GE MEDICAL SYSTEMS': 
            try:
                dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical
            except:
                msg = "Falta el campo Radiopharmaceutical en encabezado GE MEDICAL SYSTEMS"
                logger.error(msg)
                return False, msg       
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
        
        # CPS
        if dataset.Manufacturer == 'CPS':
            try:
                # Patch Radiopharmaceutical with Radionuclide for this maker
                rf_seq = dataset.RadiopharmaceuticalInformationSequence[0]
                rf_seq = rf_seq.RadionuclideCodeSequence[0]
                dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical = dataset.RadiopharmaceuticalInformationSequence[0]. \
                                                                                        RadionuclideCodeSequence[0].CodeMeaning
                # Update recon_settings
                task.recon_settings = dataset.to_json()
                db.session.commit()
                logger.info('Se parcheo el campo Radiopharmaceutical en header CPS')
            except:
                msg = "Error al extraer el nombre del Radionucleído en encabezado CPS"
                logger.error(msg)
                logger.error(traceback.format_exc())
                return False, msg                  
            try:
                dataset.ReconstructionMethod
            except:
                msg = "Falta el campo ReconstructionMethod en encabezado CPS"
                logger.error(msg)
                return False, msg               
            try:
                dataset.ConvolutionKernel
            except:
                msg = "Falta el campo ConvolutionKernel en encabezado CPS"
                logger.error(msg)
                return False, msg
        
        # Mediso
        if dataset.Manufacturer == 'Mediso':
            try:
                # Patch Radiopharmaceutical with Radionuclide for this maker
                rf_seq = dataset.RadiopharmaceuticalInformationSequence[0]
                rf_seq = rf_seq.RadionuclideCodeSequence[0]
                dataset.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical = dataset.RadiopharmaceuticalInformationSequence[0]. \
                                                                                        RadionuclideCodeSequence[0].CodeMeaning
                # Update recon_settings
                task.recon_settings = dataset.to_json()
                db.session.commit()
                logger.info('Se parcheo el campo Radiopharmaceutical en header Mediso')
            except:
                msg = "Error al extraer el nombre del Radionucleído en encabezado CPS"
                logger.error(msg)
                logger.error(traceback.format_exc())
                return False, msg
            try:
                dataset.ReconstructionMethod
            except:
                msg = "Falta el campo ReconstructionMethod en encabezado Mediso"
                logger.error(msg)
                return False, msg
            try:
                # Patch ConvolutionKernel
                match = re.search(r"@\s*(\d*\.?\d+)\s*m{0,2},", dataset.ReconstructionMethod)
                postfilter = float(match.group(1))
                dataset.ConvolutionKernel = postfilter
                task.recon_settings = dataset.to_json()
                db.session.commit()
            except:
                msg = f"Error al leer el postfiltro de Mediso en el campo ReconstructionMethod {dataset.ReconstructionMethod}"
                logger.error(msg)
                logger.error(traceback.format_exc())
                return False, msg
        
        # UIH
        if dataset.Manufacturer == 'UIH':
            try:
                recon_settings = dataset[0x00671021][0]             
                recon_alg = recon_settings[0x00189749][0]             
                iterations = recon_alg[0x00189739].value                       
                subsets = recon_alg[0x00189740].value   
            except Exception as e:
                msg = f"Falta algún encabezado en UIH: {repr(e)}"
                logger.error(msg)
                logger.error(traceback.format_exc())
                return False, msg

        # Philips
        if dataset.Manufacturer in ['Philips','Philips Medical Systems']:
            pass

        return True, ""

    def check_model(self, task: Task) -> bool:

        ss = Dataset.from_json(task.recon_settings)
        
        # SIEMENS
        if ss.Manufacturer == 'SIEMENS':
            recon_method = ss.ReconstructionMethod      
            match = re.search(r'(\d+)i(\d+)s', recon_method, re.IGNORECASE)
            try:
                iterations = int(match.group(1))
                subsets = int(match.group(2))
            except:
                return False, f"""No se encontraron las iteraciones y subsets 
                en el campo ReconstructionMethod {recon_method} de Siemens """        
        # CPS
        elif ss.Manufacturer == 'CPS':                    
            try:
                recon_method = ss.ReconstructionMethod      
                match = re.search(r'(\d+)i(\d+)s', recon_method, re.IGNORECASE)
                iterations = int(match.group(1))
                subsets = int(match.group(2))
            except:
                return False, f"""No se encontraron las iteraciones y subsets 
                en el campo ReconstructionMethod {recon_method} de CPS"""

        # Mediso        
        elif ss.Manufacturer == 'Mediso':            
            try:                
                recon_method = ss.ReconstructionMethod      
                match = re.search(r'i(\d+)s(\d+)', recon_method, re.IGNORECASE)
                iterations = int(match.group(1))
                subsets = int(match.group(2))                
            except:
                return False, f"""No se encontraron las iteraciones y subsets 
                en el campo ReconstructionMethod {recon_method} de Mediso """

        # GE  
        elif ss.Manufacturer == 'GE MEDICAL SYSTEMS':
            if type(ss[0x000910B2].value) == bytes:
                iterations = int.from_bytes(ss[0x000910B2].value, "little")  
            else:
                iterations = ss[0x000910B2].value            
            
            if type(ss[0x000910B3].value) == bytes:
                subsets = int.from_bytes(ss[0x000910B3].value, "little")  
            else:
                subsets = ss[0x000910B3].value
        
        # UIH
        elif ss.Manufacturer == 'UIH':
            recon_settings = ss[0x00671021][0]             
            recon_alg = recon_settings[0x00189749][0]             
            iterations = recon_alg[0x00189739].value                       
            subsets = recon_alg[0x00189740].value
        
        # Philips  
        elif ss.Manufacturer == 'Philips':
            iterations = 0
            subsets = 0        
        elif ss.Manufacturer == 'Philips Medical Systems':
            iterations = 0
            subsets = 0
                
        else:
            logger.info(f"manufacturer {ss.Manufacturer} not supported")      
            return False, f"El fabricante {ss.Manufacturer} no está soportado"
        
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
        logger.info(f'checking model for task {task.id} and these reconstruction settings:\n' + json.dumps(data, indent = 2))

        if not os.getenv("SERVER_INTERACTION") == "True":
            return True, "Interacción con el servidor deshabilitada (modo debug)"
        
        post_rsp = requests.post('http://' + c.server_url + '/check_model', json = data)

        messages = {
            200: "La tarea ha sido validada por el servidor",
            405: "No tienes una licencia activa",
            406: f"""No cuentas con una licencia activa para el radiofármaco
                                                {ss.RadiopharmaceuticalInformationSequence[0].Radiopharmaceutical}""",
            407: f"""No hay algoritmos de procesamiento entrenados para estos parámetros de reconstrucción
             o este radiofármaco."""
        }

        return post_rsp.status_code == 200, messages[post_rsp.status_code]
