import logging
from app_pkg import application, db
from app_pkg.services.loggers import CapitalizeFormatter
from app_pkg.db_models import AppLog

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