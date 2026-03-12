"""
Tests unitaires pour les modèles
Vérifient les méthodes et propriétés des modèles
"""
import pytest
from models.user import User
from models import db


class TestUserModel:
    """Tests pour le modèle User"""
    
    def test_user_creation(self, app, db_session):
        """Test de création d'un utilisateur"""
        user = User(
            email='newuser@example.com',
            password='hashed_password',
            roles='user',
            first_name='John',
            last_name='Doe',
            pseudo='johndoe',
            subscription='free'
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == 'newuser@example.com'
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.pseudo == 'johndoe'
        assert user.subscription == 'free'
    
    def test_user_to_dict(self, sample_user):
        """Test de la méthode to_dict"""
        user_dict = sample_user.to_dict()
        
        assert 'id' in user_dict
        assert 'pseudo' in user_dict
        assert 'profile_picture' in user_dict
        assert 'first_name' in user_dict
        assert 'last_name' in user_dict
        assert 'subscription' in user_dict
        
        # Vérifier que certains champs sensibles ne sont pas exposés
        assert 'password' not in user_dict
        assert 'email' not in user_dict
    
    def test_user_repr(self, sample_user):
        """Test de la représentation string de l'utilisateur"""
        repr_str = repr(sample_user)
        assert 'User' in repr_str
        assert sample_user.first_name in repr_str
        assert sample_user.last_name in repr_str
    
    def test_subscription_level_property(self, sample_user):
        """Test de la propriété subscription_level"""
        assert sample_user.subscription_level == 'free'
    
    def test_is_free_property(self, sample_user):
        """Test de la propriété is_free"""
        assert sample_user.is_free is True
        assert sample_user.is_premium is False
        assert sample_user.is_plus_or_premium is False
    
    def test_is_premium_property(self, premium_user):
        """Test de la propriété is_premium avec un utilisateur premium"""
        assert premium_user.is_premium is True
        assert premium_user.is_free is False
        assert premium_user.is_plus_or_premium is True
    
    def test_is_plus_or_premium_with_plus(self, app, db_session):
        """Test de la propriété is_plus_or_premium avec un utilisateur plus"""
        user = User(
            email='plus@example.com',
            password='hashed_password',
            roles='user',
            first_name='Plus',
            last_name='User',
            pseudo='plususer',
            subscription='plus'
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.is_plus_or_premium is True
        assert user.is_premium is False
        assert user.is_free is False
    
    def test_update_subscription_to_premium(self, sample_user, app):
        """Test de mise à jour d'un abonnement vers premium"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            user.update_subscription('premium', commit=True)
            
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.subscription == 'premium'
            assert user.is_premium is True
    
    def test_update_subscription_to_plus(self, sample_user, app):
        """Test de mise à jour d'un abonnement vers plus"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            user.update_subscription('plus', commit=True)
            
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.subscription == 'plus'
            assert user.is_plus_or_premium is True
    
    def test_update_subscription_invalid_type(self, sample_user):
        """Test de mise à jour avec un type d'abonnement invalide"""
        with pytest.raises(ValueError) as exc_info:
            sample_user.update_subscription('invalid')
        assert "Type d'abonnement invalide" in str(exc_info.value)
    
    def test_update_subscription_without_commit(self, sample_user, app):
        """Test de mise à jour sans commit"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            original_subscription = user.subscription
            user.update_subscription('premium', commit=False)
            
            # L'abonnement devrait être modifié en mémoire
            assert user.subscription == 'premium'
            
            # Mais pas encore en base de données si on reload
            db.session.rollback()
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.subscription == original_subscription
    
    def test_user_default_values(self, app, db_session):
        """Test des valeurs par défaut lors de la création"""
        user = User(
            email='defaults@example.com',
            password='hashed_password',
            roles='user',
            first_name='Default',
            pseudo='defaultuser'
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.subscription == 'free'
        assert user.warn_count == 0
        assert user.is_banned is False
        assert user.ban_until is None
        assert user.private is False
    
    def test_user_warn_count(self, sample_user, app):
        """Test du compteur de warnings"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.warn_count == 0
            
            user.warn_count += 1
            db.session.commit()
            
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.warn_count == 1
    
    def test_user_ban_status(self, sample_user, app):
        """Test du statut de ban"""
        with app.app_context():
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.is_banned is False
            
            user.is_banned = True
            db.session.commit()
            
            user = db.session.query(User).filter_by(id=sample_user.id).first()
            assert user.is_banned is True
    
    def test_user_unique_email(self, app, db_session):
        """Test de l'unicité de l'email"""
        user1 = User(
            email='unique@example.com',
            password='password',
            roles='user',
            first_name='User1',
            pseudo='user1'
        )
        db_session.add(user1)
        db_session.commit()
        
        # Tentative de créer un utilisateur avec le même email
        user2 = User(
            email='unique@example.com',
            password='password',
            roles='user',
            first_name='User2',
            pseudo='user2'
        )
        db_session.add(user2)
        
        with pytest.raises(Exception):  # SQLAlchemy lèvera une exception d'intégrité
            db_session.commit()
