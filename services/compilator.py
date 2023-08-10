import json, threading, logging, os, requests
from time import sleep
from datetime import datetime
import numpy as np
from services.helper_funcs import delete_series
from pydicom import Dataset

from app_pkg import application
from app_pkg.db_models import Device, Task, Series, Instance, task_instance

# Configure logging
logger = logging.getLogger('__main__')

class Compilator():

    """
    
        This class is used to read DICOM SOP Instances (images) received by the StoreSCP
        and compile them in whole series. Instances are read from input_queue.
        The number of instances present in each series is found through a dedicated function.
        
        When the process has been sleeping during a predefined time, each series is checked to
        find if it should be put in the output queue, discarded or keep waiting. This is 
        done by another predefined function.
    
    """

    def __init__(self, input_queue, task_manager, server_url, series_timeout = 30, 
                 min_instances_in_series = 47, slice_gap_tolerance = 0.025):
              
        pass