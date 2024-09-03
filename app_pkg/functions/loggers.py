import logging, os
from logging.handlers import RotatingFileHandler

class CapitalizeFormatter(logging.Formatter):
    def format(self, record):

        # Put the first character in uppercase
        msg =  record.msg
        msg = msg[0].upper() + msg[1:]
        # Remove ; and carriage returns
        msg = msg.replace('\n',' ')
        msg = msg.replace(';','-')
        record.msg = msg

        return super().format(record)

def dicom_logger():
    
    logger = logging.getLogger('pynetdicom')
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    handler = RotatingFileHandler(os.path.join('data','logs','dicom.log'), maxBytes = 10*2**20, backupCount = 10)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s; %(levelname).1s; %(message)s ')    
    handler.setFormatter(formatter)
    logger.addHandler(handler)   

def app_logger():

    # Create the folder for the output file
    logging_dir = os.environ.get('LOGGING_FILEPATH')
    logging_fpath = os.path.join(logging_dir, 'output.log')
    os.makedirs(logging_dir, exist_ok = True)

    # Configure logging for the application
    app_logger = logging.getLogger('__main__')
    app_logger.handlers = []
    app_logger.setLevel(logging.DEBUG)    
    
    # Log to a file
    handler = RotatingFileHandler(logging_fpath, maxBytes = 10*2**20, backupCount = 10)
    handler.setLevel(logging.DEBUG)
    formatter = CapitalizeFormatter('%(asctime)s;%(levelname)s;%(module)s;%(funcName)s;%(message)s')
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)

    # Log to console
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = CapitalizeFormatter('%(asctime)s - %(levelname)s in %(module)s @ %(funcName)s: %(message)s')
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
