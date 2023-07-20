#from dropbox import DropboxOAuth2FlowNoRedirect
#from dropbox import Dropbox
#from dropbox.exceptions import ApiError
import logging, threading, os, json
from time import sleep

# Configure logging
logger = logging.getLogger('__main__')

class SeriesDownloader():

    def __init__(self, output_queue, APP_KEY = None, APP_SECRET = None, auth_token = None,
                    dropbox_folder = '/processed_series', output_folder = 'SeriesToUnpack'):

        self.output_queue = output_queue
        self.auth_token = auth_token
        self.app_key = APP_KEY
        self.app_secret = APP_SECRET
        self.output_folder = output_folder

        # Set dropbox folder for this client
        config_file = os.path.join("data",'client.json')
        with open(config_file,"r") as filename:
            clientID = json.load(filename)['clientID']
        self.dbx_folder = os.path.join(dropbox_folder, clientID)

        # Create output directory if it does not exist.
        try:
            os.makedirs(output_folder, exist_ok = True)
            logger.debug('Downloader - init: output directory created successfully')
        except:
            logger.error('Downloader - init: output directory could not be created')  

    def authenticate(self):

        if not self.app_key or not self.app_secret:
            logger.error('Uploader - authenticate: key or secret not available')
        else:
            token = self.get_auth_token(self.app_key, self.app_secret)
            self.auth_token = token

    @staticmethod
    def get_auth_token(APP_KEY, APP_SECRET):

        auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)

        authorize_url = auth_flow.start()
        print("1. Go to: " + authorize_url)
        print("2. Click \"Allow\" (you might have to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()
            
        try:
            oauth_result = auth_flow.finish(auth_code)
            print('Dropbox login successful')
            return oauth_result.access_token
        except Exception as e:
            print('Dropbox login failed. Error: %s' % (e,))
            return None

    def start(self):

        """
        
            Starts the process thread.            

        """
        # Create the dropbox instance to upload files
        if not self.auth_token:
            logger.error('Authentication token not available')
            raise Exception('Authentication token not available')
        
        dbx = Dropbox(self.auth_token)

        # Check if connection was succesful
        try:
            dbx.check_user('Checking...')
        except:
            raise Exception('Could not create dropbox instance')
        
        # Check if folder exists
        path = os.path.dirname(self.dbx_folder)
        if path == '/':
            path = ""
        query = os.path.basename(self.dbx_folder)

        try:
            search_results = dbx.files_search(path, query).matches
            assert len(search_results) >= 1

        except ApiError:
            msg = 'Downloader - start: Dropbox API error when consulting folder existence.'
            logger.error(msg)
            raise Exception(msg)            
        except AssertionError:
            msg = f"Downloader - start: {path} folder does not exists in dropbox account."
            logger.warning(msg)

        # Copy the dropbox instance to class
        self.dropbox = dbx        

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        # Create and start the thread
        self.main_thread = threading.Thread(target = self.main, args = ())        
        self.main_thread.start()
        logger.info('Downloader started')

    def stop(self):

        """
        
            Stops the thread by setting an Event.

        """

        # Event to interrupy processing        
        self.stop_event.set()
        # Stop the thread
        self.main_thread.join()
        # Close dropbox connection
        self.dropbox.close()

        logger.info("Downloader stopped")


    def main(self):

        while not self.stop_event.is_set():
            # Read dropbox folder contents
            try:
                file_list = [entry.name for entry in self.dropbox.files_list_folder(self.dbx_folder).entries 
                                        if entry.name[-3:] == 'zip']
            except ApiError:
                logger.error(f"Downloader - main: Dropbox API error when trying to list {self.dbx_folder} folder from cloud storage")
                file_list = []
            except:
                logger.error(f"Downloader - main: Unknown error when trying to list {self.dbx_folder} folder from cloud storage")
                file_list = []

            # If there are any files in the folder queue, download them.
            for file in file_list:

                # Download file                
                try:
                    dbx_filename = os.path.join(self.dbx_folder, file)                    
                    logger.info(f"Downloader - main: downloading {dbx_filename} from dropbox")
                    metadata, response = self.dropbox.files_download(dbx_filename)
                    logger.info(f"Downloader - main: {file} downloaded successfully")
                                        
                    
                except ApiError:
                    logger.error('Downloader - main: Dropbox API error during download')
                except:
                    logger.error('Downloader - main: Unknown error during download')
                else:
                    try:
                        # Write data to file
                        filename = os.path.join(self.output_folder, file)
                        logger.info(f"Downloader - main: writing {file} to {filename}")
                        with open(filename,'wb') as output_file:
                            output_file.write(response.content)
                        logger.info(f"Downloader - main: {filename} written successfully")
                    except Exception as error:
                        logger.error(f"Downloader - main: file could not be written to {filename}")
                        print(error)

                    else:
                        # If download and write were successful, put filename in queue for further processing
                        self.output_queue.put(filename)  

                        # Delete from cloud storage
                        try:
                            self.dropbox.files_delete(dbx_filename)
                            logger.info(f"Downloader - main: {dbx_filename} deleted from cloud storage")
                        except ApiError:
                            logger.error(f"Downloader - main: Dropbox API error when trying to delete {dbx_filename} from cloud storage")
                        except:
                            logger.error(f"Downloader - main: Unknown error when trying to delete {dbx_filename} from cloud storage")
      
            
            sleep(1)