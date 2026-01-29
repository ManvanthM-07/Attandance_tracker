import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'attendance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, user, manager
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='present')  # present, absent, late, leave
    notes = db.Column(db.String(255))
    date = db.Column(db.Date, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username,
            'check_in_time': self.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_out_time else None,
            'status': self.status,
            'notes': self.notes,
            'date': self.date.strftime('%Y-%m-%d')
        }


# Routes
@app.route("/")
def index():
    return render_template("index.html")


# User Management Routes
@app.route("/api/users", methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/users", methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            email=data['email'],
            role=data.get('role', 'user')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'User created successfully', 'user': user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=['GET'])
def get_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'role' in data:
            user.role = data['role']
        
        db.session.commit()
        return jsonify({'message': 'User updated successfully', 'user': user.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Attendance Routes
@app.route("/api/attendance", methods=['GET'])
def get_attendance():
    try:
        date = request.args.get('date')
        user_id = request.args.get('user_id')
        
        query = Attendance.query
        
        if date:
            query = query.filter_by(date=datetime.strptime(date, '%Y-%m-%d').date())
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        attendance = query.all()
        return jsonify([record.to_dict() for record in attendance]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/attendance", methods=['POST'])
def mark_attendance():
    try:
        data = request.get_json()
        
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id is required'}), 400
        
        user = User.query.get(data['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if already checked in today
        today = datetime.utcnow().date()
        existing = Attendance.query.filter_by(
            user_id=data['user_id'],
            date=today
        ).first()
        
        if existing and not existing.check_out_time:
            # Update check_out time
            existing.check_out_time = datetime.utcnow()
            message = 'Check-out recorded successfully'
        else:
            # Create new attendance record
            attendance = Attendance(
                user_id=data['user_id'],
                status=data.get('status', 'present'),
                notes=data.get('notes', '')
            )
            db.session.add(attendance)
            message = 'Check-in recorded successfully'
        
        db.session.commit()
        return jsonify({'message': message}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route("/api/attendance/<int:attendance_id>", methods=['GET'])
def get_attendance_record(attendance_id):
    try:
        record = Attendance.query.get(attendance_id)
        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/attendance/<int:attendance_id>", methods=['PUT'])
def update_attendance(attendance_id):
    try:
        record = Attendance.query.get(attendance_id)
        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404
        
        data = request.get_json()
        
        if 'status' in data:
            record.status = data['status']
        if 'notes' in data:
            record.notes = data['notes']
        if 'check_out_time' in data:
            record.check_out_time = datetime.fromisoformat(data['check_out_time'])
        
        db.session.commit()
        return jsonify({'message': 'Attendance updated successfully', 'record': record.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route("/api/attendance/<int:attendance_id>", methods=['DELETE'])
def delete_attendance(attendance_id):
    try:
        record = Attendance.query.get(attendance_id)
        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404
        
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Attendance record deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Analytics Routes
@app.route("/api/analytics/summary", methods=['GET'])
def get_summary():
    try:
        total_users = User.query.count()
        total_present = Attendance.query.filter_by(status='present').count()
        total_absent = Attendance.query.filter_by(status='absent').count()
        total_late = Attendance.query.filter_by(status='late').count()
        
        return jsonify({
            'total_users': total_users,
            'total_present': total_present,
            'total_absent': total_absent,
            'total_late': total_late,
            'attendance_rate': round((total_present / (total_present + total_absent) * 100), 2) if (total_present + total_absent) > 0 else 0
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/analytics/user/<int:user_id>", methods=['GET'])
def get_user_analytics(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        total = Attendance.query.filter_by(user_id=user_id).count()
        present = Attendance.query.filter_by(user_id=user_id, status='present').count()
        absent = Attendance.query.filter_by(user_id=user_id, status='absent').count()
        late = Attendance.query.filter_by(user_id=user_id, status='late').count()
        
        return jsonify({
            'username': user.username,
            'total_records': total,
            'present': present,
            'absent': absent,
            'late': late,
            'attendance_percentage': round((present / total * 100), 2) if total > 0 else 0
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Health Check
@app.route("/api/health", methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Attendance Tracker is running'}), 200


# Initialize Database
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)