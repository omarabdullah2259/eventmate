import os
from functools import wraps
from flask import Flask, render_template, redirect, url_for, session, request
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
secret_key = os.environ.get('FLASK_SECRET_KEY')
if not secret_key:
    raise RuntimeError('FLASK_SECRET_KEY environment variable is required. Do not store secrets in source code.')
app.secret_key = secret_key

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eventmate.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

oauth = OAuth(app)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        access_token_url='https://oauth2.googleapis.com/token',
        authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
        api_base_url='https://openidconnect.googleapis.com/v1/',
        client_kwargs={'scope': 'openid email profile', 'prompt': 'select_account'},
    )

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    state = db.Column(db.String(120))
    city = db.Column(db.String(120))
    street = db.Column(db.String(120))
    house_number = db.Column(db.String(20))
    password_hash = db.Column(db.String(200))
    auth_method = db.Column(db.String(20))  # 'password', 'google'
    joined_events = db.relationship('EventJoin', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'state': self.state,
            'city': self.city,
            'street': self.street,
            'house_number': self.house_number,
            'auth_method': self.auth_method
        }


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(120))
    category = db.Column(db.String(60))
    joined_users = db.relationship('EventJoin', backref='event', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date,
            'location': self.location,
            'language': self.language,
            'category': self.category,
            'attendees': [ej.user.name for ej in self.joined_users]
        }


class EventJoin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)


def init_db():
    """Initialize database with sample events"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Check if events already exist
        if Event.query.first() is None:
            nrw_events = [
                {
                    'title': 'Rhine in Flames (Bonn)',
                    'date': '2026-05-10',
                    'location': 'Bonn',
                    'language': 'English-friendly',
                    'category': 'Cultural',
                },
                {
                    'title': 'Essen Original Festival',
                    'date': '2026-05-08',
                    'location': 'Essen',
                    'language': 'English-friendly',
                    'category': 'Music',
                },
                {
                    'title': 'Ruhr Festival',
                    'date': '2026-05-01',
                    'location': 'Recklinghausen',
                    'language': 'English-friendly',
                    'category': 'Cultural',
                },
                {
                    'title': 'Rock Hard Festival',
                    'date': '2026-05-22',
                    'location': 'Gelsenkirchen',
                    'language': 'English-friendly',
                    'category': 'Music',
                },
                {
                    'title': 'Ruhr Piano Festival',
                    'date': '2026-05-01',
                    'location': 'Multiple cities in NRW',
                    'language': 'English-friendly',
                    'category': 'Music',
                },
                {
                    'title': 'Dreamtime Festival',
                    'date': '2026-06-19',
                    'location': 'Duisburg',
                    'language': 'English-friendly',
                    'category': 'Music',
                },
                {
                    'title': 'Bochum Total',
                    'date': '2026-07-02',
                    'location': 'Bochum',
                    'language': 'English-friendly',
                    'category': 'Music',
                },
            ]
            
            for event_data in nrw_events:
                event = Event(**event_data)
                db.session.add(event)
            
            db.session.commit()


def auth_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session and 'guest' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def get_current_user():
    """Get current user from database"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


@app.route('/')
@auth_required
def index():
    user = get_current_user()
    guest = session.get('guest')
    events = Event.query.all()
    joined_event_ids = [ej.event_id for ej in user.joined_events] if user else []
    
    return render_template(
        'index.html',
        events=[e.to_dict() for e in events],
        user=user.to_dict() if user else None,
        guest=guest,
        joined_events=joined_event_ids
    )


@app.route('/join/<int:event_id>')
@auth_required
def join_event(event_id):
    if session.get('guest'):
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    event = Event.query.get(event_id)
    if not event:
        return "Event not found", 404
    
    # Check if already joined
    existing_join = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if not existing_join:
        join = EventJoin(user_id=user.id, event_id=event_id)
        db.session.add(join)
        db.session.commit()
    
    return redirect(url_for('find_people', event_id=event_id))


@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    return render_template(
        'login.html',
        google_enabled=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        user=None,
        guest=session.get('guest')
    )


@app.route('/login/guest')
def login_guest():
    session['guest'] = True
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        state = request.form.get('state', '').strip()
        city = request.form.get('city', '').strip()
        street = request.form.get('street', '').strip()
        house_number = request.form.get('house_number', '').strip()
        password = request.form.get('password', '').strip()

        if not (first_name and last_name and state and street and house_number and password):
            return render_template('signup.html', error='Please fill in all fields.')

        if state == 'North Rhine-Westphalia' and not city:
            return render_template('signup.html', error='Please select a city for North Rhine-Westphalia.')

        full_name = f'{first_name} {last_name}'
        
        # Check if user already exists
        if User.query.filter_by(name=full_name).first():
            return render_template('signup.html', error='Name already exists. Please choose another.')

        # Create new user
        user = User(
            name=full_name,
            first_name=first_name,
            last_name=last_name,
            state=state,
            city=city,
            street=street,
            house_number=house_number,
            password_hash=generate_password_hash(password),
            auth_method='password'
        )
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        session.pop('guest', None)
        return redirect(url_for('index'))

    return render_template('signup.html')


@app.route('/login/google')
def login_google():
    session.pop('guest', None)
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        redirect_uri = url_for('authorize', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    return render_template('login.html', google_enabled=False, error='Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable login.')


@app.route('/login/manual', methods=['POST'])
def login_manual():
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()

    user = User.query.filter_by(name=name, auth_method='password').first()
    
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session.pop('guest', None)
        return redirect(url_for('index'))
    else:
        return render_template(
            'login.html',
            google_enabled=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
            error='Invalid name or password.',
            user=None,
            guest=None
        )


@app.route('/auth')
def authorize():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return render_template('login.html', google_enabled=False, error='Google OAuth is not configured. Contact the app owner to enable login.')

    token = oauth.google.authorize_access_token()
    user_info = oauth.google.get('userinfo').json()
    
    # Check if user exists
    user = User.query.filter_by(email=user_info.get('email')).first()
    
    if not user:
        # Create new user from Google
        user = User(
            email=user_info.get('email'),
            name=user_info.get('name'),
            first_name=user_info.get('given_name', ''),
            last_name=user_info.get('family_name', ''),
            auth_method='google'
        )
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session.pop('guest', None)
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('guest', None)
    return redirect(url_for('login'))


@app.route('/find_people/<int:event_id>')
@auth_required
def find_people(event_id):
    event = Event.query.get(event_id)
    
    if not event:
        return "Event not found", 404
    
    user = get_current_user()
    guest = session.get('guest')
    
    joined = False
    if user:
        join = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
        joined = join is not None
    
    # Hide attendees for guests
    if guest:
        attendees = []
    else:
        attendees = [ej.user.name for ej in event.joined_users]
    
    return render_template(
        'find_people.html',
        event=event.to_dict(),
        user=user.to_dict() if user else None,
        guest=guest,
        joined=joined,
        attendees=attendees
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=True)