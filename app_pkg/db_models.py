from app_pkg import db
from datetime import datetime

# Association tables for many-to-many relationships
task_destination = db.Table('task_destination',
                            db.Column('task_id', db.String(18), db.ForeignKey('task.id')),
                            db.Column('device_name', db.String(64), db.ForeignKey('device.name')))

class Patient(db.Model):
    PatientID = db.Column(db.String(64), primary_key=True)
    PatientName = db.Column(db.String(64), index=True)

    # Cross-references down
    studies = db.relationship('Study', backref='patient', lazy='dynamic')    
    series = db.relationship('Series', backref='patient', lazy='dynamic')    
    instances = db.relationship('Instance', backref='patient', lazy='dynamic')    
    
    def __repr__(self):
        return f'<Patient {self.PatientName}>'
    
class Study(db.Model):

    StudyInstanceUID = db.Column(db.String(64), primary_key=True)
    StudyDate = db.Column(db.DateTime, index=True)    
    StudyDescription = db.Column(db.String(64), index=True)

    # Cross-references up
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))

    # Cross-references down
    series = db.relationship('Series', backref='study', lazy='dynamic')    
    instances = db.relationship('Instance', backref='study', lazy='dynamic')     

    def __repr__(self):
        return f'<Study {self.StudyDescription} from {self.PatientID}>'
    
class Series(db.Model):

    SeriesInstanceUID = db.Column(db.String(64), primary_key=True)
    SeriesDate = db.Column(db.DateTime, index=True)
    SeriesDescription = db.Column(db.String(64), index=True)
    Modality = db.Column(db.String(64), index=True)
    metadata_fname = db.Column(db.Text(), index=True)

    # One-to-many relationships (as child)
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))
    StudyInstanceUID = db.Column(db.String(64), db.ForeignKey('study.StudyInstanceUID'))

    # One-to-many relationships (as parent)
    instances = db.relationship('Instance', backref='series', lazy='dynamic')
    tasks = db.relationship('Task', backref='task_series', lazy='dynamic')     

    def __repr__(self):
        return f'<Series {self.SeriesDescription} from {self.PatientID}>'    
    
class Instance(db.Model):

    SOPInstanceUID = db.Column(db.String(64), primary_key=True)
    SOPClassUID = db.Column(db.String(64), index=True)   
    filename = db.Column(db.Text(), index=True)

    # One-to-many relationships (as child)
    PatientID = db.Column(db.String(64), db.ForeignKey('patient.PatientID'))
    StudyInstanceUID = db.Column(db.String(64), db.ForeignKey('study.StudyInstanceUID'))
    SeriesInstanceUID = db.Column(db.String(64), db.ForeignKey('series.SeriesInstanceUID'))     

    def __repr__(self):
        return f'<Instance {self.SOPClassUID} from {self.PatientID} stored at {self.filename}>'
    
class Device(db.Model):

    name = db.Column(db.String(64), primary_key=True)
    ae_title = db.Column(db.String(64), index=True)
    address = db.Column(db.String(16), index=True)
    port = db.Column(db.Integer(), index=True)

    def __repr__(self):
        return f'<Device {self.name}: {self.ae_title}@{self.address}>'
    
class Task(db.Model):
    id = db.Column(db.String(18), primary_key=True)
    source_addr = db.Column(db.String(16))
    source_aet = db.Column(db.String(16))
    started = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    current_step = db.Column(db.String(32))
    current_step_filename = db.Column(db.Text(), index=True)

    # One-to-many relationships (as child)
    series = db.Column(db.String(64), db.ForeignKey('series.SeriesInstanceUID'))    

    # Many-to-many relationships (as parent)
    destinations = db.relationship('Device', secondary=task_destination, backref='tasks')    

    def __repr__(self):
        return f'<Task {self.id}>'

class AppLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    level = db.Column(db.String(64), index=True)
    module = db.Column(db.String(64), index=True)
    function = db.Column(db.String(64), index=True)
    msg = db.Column(db.String(256))

    def __repr__(self):
        return f"{self.timestamp.strftime('%Y/%m/%d %H:%M:%S')} | {self.level} | {self.module} | {self.function} | {self.msg}"