from app import db
from datetime import datetime
from sqlalchemy import func

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512), nullable=False)
    title = db.Column(db.String(256))
    platform = db.Column(db.String(50))  # 'youtube' or 'instagram'
    format_type = db.Column(db.String(20), default='video')  # 'video' or 'audio'
    status = db.Column(db.String(50), default='pending')  # pending, downloading, completed, failed
    progress = db.Column(db.Integer, default=0)  # 0-100
    filename = db.Column(db.String(256))
    file_size = db.Column(db.String(50))
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Download {self.id}: {self.title or self.url}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'platform': self.platform,
            'format_type': self.format_type,
            'status': self.status,
            'progress': self.progress,
            'filename': self.filename,
            'file_size': self.file_size,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
