from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox import Dropbox
from dropbox.exceptions import ApiError
import logging, threading, os
from time import sleep

# Configure logging
logger = logging.getLogger('ClientAI')
logger = logging.getLogger('UploaderDebugger')

logger.handlers = []
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s: %(levelname).1s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class SeriesUploader():

    def __init__(self, input_queue, APP_KEY = None, APP_SECRET = None, auth_token = None,
                    dropbox_folder = '/series_to_process'):

        self.input_queue = input_queue
        self.auth_token = auth_token
        self.app_key = APP_KEY
        self.app_secret = APP_SECRET        
        self.dbx_folder = dropbox_folder    

    def authenticate(self):

        if not self.app_key or not self.app_secret:
            logger.error('Key or secret not available')
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
        
        # Create folder to store contents
        try:
            dbx.files_create_folder(self.dbx_folder)

        except ApiError as error:
            logger.error('Uploader - start: Dropbox API error during folder creating')

        # Copy the dropbox instance to class
        self.dropbox = dbx        

        # Set an event to stop the thread later 
        self.stop_event = threading.Event()

        # Create and start the thread
        self.main_thread = threading.Thread(target = self.main, args = ())        
        self.main_thread.start()
        logger.info('Uploader started')

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

        logger.info("Uploader stopped")


    def main(self):

        while not self.stop_event.is_set() or not self.input_queue.empty():

            # If there are any elements in the input queue, read them.
            if not self.input_queue.empty():
                # Get filenames from the queue
                filename = self.input_queue.get()

                # Read and upload file
                with open(filename, 'rb') as file:
                    data = file.read()
                try:                    
                    logger.info(f"Uploader - main: uploading {filename}")
                    dbx_filename = os.path.join(self.dbx_folder, os.path.basename(filename))
                    upload_result = self.dropbox.files_upload(data, dbx_filename)
                    logger.info(f"Uploader - main: {filename} uploaded successfully")                    

                except ApiError as error:
                    logger.error('Uploader - main: Dropbox API error during upload')
                    logger.error(f"{error}")

                except:
                    logger.error('Uploader - main: Unknown error occurred during upload')

                else:
                    # Delete file if upload was succesful
                    os.remove(filename)

            else:
                sleep(1)

    

    
        
# And another comment here