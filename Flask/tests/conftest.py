"""
Configuration pytest pour les tests
Contient les fixtures utilisées dans tous les tests
"""
import pytest
from app import create_app
from models import db
from models.user import User
from models.category import Category
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


class TestConfig:
    """Configuration spécifique pour les tests"""
    TESTING = True
    # Utiliser SQLite en mémoire pour les tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret-key'
    
    # Configuration Cloudinary pour tests (mock)
    CLOUDINARY_CLOUD_NAME = 'test_cloud'
    CLOUDINARY_API_KEY = 'test_key'
    CLOUDINARY_API_SECRET = 'test_secret'
    
    # Configuration email pour tests
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 25
    MAIL_USE_TLS = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    MAIL_DEFAULT_SENDER = 'test@example.com'
    
    FRONTEND_URL = 'http://localhost:3000'
    
    # Stripe pour tests
    STRIPE_SECRET_KEY = 'test_stripe_key'
    STRIPE_WEBHOOK_SECRET = 'test_webhook_secret'


@pytest.fixture(scope='function')
def app():
    """Créer une instance de l'application Flask pour les tests"""
    # create_app retourne (app, socketio), on ne garde que l'app
    flask_app, _ = create_app(TestConfig)
    
    with flask_app.app_context():
        db.create_all()
        
        # Créer une catégorie par défaut pour les tests
        default_category = Category(name='Test Category')
        db.session.add(default_category)
        db.session.commit()
        
        yield flask_app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Créer un client de test pour effectuer les requêtes"""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Créer un runner pour les commandes CLI"""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """Retourne la session de base de données pour les tests"""
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_user(app):
    """Créer un utilisateur de test"""
    with app.app_context():
        user = User(
            email='test@example.com',
            password=bcrypt.generate_password_hash('Test@1234').decode('utf-8'),
            roles='user',
            first_name='Test',
            last_name='User',
            pseudo='testuser',
            subscription='free'
        )
        db.session.add(user)
        db.session.commit()
        
        # Recharger l'utilisateur pour avoir l'ID
        user = db.session.query(User).filter_by(email='test@example.com').first()
        return user


@pytest.fixture
def premium_user(app):
    """Créer un utilisateur premium de test"""
    with app.app_context():
        user = User(
            email='premium@example.com',
            password=bcrypt.generate_password_hash('Premium@1234').decode('utf-8'),
            roles='user',
            first_name='Premium',
            last_name='User',
            pseudo='premiumuser',
            subscription='premium'
        )
        db.session.add(user)
        db.session.commit()
        
        user = db.session.query(User).filter_by(email='premium@example.com').first()
        return user


@pytest.fixture
def auth_headers(client, sample_user):
    """Génère les headers d'authentification pour un utilisateur"""
    from flask_jwt_extended import create_access_token
    
    with client.application.app_context():
        access_token = create_access_token(identity=sample_user.id)
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }


@pytest.fixture
def admin_user(app):
    """Créer un utilisateur admin de test"""
    with app.app_context():
        user = User(
            email='admin@example.com',
            password=bcrypt.generate_password_hash('Admin@1234').decode('utf-8'),
            roles='admin',
            first_name='Admin',
            last_name='User',
            pseudo='adminuser',
            subscription='free'
        )
        db.session.add(user)
        db.session.commit()
        
        user = db.session.query(User).filter_by(email='admin@example.com').first()
        return user
