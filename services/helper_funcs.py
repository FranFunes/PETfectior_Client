import os, logging
#from dropbox import DropboxOAuth2FlowNoRedirect

# Configure logging
logger = logging.getLogger('__main__')

def delete_series(filenames):

    """
    
        Deletes files from disk.
        Args:
            ·filenames: list of str with the filenames to delete.

    """

    for file in filenames:
        try:
            os.remove(file)
        except:
            logger.error(f"Could not remove file {file}")

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