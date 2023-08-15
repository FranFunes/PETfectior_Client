import logging, threading, requests
from time import sleep
from datetime import datetime
from app_pkg import application
from app_pkg.db_models import AppConfig


# Configure logging
logger = logging.getLogger('__main__')

class ServerMonitor():

    def __init__(self, ping_route: str, sample_period_seconds:float = 10):
        
        self.ping_route = ping_route
        self.clock = sample_period_seconds

        # Initialize state variables
        self.total_downtime_seconds = 0
        self.total_uptime_seconds = 0        
        self.current_state_duration = 0
        self.total_disconnections = 0
        self.last_connection = None
        self.last_disconnection = None
        self.connected = False
        self.state = 'Unknown'  

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
            return "Validator can't be started: database not available"
        
        self.ping_url = 'http://' + config.server_url + '/' + self.ping_route
        if not self.get_status() == 'Running':
            # Create and start the thread if all conditions are fullfilled
            self.main_thread = threading.Thread(target = self.main, args = ())   
            self.main_thread.start()
            logger.info('Server monitor started')
            return "Server monitor started successfully"
        else:
            return "Server monitor is already running"

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """
        try:
            self.stop_event.set()
            self.main_thread.join()
            logger.info("Server monitor stopped")
            return "Server monitor stopped!"
        except Exception as e:
            logger.error("Server monitor stop failed")
            logger.error(repr(e))
            return "Server monitor could not be stopped!"
    
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

    def ping(self):
        
        start = datetime.now()
        try:
            page = requests.get(self.ping_url, timeout = 5)
            logger.debug(f'Connection succesful!')
            stop = datetime.now()
            etime = (stop - start).seconds
            return True, etime        
        
        except Exception as e:
            logger.debug(f'Connection failed: {repr(e)}')
            stop = datetime.now()
            etime = (stop - start).seconds

            return False, etime

    def main(self):       
              

        logger.info('Started monitoring')

        while not self.stop_event.is_set():
                                    
            if self.connected:              
                # Refresh connection state  
                self.state = self.state + ' (refreshing...)' 
                self.connected, etime = self.ping()
                if self.connected:
                    self.total_uptime_seconds += self.clock + etime 
                    self.current_state_duration += self.clock + etime
                    self.state = 'Alive'    
                else:
                    self.total_disconnections += 1
                    self.current_state_duration = etime
                    self.state = 'Not available'                                     
            else:
                # Refresh connection state  
                self.state = self.state + ' (refreshing...)' 
                self.connected, etime = self.ping()
                if self.connected:
                    self.current_state_duration = etime
                    self.state = 'Alive'
                else:
                    self.total_downtime_seconds += self.clock + etime
                    self.current_state_duration += self.clock + etime
                    self.state = 'Not available' 
                    
            sleep(self.clock)

    def get_statistics(self):

        data = {
            'state': self.state,
            'state_duration': self.current_state_duration,
            'total_disconnections': self.total_disconnections,
            'total_uptime': self.total_uptime_seconds,
            'total_downtime': self.total_downtime_seconds
        }

        return data




        


        