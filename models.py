import datetime
from flask_sqlalchemy import SQLAlchemy

# db 객체를 여기서 생성합니다.
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')
    daily_upload_count = db.Column(db.Integer, default=0)
    last_upload_date = db.Column(db.Date, default=datetime.date.today)
    last_upload_time = db.Column(db.DateTime, nullable=True)

class Script(db.Model):
    __tablename__ = 'scripts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def to_dict(self, current_user):
        is_owner = (current_user and self.owner_id == current_user.id)
        is_admin = (current_user and current_user.role == 'admin')
        
        return {
            'name': self.name,
            'url': f"https://script.ekohub.xyz/{self.name}",
            'owner_id': self.owner_id,
            'can_edit': is_owner or is_admin,
            'can_delete': is_owner or is_admin
        }
