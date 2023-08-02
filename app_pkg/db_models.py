from app_pkg import db
from datetime import datetime

class AppLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    level = db.Column(db.String(64), index=True)
    module = db.Column(db.String(64), index=True)
    function = db.Column(db.String(64), index=True)
    msg = db.Column(db.String(256))

    def __repr__(self):
        return f"{self.timestamp.strftime('%Y/%m/%d %H:%M:%S')} | {self.level} | {self.module} | {self.function} | {self.msg}"

