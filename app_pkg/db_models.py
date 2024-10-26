import os, logging, traceback
from shutil import rmtree
from app_pkg import db, login
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import event
   
logger = logging.getLogger('__main__')

# Association tables for many-to-many relationships
task_destination = db.Table('task_destination',
                            db.Column('task_id', db.String(18), db.ForeignKey('task.id')),
                            db.Column('device_name', db.String(64), db.ForeignKey('device.name')))

task_instance = db.Table('task_instance',
                            db.Column('task_id', db.String(18), db.ForeignKey('task.id')),
                            db.Column('sop_instance_uid', db.String(64), db.ForeignKey('instance.SOPInstanceUID')))

class Patient(db.Model):
    PatientID = db.Column(db.String(64), primary_key=True)
    PatientName = db.Column(db.String(64), index=True)

    # Cross-references down
    studies = db.relationship('Study', backref='patient', lazy='dynamic', cascade='all, delete-orphan')    
    series = db.relationship('Series', backref='patient', lazy='dynamic')    
    instances = db.relationship('Instance', backref='patient', lazy='dynamic')    
    
    def __repr__(self):
        return f'<Patient {self.PatientName}>'

class Study(db.Model):

    StudyInstanceUID = db.Column(db.String(64), primary_key=True)
    StudyDate = db.Column(db.DateTime, index=True)    
    StudyDescription = db.Column(db.String(64), index=True)
    PatientWeight = db.Column(db.Float())
    PatientAge = db.Column(db.String(4))
    PatientSize = db.Column(db.Float())
    stored_in = db.Column(db.Text())   

    # Cross-references up
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))

    # Cross-references down
    series = db.relationship('Series', backref='study', lazy='dynamic', cascade='all, delete-orphan')    
    instances = db.relationship('Instance', backref='study', lazy='dynamic')     

    def __repr__(self):
        return f'<Study {self.StudyDescription} from {self.PatientID}>'
    
class Series(db.Model):

    SeriesInstanceUID = db.Column(db.String(64), primary_key=True)
    SeriesDate = db.Column(db.DateTime, index=True)
    SeriesDescription = db.Column(db.String(64), index=True)
    Modality = db.Column(db.String(64), index=True)
    SeriesNumber = db.Column(db.Integer())
    SeriesTime = db.Column(db.DateTime)  
    stored_in = db.Column(db.Text())   
    
    # One-to-many relationships (as child)
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))
    StudyInstanceUID = db.Column(db.String(64), db.ForeignKey('study.StudyInstanceUID'))
    originating_task = db.Column(db.String(18), db.ForeignKey('task.id'))

    # One-to-many relationships (as parent)
    instances = db.relationship('Instance', backref='series', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='task_series', lazy='dynamic', foreign_keys='Task.series')     

    def __repr__(self):
        return f'<Series {self.SeriesDescription} from {self.PatientID}>'    

def clear_storage(mapper, connection, target):
    
    try:
        logger.info(f"deleting storage before deleting Series {target.SeriesInstanceUID}")
    except:
        try:
            logger.info(f"deleting storage before deleting Series {target.StudyInstanceUID}")
        except:
            logger.info(f"deleting storage before deleting Series or Study")
    # Delete files from disk
    try:
        rmtree(target.stored_in)
        logger.info(f"deleted {target.stored_in}")
    except Exception as e:
        logger.error(f"could'n delete {target} from storage")
        logger.error(traceback.format_exc())

event.listen(Study, 'before_delete', clear_storage)
event.listen(Series, 'before_delete', clear_storage)

class Instance(db.Model):

    SOPInstanceUID = db.Column(db.String(64), primary_key=True)
    SOPClassUID = db.Column(db.String(64), index=True)   
    filename = db.Column(db.Text())    

    # One-to-many relationships (as child)
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))
    StudyInstanceUID = db.Column(db.String(64), db.ForeignKey('study.StudyInstanceUID'))
    SeriesInstanceUID = db.Column(db.String(64), db.ForeignKey('series.SeriesInstanceUID'))     

    def __repr__(self):
        return f'<Instance {self.SOPInstanceUID} from {self.PatientID} stored at {self.filename}>'   
    
class Device(db.Model):

    name = db.Column(db.String(64), primary_key=True)
    ae_title = db.Column(db.String(64), index=True, nullable=False)
    address = db.Column(db.String(16), index=True, nullable=False)
    port = db.Column(db.Integer(), index=True, nullable=False)
    is_destination = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Device {self.name}: {self.ae_title}@{self.address}>'    

class Source(db.Model):

    identifier = db.Column(db.String(96), primary_key=True)
    port = db.Column(db.Integer)    

    # One-to-many relationships (as parent)
    related_tasks = db.relationship('Task', backref='task_source', lazy='dynamic')

    def __repr__(self):
        return f'<Source {self.identifier}>'    
    
class Task(db.Model):
    id = db.Column(db.String(18), primary_key=True)
    started = db.Column(db.DateTime, default=datetime.now)
    updated = db.Column(db.DateTime)
    current_step = db.Column(db.String(32))
    recon_settings = db.Column(db.Text()) # JSON
    step_state = db.Column(db.Integer, index=True) # -1 failed, 0 processing, 1 processing, 2 completed
    status_msg = db.Column(db.Text())
    full_status_msg = db.Column(db.Text())
    imgs = db.Column(db.Integer)
    expected_imgs = db.Column(db.Integer)
    visible = db.Column(db.Boolean, default=True) # Task should be shown on frontend
    
    # One-to-many relationships (as child)
    series = db.Column(db.String(64), db.ForeignKey('series.SeriesInstanceUID')) 
    source = db.Column(db.String(96), db.ForeignKey('source.identifier'))   
    radiopharmaceutical = db.Column(db.String(64), db.ForeignKey('radiopharmaceutical.name'))

    # One-to-many relationships (as parent)
    result_series = db.relationship('Series', backref='result_task', lazy='dynamic', foreign_keys='Series.originating_task', cascade='all, delete-orphan')

    # Many-to-many relationships (as parent)
    destinations = db.relationship('Device', secondary=task_destination, backref='tasks')  
    instances =  db.relationship('Instance', secondary=task_instance, backref='tasks')

    def __repr__(self):
        return f'<Task {self.id}>'

@event.listens_for(Task, 'before_update')
def update_task_modified_timestamp(mapper, connection, target):
    # Perform actions before a Task instance is modified
    logger.debug(f"updating task {target.id}")
    target.updated = datetime.now()
    
@event.listens_for(Task, 'before_delete')
def delete_task(mapper, connection, target):
    # Delete originating series if it is not related to other tasks
    logger.info(f"deleting task {target.id}")
    
    source_series = Series.query.get(target.series)
    if source_series:
        has_other_related_tasks = db.session.query(db.exists().where(Task.series == source_series.SeriesInstanceUID, Task.id != target.id)).scalar()
        if not has_other_related_tasks:
            logger.info(f"task {target.id} deleting source series {source_series.SeriesInstanceUID}")
            db.session.delete(source_series)        
        else:
            logger.info(f"task {target.id} source series {source_series.SeriesInstanceUID} won't be deleted")
    else:
        logger.info(f"task {target.id} source series not found")

class AppLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.now)
    level = db.Column(db.String(64), index=True)
    module = db.Column(db.String(64), index=True)
    function = db.Column(db.String(64), index=True)
    msg = db.Column(db.String(256))
    
    def __repr__(self):
        return f"{self.timestamp.strftime('%Y/%m/%d %H:%M:%S')} | {self.level} | {self.module} | {self.function} | {self.msg}"    

class AppConfig(db.Model):    
    client_id = db.Column(db.String(64), default='GenericClient', primary_key=True)    
    min_instances_in_series = db.Column(db.Integer, default=47)
    slice_gap_tolerance = db.Column(db.Float, default=0.025)
    series_timeout = db.Column(db.Integer, default=30)
    store_scp_port = db.Column(db.Integer, default=os.getenv('DICOM_LISTENER_PORT'))
    store_scp_aet = db.Column(db.String(64), default='PETFECTIOR')
    ip_address = db.Column(db.String(12), default = '')
    mirror_mode = db.Column(db.Boolean, default=False)
    server_url = db.Column(db.String(64), default=os.getenv('SERVER_ADDRESS') + ':' + os.getenv('SERVER_PORT') )    
    shared_mount_point = db.Column(db.String(128), default=os.getenv('SHARED_MOUNT_POINT') or 'shared')
    zip_dir = db.Column(db.String(128), default=os.path.join('temp','packed_series'))
    unzip_dir = db.Column(db.String(128), default=os.path.join('temp','unpacked_series'))
    download_path = db.Column(db.String(128), default=os.path.join('temp','series_to_unpack'))

    def __repr__(self):
        return f"<AppConfig for client {self.client_id}>"    

class FilterSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fwhm = db.Column(db.Float, default = 0)
    description = db.Column(db.String(128), default = '')
    mode = db.Column(db.String(32), default = 'append')
    series_number = db.Column(db.Integer, default = '1001')
    noise = db.Column(db.Float, default = 0)
    model = db.Column(db.String(64), default = 'all')
    radiopharmaceutical = db.Column(db.String(64), default = 'all')
    enabled = db.Column(db.Boolean, default = True)

    def __repr__(self):
        return f"Recon '{self.description}' | {self.fwhm}mm | {'Enabled' if self.enabled else 'Disabled'}"

class PetModel(db.Model):
    name = db.Column(db.String(64), primary_key = True)

    def __repr__(self):
        return f"PET Model {self.name}"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password = db.Column(db.String(64))

    def __repr__(self):
        return f'<User {self.username}>'    
    
class Radiopharmaceutical(db.Model):
    name = db.Column(db.String(64), primary_key=True, nullable=False)
    synonyms = db.Column(db.Text())
    half_life = db.Column(db.Float())

    # One-to-many relationships (as parent)
    related_tasks = db.relationship('Task', backref='task_radiopharmaceutical', lazy='dynamic')

    def __repr__(self):
        return f"Radiopharmaceutical {self.name}"

@login.user_loader
def load_user(id):
    return User.query.get(int(id))