"""
Tests d'intégration pour les routes d'authentification
Ces tests vérifient les endpoints API avec une base de données fictive
"""
import json
from models.user import User
from models import db
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


class TestAuthRegistration:
    """Tests pour l'inscription d'utilisateurs"""
    
    def test_register_user_success(self, client, app):
        """Test d'inscription réussie avec des données valides"""
        response = client.post('/api/users', 
            json={
                'email': 'newuser@example.com',
                'password': 'Test@1234',
                'first_name': 'New',
                'last_name': 'User',
                'pseudo': 'newuser',
                'private': False
            })
        
        data = json.loads(response.data)
        assert response.status_code == 201
        assert 'message' in data
        
        # Vérifier que l'utilisateur existe en base de données
        with app.app_context():
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
    
    def test_register_user_missing_email(self, client):
        """Test d'inscription sans email"""
        response = client.post('/api/users',
            json={
                'password': 'Test@1234',
                'first_name': 'Test',
                'pseudo': 'testuser'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 400
        assert 'error' in data
    
    def test_register_user_invalid_password(self, client):
        """Test d'inscription avec un mot de passe invalide"""
        response = client.post('/api/users',
            json={
                'email': 'test@example.com',
                'password': 'weak',
                'first_name': 'Test',
                'pseudo': 'testuser'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 400
        assert 'error' in data
    
    def test_register_duplicate_email(self, client, sample_user):
        """Test d'inscription avec un email déjà utilisé"""
        response = client.post('/api/users',
            json={
                'email': 'test@example.com',
                'password': 'Test@1234',
                'first_name': 'Another',
                'pseudo': 'anotheruser'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 400
        assert 'error' in data


class TestAuthLogin:
    """Tests pour la connexion d'utilisateurs"""
    
    def test_login_success(self, client, sample_user):
        """Test de connexion réussie"""
        response = client.post('/api/login',
            json={
                'email': 'test@example.com',
                'password': 'Test@1234'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 200
        assert 'user' in data
        # Le token peut être dans 'access_token' ou 'token' selon l'implémentation
        assert ('access_token' in data or 'token' in data or 'message' in data)
    
    def test_login_invalid_email(self, client):
        """Test de connexion avec un email inexistant"""
        response = client.post('/api/login',
            json={
                'email': 'nonexistent@example.com',
                'password': 'Test@1234'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 401
        assert 'error' in data
    
    def test_login_wrong_password(self, client, sample_user):
        """Test de connexion avec un mauvais mot de passe"""
        response = client.post('/api/login',
            json={
                'email': 'test@example.com',
                'password': 'WrongPassword@123'
            })
        
        data = json.loads(response.data)
        assert response.status_code == 401
        assert 'error' in data


class TestAuthDatabaseIntegration:
    """Tests d'intégration pour les opérations sur la base de données"""
    
    def test_user_persistence(self, client, app):
        """Test de la persistance des utilisateurs en base de données"""
        # Créer un utilisateur
        response = client.post('/api/users',
            json={
                'email': 'persist@example.com',
                'password': 'Test@1234',
                'first_name': 'Persist',
                'pseudo': 'persistuser'
            })
        
        assert response.status_code == 201
        
        # Vérifier que l'utilisateur existe en base
        with app.app_context():
            user = User.query.filter_by(email='persist@example.com').first()
            assert user is not None
            assert user.email == 'persist@example.com'
            assert user.first_name == 'Persist'
            assert user.pseudo == 'persistuser'
            
            # Vérifier que le mot de passe est hashé
            assert user.password != 'Test@1234'
            assert bcrypt.check_password_hash(user.password, 'Test@1234')
    
    def test_query_user_by_email(self, app, sample_user):
        """Test de requête SQL pour trouver un utilisateur par email"""
        with app.app_context():
            user = db.session.query(User).filter_by(email='test@example.com').first()
            assert user is not None
            assert user.id == sample_user.id
            assert user.pseudo == sample_user.pseudo
    
    def test_query_user_by_pseudo(self, app, sample_user):
        """Test de requête SQL pour trouver un utilisateur par pseudo"""
        with app.app_context():
            user = db.session.query(User).filter_by(pseudo='testuser').first()
            assert user is not None
            assert user.id == sample_user.id
            assert user.email == sample_user.email
    
    def test_query_all_users(self, app, sample_user, premium_user):
        """Test de requête SQL pour récupérer tous les utilisateurs"""
        with app.app_context():
            users = db.session.query(User).all()
            assert len(users) >= 2
            
            emails = [u.email for u in users]
            assert 'test@example.com' in emails
            assert 'premium@example.com' in emails
    
    def test_query_users_by_subscription(self, app, sample_user, premium_user):
        """Test de requête SQL pour filtrer les utilisateurs par abonnement"""
        with app.app_context():
            free_users = db.session.query(User).filter_by(subscription='free').all()
            premium_users = db.session.query(User).filter_by(subscription='premium').all()
            
            assert len(free_users) >= 1
            assert len(premium_users) >= 1
    
    def test_update_user_in_database(self, app, sample_user):
        """Test de mise à jour d'un utilisateur en base de données"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            user.first_name = 'Updated'
            db.session.commit()
            
            # Recharger depuis la base
            updated_user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert updated_user.first_name == 'Updated'