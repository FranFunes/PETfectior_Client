import os, logging
from queue import Queue
from datetime import datetime
from pynetdicom.events import Event
from pydicom.dataset import Dataset
from app_pkg import application, db
from app_pkg.db_models import Patient, Study, Series, Instance

logger = logging.getLogger('__main__')

# Some functions to manage database operations
def db_create_patient(ds: Dataset) -> Patient:
    
    pat_id = str(ds.PatientID)
    pat_name = str(ds.PatientName)
    with application.app_context():
        # Raise error if patient already exists
        patient = Patient.query.get(pat_id)
        if patient is not None:
            logger.error('patient already exists.')
            raise ValueError("This patient already exists")
        patient = Patient(PatientID = pat_id, PatientName = pat_name)
        db.session.add(patient)
        db.session.commit()
    return patient

def db_create_study(ds: Dataset) -> Study:

    uid = ds.StudyInstanceUID
    date = datetime.strptime(ds.StudyDate + ds.StudyTime[:6], '%Y%m%d%H%M%S')
    description = ds.StudyDescription
    with application.app_context():
        # Raise error if study already exists
        study = Study.query.get(uid)
        if study is not None:
            logger.error('study already exists.')
            raise ValueError("This study already exists")
        # Check if patient already exists and create it if not
        patient = Patient.query.get(ds.PatientID) or db_create_patient(ds)
        study = Study(StudyInstanceUID = uid, 
                      StudyDate = date,
                      StudyDescription = description, 
                      patient = patient)
        db.session.add(study)
        db.session.commit()

    return study
    
def db_create_series(ds: Dataset) -> Series:

    uid = ds.SeriesInstanceUID
    date = datetime.strptime(ds.SeriesDate + ds.SeriesTime[:6], '%Y%m%d%H%M%S')
    description = ds.SeriesDescription
    mod = ds.Modality
    number = ds.SeriesNumber
    with application.app_context():
        # Raise error if series already exists
        series = Series.query.get(uid)
        if series is not None:
            logger.error('series already exists.')
            raise ValueError("This series already exists")
        # Check if patient and study already exist or create them if not
        patient = Patient.query.get(ds.PatientID) or db_create_patient(ds)
        study = Study.query.get(ds.StudyInstanceUID) or db_create_study(ds)
        series = Series(SeriesInstanceUID = uid, 
                        SeriesDate = date,
                        SeriesDescription = description, 
                        SeriesNumber = number,
                        Modality = mod, 
                        patient = patient,
                        study = study)
        db.session.add(series)
        db.session.commit()
        
    return series

def db_create_instance(ds: Dataset, filename: str) -> Instance:

    uid = ds.SOPInstanceUID
    uid_class = ds.SOPClassUID
    with application.app_context():
        # Raise error if instance already exists
        instance = Instance.query.get(uid)
        if instance is not None:
            logger.error('instance already exists.')
            raise ValueError("This instance already exists")
        # Check if patient, study and series already exist or create them if not
        patient = Patient.query.get(ds.PatientID) or db_create_patient(ds)
        study = Study.query.get(ds.StudyInstanceUID) or db_create_study(ds)
        series = Series.query.get(ds.SeriesInstanceUID) or db_create_series(ds)
        instance = Instance(SOPInstanceUID = uid, 
                            SOPClassUID = uid_class,
                            filename = filename,
                            patient = patient,
                            study = study,
                            series = series)
        db.session.add(instance)
        db.session.commit()
        
    return instance

# Create a handler for the store request event
def db_store_handler(event: Event, output_queue:Queue, root_dir:str) -> int:
    
    ds = event.dataset
    ds.file_meta = event.file_meta    

    # Check if dataset has all mandatory information
    new_ds = Dataset()
    try:
        # Append mandatory information to the new dataset
        new_ds.StudyInstanceUID = ds.StudyInstanceUID
        new_ds.SeriesInstanceUID = ds.SeriesInstanceUID
        new_ds.SOPInstanceUID = ds.SOPInstanceUID
        new_ds.ImagePositionPatient = ds.ImagePositionPatient
    except AttributeError:
        # Return error code and log failure information
        logger.debug("New dataset could not be processed. Missing DICOM information?")
        return 0xA700 
    
    # Try to store dataset in disk and database
    os.makedirs(root_dir, exist_ok = True)
    # Construct an unique fname for each dataset received
    timestamp = datetime.now()
    filepath = os.path.join(root_dir, timestamp.strftime('%Y%m%d%H%m%S%f'))
    try:
        ds.save_as(filepath, write_like_original = False)
    except FileNotFoundError as e:        
        logger.debug("New dataset could not be saved - No such file or directory")
        logger.debug(repr(e))
        return 0xA700
    except Exception as e:
        logger.debug("New dataset could not be saved - unknown error")
        logger.debug(repr(e))
        return 0xA700

    # Store in the database
    try:
        db_create_instance(ds, filepath)
    except ValueError:
        logger.error("Can't write instance to database: instance already exists")
        # Try to delete written file from disk
        try:
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Can't delete file {filepath} from disk: {repr(e)}")
        return 0xA700

    # Append non mandatory information to new_ds
    fields = ['NumberOfSlices','PatientName','StudyDate','SeriesDescription']
    for field in fields:
        try:
            new_ds[field] = ds[field]
        except:
            logger.info(f"{field} not available") 
    
    # Send recon information in other dataset
    recon_ds = Dataset()            
    fields = ['PixelSpacing', 
                'ReconstructionMethod',
                'Manufacturer',
                'ManufacturerModelName',
                'SliceThickness',
                'ConvolutionKernel',
                'PatientWeight',
                'ActualFrameDuration',
                'RadiopharmaceuticalInformationSequence',
                0x000910B3,
                0x000910B2,
                0x000910BA,
                0x000910BB,
                0x000910DC]
    for field in fields:
        try:
            recon_ds[field] = ds[field]
        except:
            logger.debug(f"{field} not available")
    
    # Put relevant information in processing queue
    element = {'dataset':new_ds, 'recon_ds':recon_ds,
               'address': event.assoc.requestor.info['address'],
               'ae_title': event.assoc.requestor.info['ae_title']}        
    output_queue.put(element)

    # Return a 'Success' status
    logger.debug('instance stored successfully.')
    return 0x0000
    
