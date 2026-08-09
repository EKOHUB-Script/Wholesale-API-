import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')
    daily_upload_count = db.Column(db.Integer, default=0)
    last_upload_date = db.Column(db.Date, default=datetime.date.today)
    last_upload_time = db.Column(db.DateTime, nullable=True)
    username = db.Column(db.String(100), nullable=True) # 🆕 추가
    avatar_url = db.Column(db.String(255), nullable=True) # 🆕 추가

class Script(db.Model):
    __tablename__ = 'scripts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def to_dict(self, current_user):
        is_owner = (current_user and self.owner_id == current_user.id)
        is_admin = (current_user and current_user.role == 'admin')
        
        # 스크립트 소유자 정보 가져오기
        owner = User.query.get(self.owner_id) if self.owner_id else None
        owner_name = owner.username if owner else "Unknown"
        owner_avatar = owner.avatar_url if owner else None
        
        return {
            'name': self.name,
            'url': f"https://script.ekohub.xyz/{self.name}",
            'owner_id': self.owner_id,
            'owner_name': owner_name, # 🆕 추가
            'owner_avatar': owner_avatar, # 🆕 추가
            'can_edit': is_owner or is_admin,
            'can_delete': is_owner or is_admin
        }
