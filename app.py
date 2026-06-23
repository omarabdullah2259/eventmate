import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
secret_key = os.environ.get('FLASK_SECRET_KEY')
if not secret_key:
    raise RuntimeError('FLASK_SECRET_KEY environment variable is required.')
app.secret_key = secret_key

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

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

CATEGORIES = [
    'Music', 'Sports', 'Gaming', 'Food', 'Technology', 'Cultural', 'Culture',
    'Business', 'Workshop', 'Career', 'Language Exchange',
    'Art', 'Cinema', 'Festival', 'Market', 'Networking', 'Theatre',
]
CATEGORY_ICONS = {
    'Music': '🎵', 'Sports': '⚽', 'Gaming': '🎮', 'Food': '🍔',
    'Technology': '💻', 'Cultural': '🎭', 'Culture': '🎭',
    'Business': '💼', 'Workshop': '🔧', 'Career': '🎓',
    'Language Exchange': '🗣️', 'Art': '🎨', 'Cinema': '🎬',
    'Festival': '🎉', 'Market': '🛍️', 'Networking': '🤝',
    'Theatre': '🎭',
}
CATEGORY_COLORS = {
    'Music': 'linear-gradient(135deg,#6d28d9,#8b5cf6)',
    'Sports': 'linear-gradient(135deg,#065f46,#10b981)',
    'Gaming': 'linear-gradient(135deg,#1e3a8a,#3b82f6)',
    'Food': 'linear-gradient(135deg,#92400e,#f59e0b)',
    'Technology': 'linear-gradient(135deg,#0e7490,#22d3ee)',
    'Cultural': 'linear-gradient(135deg,#7c2d12,#f97316)',
    'Culture': 'linear-gradient(135deg,#7c2d12,#f97316)',
    'Business': 'linear-gradient(135deg,#1f2937,#6b7280)',
    'Workshop': 'linear-gradient(135deg,#312e81,#6366f1)',
    'Career': 'linear-gradient(135deg,#9d174d,#f43f5e)',
    'Language Exchange': 'linear-gradient(135deg,#0f766e,#14b8a6)',
    'Art': 'linear-gradient(135deg,#831843,#ec4899)',
    'Cinema': 'linear-gradient(135deg,#1c1917,#78716c)',
    'Festival': 'linear-gradient(135deg,#713f12,#eab308)',
    'Market': 'linear-gradient(135deg,#134e4a,#2dd4bf)',
    'Networking': 'linear-gradient(135deg,#1e3a5f,#60a5fa)',
    'Theatre': 'linear-gradient(135deg,#4a044e,#c026d3)',
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(field_name):
    if field_name not in request.files:
        return None
    f = request.files[field_name]
    if not f or f.filename == '':
        return None
    if allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        fname = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        return fname
    return None


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    state = db.Column(db.String(120))
    city = db.Column(db.String(120))
    street = db.Column(db.String(120))
    house_number = db.Column(db.String(20))
    password_hash = db.Column(db.String(200))
    auth_method = db.Column(db.String(20))
    university = db.Column(db.String(200))
    study_program = db.Column(db.String(200))
    languages = db.Column(db.Text)
    interests = db.Column(db.Text)
    about_me = db.Column(db.Text)
    profile_picture = db.Column(db.String(200))
    joined_events = db.relationship('EventJoin', backref='user', lazy=True, cascade='all, delete-orphan')
    created_events = db.relationship('Event', backref='organizer', lazy=True, foreign_keys='Event.organizer_id')

    def get_languages(self):
        return [l.strip() for l in self.languages.split(',') if l.strip()] if self.languages else []

    def get_interests(self):
        return [i.strip() for i in self.interests.split(',') if i.strip()] if self.interests else []

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'state': self.state,
            'city': self.city,
            'street': self.street,
            'house_number': self.house_number,
            'auth_method': self.auth_method,
            'university': self.university,
            'study_program': self.study_program,
            'languages': self.get_languages(),
            'interests': self.get_interests(),
            'about_me': self.about_me,
            'profile_picture': self.profile_picture,
        }


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(10))
    location = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(120))
    category = db.Column(db.String(60))
    description = db.Column(db.Text)
    max_participants = db.Column(db.Integer)
    banner = db.Column(db.String(200))
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    joined_users = db.relationship('EventJoin', backref='event', lazy=True, cascade='all, delete-orphan')

    def attendee_count(self):
        return len(self.joined_users)

    def to_dict(self):
        org = User.query.get(self.organizer_id) if self.organizer_id else None
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date,
            'time': self.time,
            'location': self.location,
            'language': self.language,
            'category': self.category,
            'description': self.description,
            'max_participants': self.max_participants,
            'banner': self.banner,
            'organizer_id': self.organizer_id,
            'organizer_name': org.name if org else 'EventMate',
            'organizer_username': org.username if org else None,
            'attendee_count': self.attendee_count(),
            'attendees': [ej.user.name for ej in self.joined_users],
            'category_color': CATEGORY_COLORS.get(self.category, 'linear-gradient(135deg,#1e3a8a,#3b82f6)'),
            'category_icon': CATEGORY_ICONS.get(self.category, '📅'),
        }


class EventJoin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender = db.relationship('User', lazy=True)


def init_db():
    with app.app_context():
        db.create_all()
        if Event.query.first() is None:
            seed_events = [
                {
                    'title': 'Rhine in Flames (Bonn)',
                    'date': '2026-09-12', 'time': '20:00',
                    'location': 'Bonn', 'language': 'English-friendly',
                    'category': 'Cultural',
                    'description': 'A spectacular fireworks festival along the Rhine river. Join thousands of visitors to enjoy the breathtaking light show reflected on the water. One of the most iconic events in NRW.',
                    'max_participants': 500,
                },
                {
                    'title': 'Essen Original Festival',
                    'date': '2026-08-21', 'time': '14:00',
                    'location': 'Essen', 'language': 'English-friendly',
                    'category': 'Music',
                    'description': 'A diverse cultural festival in the heart of Essen celebrating music, food, and art. Multiple stages, international food stalls, and live performances from local and international artists.',
                    'max_participants': 300,
                },
                {
                    'title': 'Ruhr Festival',
                    'date': '2026-09-01', 'time': '18:00',
                    'location': 'Recklinghausen', 'language': 'English-friendly',
                    'category': 'Cultural',
                    'description': 'One of Europe\'s largest theatre festivals with drama, opera, dance, and comedy. English subtitles available for select performances. A highlight of the NRW cultural calendar.',
                    'max_participants': 200,
                },
                {
                    'title': 'Rock Hard Festival',
                    'date': '2026-08-14', 'time': '16:00',
                    'location': 'Gelsenkirchen', 'language': 'English-friendly',
                    'category': 'Music',
                    'description': 'Germany\'s premier metal and rock festival at the iconic VELTINS-Arena. Three days of heavy music with international headliners and rising bands from across the globe.',
                    'max_participants': 1000,
                },
                {
                    'title': 'Ruhr Piano Festival',
                    'date': '2026-08-01', 'time': '19:30',
                    'location': 'Dortmund', 'language': 'English-friendly',
                    'category': 'Music',
                    'description': 'A world-class classical piano festival spanning multiple cities in the Ruhr area. Renowned pianists perform in unique industrial and cultural settings across NRW.',
                    'max_participants': 150,
                },
                {
                    'title': 'Dreamtime Festival',
                    'date': '2026-09-19', 'time': '15:00',
                    'location': 'Duisburg', 'language': 'English-friendly',
                    'category': 'Music',
                    'description': 'An electronic music and arts festival in Duisburg\'s inner harbour. Cutting-edge DJs, immersive art installations, and a stunning waterfront atmosphere.',
                    'max_participants': 400,
                },
                {
                    'title': 'Bochum Total',
                    'date': '2026-07-09', 'time': '12:00',
                    'location': 'Bochum', 'language': 'English-friendly',
                    'category': 'Music',
                    'description': 'Bochum\'s biggest free street music festival. Five days of live music across multiple outdoor stages, featuring over 100 bands across all genres. Free entry!',
                    'max_participants': 2000,
                },
                {
                    'title': 'International Tech Meetup NRW',
                    'date': '2026-07-20', 'time': '18:30',
                    'location': 'Düsseldorf', 'language': 'English',
                    'category': 'Technology',
                    'description': 'Monthly meetup for tech enthusiasts, students, and professionals. Talks on AI, web dev, and startups. Perfect networking opportunity for international students in the region.',
                    'max_participants': 80,
                },
                {
                    'title': 'Language Exchange Café',
                    'date': '2026-07-12', 'time': '17:00',
                    'location': 'Cologne', 'language': 'Multi-language',
                    'category': 'Language Exchange',
                    'description': 'Practice German, English, Arabic, French and more with native speakers in a cozy café. Welcoming environment for international students and newcomers to Germany.',
                    'max_participants': 50,
                },
                {
                    'title': 'Career Fair for International Students',
                    'date': '2026-07-25', 'time': '10:00',
                    'location': 'Dortmund', 'language': 'English',
                    'category': 'Career',
                    'description': 'Career fair designed for international students in Germany. Meet recruiters, get CV advice, and network with peers. Many companies offer English-speaking roles and sponsorships.',
                    'max_participants': 200,
                },
            ]
            for event_data in seed_events:
                db.session.add(Event(**event_data))
            db.session.commit()


def auth_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session and 'guest' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


@app.context_processor
def inject_nav():
    user = get_current_user()
    return dict(
        nav_user=user.to_dict() if user else None,
        is_guest=session.get('guest', False),
    )


@app.route('/')
@auth_required
def index():
    user = get_current_user()
    guest = session.get('guest')

    q = request.args.get('q', '').strip()
    active_category = request.args.get('category', '').strip()
    active_city = request.args.get('city', '').strip()
    active_language = request.args.get('language', '').strip()

    query = Event.query
    if q:
        query = query.filter(Event.title.ilike(f'%{q}%'))
    if active_category:
        query = query.filter(Event.category == active_category)
    if active_city:
        query = query.filter(Event.location.ilike(f'%{active_city}%'))
    if active_language:
        query = query.filter(Event.language.ilike(f'%{active_language}%'))

    events = query.order_by(Event.date).all()
    joined_event_ids = [ej.event_id for ej in user.joined_events] if user else []

    return render_template(
        'index.html',
        events=[e.to_dict() for e in events],
        user=user.to_dict() if user else None,
        guest=guest,
        joined_events=joined_event_ids,
        categories=CATEGORIES,
        category_icons=CATEGORY_ICONS,
        active_q=q,
        active_category=active_category,
        active_city=active_city,
        active_language=active_language,
        total_events=Event.query.count(),
        total_users=User.query.count(),
    )


@app.route('/event/<int:event_id>')
@auth_required
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    user = get_current_user()
    guest = session.get('guest')

    joined = False
    if user:
        joined = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first() is not None

    attendees = []
    if not guest:
        for ej in event.joined_users:
            a = ej.user
            common = []
            if user and a.id != user.id:
                if a.university and a.university == user.university:
                    common.append(f'Studies at {a.university}')
                if a.city and a.city == user.city:
                    common.append(f'Lives in {a.city}')
                shared_langs = set(a.get_languages()) & set(user.get_languages())
                if shared_langs:
                    common.append(f'Speaks {", ".join(shared_langs)}')
                shared_interests = set(a.get_interests()) & set(user.get_interests())
                if shared_interests:
                    common.append(f'Likes {", ".join(list(shared_interests)[:3])}')
            attendees.append({
                'id': a.id,
                'name': a.name,
                'username': a.username,
                'university': a.university,
                'study_program': a.study_program,
                'profile_picture': a.profile_picture,
                'city': a.city,
                'languages': a.get_languages(),
                'interests': a.get_interests(),
                'common': common,
                'is_self': bool(user and a.id == user.id),
            })

    organizer = User.query.get(event.organizer_id) if event.organizer_id else None
    is_organizer = bool(user and organizer and user.id == organizer.id)

    return render_template(
        'event_detail.html',
        event=event.to_dict(),
        user=user.to_dict() if user else None,
        guest=guest,
        joined=joined,
        attendees=attendees,
        organizer=organizer,
        is_organizer=is_organizer,
    )


@app.route('/join/<int:event_id>')
@auth_required
def join_event(event_id):
    if session.get('guest'):
        return redirect(url_for('login'))
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    event = Event.query.get_or_404(event_id)
    existing = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if not existing:
        if event.max_participants is None or event.attendee_count() < event.max_participants:
            db.session.add(EventJoin(user_id=user.id, event_id=event_id))
            db.session.commit()
    return redirect(url_for('event_detail', event_id=event_id))


@app.route('/unjoin/<int:event_id>', methods=['POST'])
@login_required
def unjoin_event(event_id):
    user = get_current_user()
    join = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if join:
        db.session.delete(join)
        db.session.commit()
    return redirect(url_for('event_detail', event_id=event_id))


@app.route('/find_people/<int:event_id>')
def find_people(event_id):
    return redirect(url_for('event_detail', event_id=event_id))


def _chat_message_to_dict(msg):
    return {
        'id': msg.id,
        'event_id': msg.event_id,
        'user_id': msg.user_id,
        'message': msg.message,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'sender_name': msg.sender.name if msg.sender else 'Unknown',
        'profile_picture': msg.sender.profile_picture if msg.sender else None,
    }


@app.route('/event/<int:event_id>/chat')
@login_required
def event_chat(event_id):
    user = get_current_user()
    event = Event.query.get_or_404(event_id)
    joined = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if not joined:
        return render_template('error.html',
            title='Access Denied',
            message='You must join this event before accessing the group chat.',
            back_url=url_for('event_detail', event_id=event_id)), 403

    messages = ChatMessage.query.filter_by(event_id=event_id)\
        .order_by(ChatMessage.timestamp.asc()).all()

    member_ids = [ej.user_id for ej in EventJoin.query.filter_by(event_id=event_id).all()]
    members = User.query.filter(User.id.in_(member_ids)).all()

    event_dict = event.to_dict()

    return render_template('chat.html',
        event=event_dict,
        user=user.to_dict() if hasattr(user, 'to_dict') else {
            'id': user.id, 'name': user.name, 'username': user.username,
            'profile_picture': user.profile_picture,
        },
        messages=[_chat_message_to_dict(m) for m in messages],
        members=members,
    )


@app.route('/event/<int:event_id>/chat/send', methods=['POST'])
@login_required
def event_chat_send(event_id):
    user = get_current_user()
    event = Event.query.get_or_404(event_id)
    joined = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if not joined:
        return jsonify({'ok': False, 'error': 'You must join the event first.'}), 403

    data = request.get_json(silent=True) or {}
    text = (data.get('message') or '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'Message cannot be empty.'}), 400
    if len(text) > 2000:
        return jsonify({'ok': False, 'error': 'Message is too long (max 2000 chars).'}), 400

    msg = ChatMessage(event_id=event_id, user_id=user.id, message=text)
    db.session.add(msg)
    db.session.commit()
    db.session.refresh(msg)

    return jsonify({'ok': True, 'message': _chat_message_to_dict(msg)})


@app.route('/event/<int:event_id>/chat/messages')
@login_required
def event_chat_messages(event_id):
    user = get_current_user()
    joined = EventJoin.query.filter_by(user_id=user.id, event_id=event_id).first()
    if not joined:
        return jsonify({'ok': False, 'error': 'Access denied.'}), 403

    after_id = request.args.get('after', 0, type=int)
    msgs = ChatMessage.query.filter(
        ChatMessage.event_id == event_id,
        ChatMessage.id > after_id
    ).order_by(ChatMessage.timestamp.asc()).all()

    return jsonify({'ok': True, 'messages': [_chat_message_to_dict(m) for m in msgs]})


@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    user = get_current_user()
    error = None
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        date = request.form.get('date', '').strip()
        location = request.form.get('location', '').strip()
        if not (title and date and location):
            error = 'Title, date, and location are required.'
        else:
            mp_raw = request.form.get('max_participants', '').strip()
            banner = save_upload('banner')
            event = Event(
                title=title,
                date=date,
                time=request.form.get('time', '').strip(),
                location=location,
                language=request.form.get('language', '').strip(),
                category=request.form.get('category', '').strip(),
                description=request.form.get('description', '').strip(),
                max_participants=int(mp_raw) if mp_raw.isdigit() else None,
                banner=banner,
                organizer_id=user.id,
            )
            db.session.add(event)
            db.session.commit()
            return redirect(url_for('dashboard'))
    return render_template('create_event.html', user=user.to_dict(), categories=CATEGORIES, error=error)


@app.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    user = get_current_user()
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != user.id:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        event.title = request.form.get('title', event.title).strip()
        event.date = request.form.get('date', event.date).strip()
        event.time = request.form.get('time', event.time or '').strip()
        event.location = request.form.get('location', event.location).strip()
        event.language = request.form.get('language', event.language or '').strip()
        event.category = request.form.get('category', event.category or '').strip()
        event.description = request.form.get('description', event.description or '').strip()
        mp_raw = request.form.get('max_participants', '').strip()
        event.max_participants = int(mp_raw) if mp_raw.isdigit() else None
        new_banner = save_upload('banner')
        if new_banner:
            event.banner = new_banner
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_event.html', user=user.to_dict(), event=event.to_dict(), categories=CATEGORIES, editing=True, error=error)


@app.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    user = get_current_user()
    event = Event.query.get_or_404(event_id)
    if event.organizer_id == user.id:
        db.session.delete(event)
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    my_events = Event.query.filter_by(organizer_id=user.id).order_by(Event.date).all()
    total_attendees = sum(e.attendee_count() for e in my_events)
    return render_template(
        'dashboard.html',
        user=user.to_dict(),
        my_events=[e.to_dict() for e in my_events],
        total_attendees=total_attendees,
    )


@app.route('/profile/<int:user_id>')
@auth_required
def profile(user_id):
    current_user = get_current_user()
    guest = session.get('guest')
    profile_user = User.query.get_or_404(user_id)
    joined_events = [ej.event for ej in profile_user.joined_events]
    is_own = bool(current_user and current_user.id == user_id)
    return render_template(
        'profile.html',
        profile_user=profile_user,
        user=current_user.to_dict() if current_user else None,
        guest=guest,
        joined_events=[e.to_dict() for e in joined_events],
        is_own=is_own,
    )


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = get_current_user()
    if request.method == 'POST':
        user.university = request.form.get('university', '').strip() or None
        user.study_program = request.form.get('study_program', '').strip() or None
        user.about_me = request.form.get('about_me', '').strip() or None
        langs = request.form.get('languages', '').strip()
        user.languages = langs if langs else None
        interests = request.form.get('interests', '').strip()
        user.interests = interests if interests else None
        new_pic = save_upload('profile_picture')
        if new_pic:
            user.profile_picture = new_pic
        db.session.commit()
        return redirect(url_for('profile', user_id=user.id))
    return render_template('edit_profile.html', user=user.to_dict())


@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template(
        'login.html',
        google_enabled=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        user=None,
        guest=session.get('guest'),
    )


@app.route('/login/guest')
def login_guest():
    session['guest'] = True
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        state = request.form.get('state', '').strip()
        city = request.form.get('city', '').strip()
        street = request.form.get('street', '').strip()
        house_number = request.form.get('house_number', '').strip()
        password = request.form.get('password', '').strip()

        if not (username and first_name and last_name and state and street and house_number and password):
            return render_template('signup.html', error='Please fill in all fields.')
        if state == 'North Rhine-Westphalia' and not city:
            return render_template('signup.html', error='Please select a city for North Rhine-Westphalia.')
        if User.query.filter_by(username=username).first():
            return render_template('signup.html', error='Username already taken. Please choose another.')

        user = User(
            username=username,
            name=f'{first_name} {last_name}',
            first_name=first_name,
            last_name=last_name,
            state=state,
            city=city,
            street=street,
            house_number=house_number,
            password_hash=generate_password_hash(password),
            auth_method='password',
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
    return render_template('login.html', google_enabled=False, error='Google OAuth is not configured.')


@app.route('/login/manual', methods=['POST'])
def login_manual():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    user = User.query.filter_by(username=username, auth_method='password').first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session.pop('guest', None)
        return redirect(url_for('index'))
    return render_template(
        'login.html',
        google_enabled=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        error='Invalid username or password.',
        user=None, guest=None,
    )


@app.route('/auth')
def authorize():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return render_template('login.html', google_enabled=False, error='Google OAuth is not configured.')
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.get('userinfo').json()
    user = User.query.filter_by(email=user_info.get('email')).first()
    if not user:
        user = User(
            email=user_info.get('email'),
            name=user_info.get('name', 'Google User'),
            first_name=user_info.get('given_name', ''),
            last_name=user_info.get('family_name', ''),
            auth_method='google',
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


@app.route('/about', methods=['GET', 'POST'])
def about():
    sent = False
    error = None
    form = {}
    if request.method == 'POST':
        sender_name = request.form.get('sender_name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        form = {'sender_name': sender_name, 'email': email, 'subject': subject, 'message': message}
        if not sender_name or not email or not subject or not message:
            error = 'Please fill in all fields.'
        else:
            sent = True
            form = {}
    return render_template('about.html', sent=sent, error=error, form=form)


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
