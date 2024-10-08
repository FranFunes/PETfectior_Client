from pynetdicom import AE, evt, AllStoragePresentationContexts, VerificationPresentationContexts
from pynetdicom._globals import DEFAULT_TRANSFER_SYNTAXES
import logging, os, traceback, pydicom
from app_pkg import application
from app_pkg.db_models import AppConfig

# Setup logging behaviour
logger = logging.getLogger('__main__')

pydicom.config.convert_wrong_length_to_UN = True


class StoreSCP(AE):    

    """ 
        The main class for creating and managing DICOM Store Service Class Provider.
        Inherits from pynetdicom AE class, so it has similar functionality.
        Some properties and methods are added to simplify its usage as a DICOM Store SCP:
    
        Properties:
            · scp_queue: received datasets are put into this queue. Another process is responsable
              for consuming this queue.            
                       
        Methods:
            · start: starts the server.
            · stop: stops the server (after all current transfers and existing associations are cleared up).
    
    """

    def __init__(self, input_queue, c_store_handler, ae_title = 'PETFECTIOR', store_dest = 'incoming', *args, **kwargs):

        super().__init__(ae_title, *args,**kwargs)

        # Set class properties
        self.queue = input_queue
        self.store_dest =  store_dest   
        self.handle_store = c_store_handler     

        # Add presentation contexts with specified transfer syntaxes
        for context in AllStoragePresentationContexts:
            self.add_supported_context(context.abstract_syntax, DEFAULT_TRANSFER_SYNTAXES)

        for context in VerificationPresentationContexts:
            self.add_supported_context(context.abstract_syntax, DEFAULT_TRANSFER_SYNTAXES)
            self.add_requested_context(context.abstract_syntax, DEFAULT_TRANSFER_SYNTAXES)                     

        # Create store directory if it does not exist.
        try:
            os.makedirs(store_dest, exist_ok = True)
            logger.debug('Destination directory created successfully')
        except:
            logger.error('Destination directory could not be created')
        
        # Implement a handler for evt.EVT_C_ECHO
        def handle_echo(event):
            """Handle a C-ECHO request event."""
            return 0x0000
        
        self.handle_echo = handle_echo

    def start(self):        

        """    

        Starts the DICOM Store Service Class Provider.

        """                      
        with application.app_context():
            config = AppConfig.query.first()
            ae_title = config.store_scp_aet
            port = config.store_scp_port


        handlers = [(evt.EVT_C_STORE, self.handle_store, [self.queue, self.store_dest]), (evt.EVT_C_ECHO, self.handle_echo)]   

        # Start listening for incoming association requests
        if not self.get_status() == 'Corriendo':
            try:
                self.server = self.start_server(address = ('0.0.0.0', port), ae_title = ae_title, evt_handlers=handlers, block = False)     
                logger.info(f'Starting Store SCP: {ae_title}@0.0.0.0:{port}')
                return "Dicom Listener inició exitosamente"
            except Exception as e:
                logger.error(f'Failed when starting StoreSCP {ae_title}@0.0.0.0:{port}')
                logger.error(traceback.format_exc())
                return "Dicom Listener could not be started"
        else:
            return 'Dicom Listener ya está corriendo'

    def stop(self):

        """ Stops the SCP """ 
        try:               
            self.server.shutdown()
            logger.info("Store SCP stopped")
            return 'Dicom Listener stopped!'
        except:
            logger.error("Store SCP could not be stopped")
            return 'Dicom Listener could not be stopped!'


    def restart(self):
        
        try:
            self.stop()
        except Exception as e: 
            logger.info("Server could not be stopped")
            logger.info(repr(e))
        self.start()

    def get_status(self):

        if not hasattr(self,"server"):
            state = 'No iniciado'
        else:
            state = 'Detenido'
            # Create an AE and send a C - ECHO to ourselves            
            ae = AE()            
            
            for context in VerificationPresentationContexts:                
                ae.add_requested_context(context.abstract_syntax, DEFAULT_TRANSFER_SYNTAXES)   

            with application.app_context():
                config = AppConfig.query.first()                
            port = config.store_scp_port
            assoc = ae.associate("127.0.0.1", port)

            if assoc.is_established:
                status = assoc.send_c_echo()
                if status:                                        
                    try:
                        assert status.Status == 0                        
                        state = 'Corriendo'
                    except:
                        pass
                else:
                    logger.error("Connection timed out, was aborted or received invalid response")                    

                # Release the association
                assoc.release()
            else:
                logger.error("Association rejected, aborted or never connected")                                    
        
        return state
    
    def echo(self, device: dict) -> int:

        """
            device: dict with address, port and ae_title

        """
        try:
            assoc = self.associate(device['address'], device['port'], ae_title = device['ae_title'])

            if assoc.is_established:
                echo_response = assoc.send_c_echo()
                if 'Status' in echo_response: 
                    assoc.release()
                    return echo_response.Status
            else:
                return -1
        except RuntimeError:
            logger.info(f"association with {device['ae_title']}@{device['address']}:{device['port']} could not be established")
            return -1
        
    