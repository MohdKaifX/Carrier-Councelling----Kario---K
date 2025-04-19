from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS, cross_origin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
import os
from datetime import timezone
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Flask App setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")

# DB Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SESSION_COOKIE_NAME'] = 'careerhub_session'
db = SQLAlchemy(app)

# Enable CORS
CORS(app, supports_credentials=True)

# === MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text)

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# === TOKEN CHECK DECORATOR ===
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            current_user = db.session.get(User, data['user_id'])
            if not current_user:
                raise Exception("User not found")
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# === AUTH ROUTES ===
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    if not full_name or not email or not password:
        return jsonify({'message': 'Missing fields'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'User already exists'}), 400
    hashed_pw = generate_password_hash(password)
    new_user = User(full_name=full_name, email=email, password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid email or password'}), 401
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }, app.secret_key, algorithm="HS256")
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'email': user.email,
            'full_name': user.full_name
        }
    }), 200

@app.route('/api/auth/dashboard', methods=['GET'])
@token_required
def dashboard(current_user):
    return jsonify({'user': {
        'email': current_user.email,
        'full_name': current_user.full_name,
        'created_at': current_user.created_at.strftime('%Y-%m-%d')
    }}), 200

# === GPT-POWERED QUIZ ===
@app.route('/api/chat-quiz', methods=['POST'])
@token_required
def chat_quiz(current_user):
    data = request.get_json()
    user_prompt = data.get('prompt')
    history = data.get('history', [])
    if not user_prompt:
        return jsonify({'message': 'Prompt is required'}), 400
    try:
        messages = [{"role": "system", "content": "You are a professional career counselor helping users discover their ideal career path."}]
        messages += history
        messages.append({"role": "user", "content": user_prompt})
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        reply = response['choices'][0]['message']['content']
    except Exception as e:
        print("🔥 ChatGPT error (using fallback):", str(e))
        reply = """
        Thank you for completing the quiz! Based on your responses, you might thrive in:
        1. Software Development – if you enjoy logic and building things.
        2. UX/UI Design – if you're creative and user-focused.
        3. Data Analytics – if you love patterns and insights.

        Ask me for roadmaps or advice on any of these!
        """
    quiz_result = QuizResult(user_id=current_user.id, prompt=user_prompt, response=reply)
    db.session.add(quiz_result)
    db.session.commit()
    return jsonify({'reply': reply}), 200


@app.route('/api/quiz/results', methods=['GET'])
@token_required
def quiz_results(current_user):
    results = QuizResult.query.filter_by(user_id=current_user.id).order_by(QuizResult.timestamp.desc()).all()
    data = [{
        'prompt': r.prompt,
        'response': r.response,
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for r in results]
    return jsonify({'results': data}), 200

# === CONTACT FORM ===
@app.route('/api/contact', methods=['POST'])
def contact():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    try:
        jwt.decode(token, app.secret_key, algorithms=["HS256"])
    except Exception:
        return jsonify({'message': 'Invalid or expired token'}), 401
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    message = data.get('message')
    if not name or not email or not message:
        return jsonify({'message': 'Please fill in all required fields.'}), 400
    new_message = ContactMessage(name=name, email=email, phone=phone, message=message)
    db.session.add(new_message)
    db.session.commit()
    return jsonify({'message': 'Message received. We will get back to you soon!'}), 200

# === STATIC PAGE ROUTES ===
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/quiz')
def quiz_page():
    return render_template('quiz.html')

@app.route('/explore')
def explore_page():
    return render_template('explore.html')

# Career field and detail routes (update as needed)
@app.route('/technology')
def technology(): return render_template('technology.html')

@app.route('/technology-career')
def technology_career(): return render_template('technology-career.html')

# === INIT DB AND RUN ===
@app.route('/business')
def business():
    return render_template('business.html')

@app.route('/business-career')
def business_career():
    return render_template('business-career.html')

@app.route('/engineering')
def engineering():
    return render_template('engineering.html')

@app.route('/engineering-career')
def engineering_career():
    return render_template('engineering-career.html')

@app.route('/finance')
def finance():
    return render_template('finance.html')

@app.route('/finance-career')
def finance_career():
    return render_template('finance-career.html')

@app.route('/healthcare')
def healthcare():
    return render_template('healthcare.html')

@app.route('/healthcare-career')
def healthcare_career():
    return render_template('healthcare-career.html')

@app.route('/law')
def law():
    return render_template('law.html')

@app.route('/law-career')
def law_career():
    return render_template('law-career.html')

@app.route('/media')
def media():
    return render_template('media.html')

@app.route('/media-career')
def media_career():
    return render_template('media-career.html')

@app.route('/education')
def education():
    return render_template('education.html')

@app.route('/education-career')
def education_career():
    return render_template('education-career.html')

@app.route('/arts')
def arts():
    return render_template('arts.html')

@app.route('/arts-career')
def arts_career():
    return render_template('arts-career.html')

@app.route('/science')
def science():
    return render_template('science.html')

@app.route('/science-career')
def science_career():
    return render_template('science-career.html')

@app.route('/hospitality')
def hospitality():
    return render_template('hospitality.html')

@app.route('/hospitality-career')
def hospitality_career():
    return render_template('hospitality-career.html')

@app.route('/public-services')
def public_services():
    return render_template('public-services.html')

@app.route('/public-services-career')
def public_services_career():
    return render_template('public-services-career.html')

@app.route('/culture')
def culture():
    return render_template('culture.html')

@app.route('/culture-career')
def culture_career():
    return render_template('culture-career.html')

@app.route('/environment')
def environment():
    return render_template('environment.html')

@app.route('/environment-career')
def environment_career():
    return render_template('environment-career.html')

@app.route('/sports')
def sports():
    return render_template('sports.html')

@app.route('/sports-career')
def sports_career():
    return render_template('sports-career.html')

@app.route('/agriculture')
def agriculture():
    return render_template('agriculture.html')

@app.route('/agriculture-career')
def agriculture_career():
    return render_template('agriculture-career.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/profile')
def profile_page():
    return render_template('profile.html')


# === MAIN ===
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)