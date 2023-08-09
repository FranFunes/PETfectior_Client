from app_pkg import application, db
from app_pkg.db_models import AppLog
import logging, os
from logging.handlers import RotatingFileHandler

os.makedirs(os.path.join('data','logs'), exist_ok = True)

class LogDBHandler(logging.Handler):
    
    """

    Customized logging handler that puts logs to the database.

    """
    
    def __init__(self, bkp_handler):
        logging.Handler.__init__(self)
        self.bkp_handler = bkp_handler    
    
    def emit(self, record):
        
        # Write to database
        try:
            with application.app_context():
                log = AppLog(level = record.levelname,
                            module = record.module,
                            function = record.funcName,
                            msg = record.msg)
                db.session.add(log)
                db.session.commit()
        # If error, use backup handler. Since DB is not working - there's
        # no point making a log about it to the database.
        except Exception as e:
            print('Error when trying to log to database. Logging to backup logger')
            print(e.__traceback__.tb_frame)
            print(e.__traceback__.tb_lineno)
            print(repr(e))
            self.bkp_handler.emit(record)
            

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
    handler = RotatingFileHandler(os.path.join('data','logs','dicom_events.log'), maxBytes = 10*2**20, backupCount = 10)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s: %(levelname).1s: %(threadName)s: %(message)s ')    
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    handler = RotatingFileHandler(os.path.join('data','logs','dicom_errors.log'), maxBytes = 10*2**20, backupCount = 1)
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s: %(levelname).1s: %(threadName)s: %(message)s ')    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
   

def app_logger():

    # Configure logging for the application
    app_logger = logging.getLogger('__main__')
    app_logger.handlers = []
    app_logger.setLevel(logging.DEBUG)    
    
    bkp_handler = RotatingFileHandler(os.environ.get('LOGGING_FILE', default = 'output.log'), maxBytes = 10*2**20, backupCount = 100)
    bkp_handler.setLevel(logging.DEBUG)
    formatter = CapitalizeFormatter('%(asctime)s;%(levelname)s;%(module)s;%(funcName)s;%(message)s')
    bkp_handler.setFormatter(formatter)
    app_logger.addHandler(bkp_handler)

    db_handler = LogDBHandler(bkp_handler)
    app_logger.addHandler(db_handler)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = CapitalizeFormatter('%(asctime)s - %(levelname)s in %(module)s @ %(funcName)s: %(message)s')
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
