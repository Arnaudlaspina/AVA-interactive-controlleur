from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    sections = db.relationship('Section', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    context = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    exchanges = db.relationship('Exchange', backref='section', lazy=True)

    def __repr__(self):
        return f"<Section {self.id} for User {self.user_id}>"


class Exchange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_input = db.Column(db.Text, nullable=False)
    gpt_output = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)

    def __repr__(self):
        return f"<Exchange {self.id} at {self.timestamp}>"

