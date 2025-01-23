from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from datetime import timedelta
import os

db = SQLAlchemy()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'customer' or 'professional'
    category = db.Column(db.String(50), nullable=True)  # Professional's work category
    is_blocked = db.Column(db.Boolean, default=False)  


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    base_price = db.Column(db.Float, nullable=True)  # Service price
    time_required = db.Column(db.Integer)  # Time required for service (in minutes)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending')
    approval_status = db.Column(db.String(20), default='Pending')

    customer = db.relationship('User', foreign_keys=[customer_id], lazy='joined')
    professional = db.relationship('User', foreign_keys=[professional_id], lazy='joined')

  
   
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        role = request.form['role']
        email=request.form['email']
        
        
        if User.query.filter_by(username=username).first():
            return redirect(url_for('register'))
        
        new_user = User(username=username, password=password, role=role, email = email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/select-category', methods=['GET', 'POST'])
@login_required
def select_category():
    if current_user.role != 'professional':
        return redirect(url_for('home'))  # Redirect if not a professional
    
    if request.method == 'POST':
        category = request.form['category']
        current_user.category = category
        db.session.commit()
        return redirect(url_for('professional_dashboard'))

    return render_template('select-category.html')


@app.route('/professional-dashboard')
@login_required
def professional_dashboard():
    if current_user.role != 'professional':
        return redirect(url_for('home'))
    
    bookings = Booking.query.filter_by(professional_id=current_user.id).all()

    for booking in bookings:
        booking.service_date = booking.booking_date.date() 
        updated_datetime = booking.booking_date + timedelta(hours=2) 
        booking.arrival_time = updated_datetime.time()

    return render_template('professional-dashboard.html', bookings=bookings)

@app.route('/customer-dashboard', methods=['GET', 'POST'])
@login_required
def customer_dashboard():
    if current_user.role != 'customer':
        return redirect(url_for('home'))
    
    categories = ['beauty', 'cleaning', 'plumbing', 'electrical']
    
    selected_category = request.args.get('category', default='', type=str)
    
    if selected_category:
        professionals = User.query.filter_by(role='professional', category=selected_category).all()
    else:
        professionals = User.query.filter_by(role='professional').all()

    bookings = Booking.query.filter_by(customer_id=current_user.id).all()
    for booking in bookings:
        booking.service_date = booking.booking_date.date() 
        updated_datetime = booking.booking_date + timedelta(hours=2)  
        booking.arrival_time = updated_datetime.time()

    return render_template('customer-dashboard.html', professionals=professionals, bookings=bookings, categories=categories, selected_category=selected_category)

@app.route('/approve-booking/<int:booking_id>', methods=['POST'])
@login_required
def approve_booking(booking_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    booking = Booking.query.get_or_404(booking_id)
    booking.approval_status = 'Approved' 
    booking.status = 'Pending' 
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/accept_booking/<int:booking_id>', methods=['POST'])
@login_required
def accept_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    if current_user.id != booking.professional_id:
        return redirect(url_for('professional_dashboard'))
    
    if booking.approval_status != 'Approved': 
        return redirect(url_for('professional_dashboard'))
    
    booking.status = 'Accepted'
    db.session.commit()
    return redirect(url_for('professional_dashboard'))


@app.route('/reject_booking/<int:booking_id>', methods=['POST'])
@login_required
def reject_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    if current_user.id != booking.professional_id:
        return redirect(url_for('professional_dashboard'))
    
    if booking.approval_status != 'Approved':  
        return redirect(url_for('professional_dashboard'))
    
    booking.status = 'Rejected'
    db.session.commit()
    return redirect(url_for('professional_dashboard'))



@app.route('/book_professional', methods=['POST'])
@login_required
def book_professional():
    professional_id = request.form.get('professional_id')
    customer_id = current_user.id

    if customer_id and professional_id:
        professional = User.query.get(professional_id)
        if not professional or professional.role != 'professional':
            return redirect(url_for('customer_dashboard'))
        
        category = professional.category
        if category == 'beauty':
            base_price = 500.0  
            time_required = 60  
        elif category == 'cleaning':
            base_price = 300.0
            time_required = 90
        elif category == 'plumbing':
            base_price = 700.0
            time_required = 120
        elif category == 'electrical':
            base_price = 800.0
            time_required = 150
        else:
            return redirect(url_for('customer_dashboard'))
        
        new_booking = Booking(
            customer_id=customer_id,
            professional_id=professional_id,
            base_price=base_price,  
            time_required=time_required, 
            booking_date=datetime.utcnow()
        )

        db.session.add(new_booking)
        db.session.commit()
    return redirect(url_for('customer_dashboard'))

@app.route('/show_professionals', methods=['POST'])
def show_professionals():
    category = request.form.get('category')
    professionals = User.query.filter_by(role='professional', category=category).all()
    return render_template('customer_dashboard.html', user=current_user, professionals=professionals)

@app.route('/view_professional/<int:professional_id>')
@login_required
def view_professional(professional_id):
    professional = User.query.get_or_404(professional_id)
    if professional.role != 'professional':
        return redirect(url_for('customer_dashboard'))
    
    return render_template('view_professional.html', professional=professional)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user:
            if user.is_blocked:  
                return redirect(url_for('login'))
            
            if check_password_hash(user.password, password): 
                login_user(user)
                
                if user.role == 'professional':
                    if not user.category:
                        return redirect(url_for('select_category'))
                    else:
                        return redirect(url_for('professional_dashboard'))
                elif user.role == 'customer':
                    return redirect(url_for('customer_dashboard'))
                elif user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
        
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('home'))
    customers = User.query.filter_by(role='customer').all()
    professionals = User.query.filter_by(role='professional').all()
    bookings = Booking.query.all()
    return render_template('admin-dashboard.html', customers=customers, professionals=professionals, bookings=bookings)

@app.route('/block_booking/<int:booking_id>', methods=['POST'])
@login_required
def block_booking(booking_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'Blocked' 
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/block-user/<int:id>', methods=['POST'])
@login_required
def block_user(id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    user = User.query.get(id)
    user.is_blocked = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/unblock-user/<int:id>', methods=['POST'])
@login_required
def unblock_user(id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    user = User.query.get(id)
    user.is_blocked = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/create-service', methods=['GET', 'POST'])
@login_required
def create_service():
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        service_name = request.form['service_name']
        base_price = request.form['base_price']
        description = request.form['description']
        time_required = request.form['time_required']

        new_service = Booking(
            service_name=service_name, 
            base_price=base_price, 
            description=description, 
            time_required=time_required
        )
        db.session.add(new_service)
        db.session.commit()
    return render_template('create-service.html')

@app.route('/approve-professional/<int:id>', methods=['GET', 'POST'])
@login_required
def approve_professional(id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    professional = User.query.get(id)
    professional.status = 'approved' 
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/about_us', methods=['GET'])
def about_us():
    return render_template('about-us.html', user=current_user )

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':       
        return redirect(url_for('thank_you'))
    return render_template('feedback.html', user=current_user)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():     
    return redirect(url_for('thank_you'))

@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/services')
def services():
    return render_template('services.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
