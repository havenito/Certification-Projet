"""
Tests unitaires pour les fonctions de validation
Ces tests vérifient les fonctions basiques sans dépendance à la base de données
"""
import pytest
from routes.auth import validate_pseudo, validate_password, validate_subscription_type


class TestValidatePseudo:
    """Tests pour la fonction validate_pseudo"""
    
    def test_valid_pseudo(self):
        """Test avec un pseudo valide"""
        result = validate_pseudo("testuser123")
        assert result is None
    
    def test_valid_pseudo_with_underscore(self):
        """Test avec un pseudo valide contenant un underscore"""
        result = validate_pseudo("test_user")
        assert result is None
    
    def test_valid_pseudo_with_dash(self):
        """Test avec un pseudo valide contenant un tiret"""
        result = validate_pseudo("test-user")
        assert result is None
    
    def test_valid_pseudo_with_dot(self):
        """Test avec un pseudo valide contenant un point"""
        result = validate_pseudo("test.user")
        assert result is None
    
    def test_empty_pseudo(self):
        """Test avec un pseudo vide"""
        result = validate_pseudo("")
        assert result == "Le pseudo est requis."
    
    def test_none_pseudo(self):
        """Test avec un pseudo None"""
        result = validate_pseudo(None)
        assert result == "Le pseudo est requis."
    
    def test_pseudo_too_short(self):
        """Test avec un pseudo trop court (moins de 3 caractères)"""
        result = validate_pseudo("ab")
        assert result == "Le pseudo doit contenir au moins 3 caractères."
    
    def test_pseudo_too_long(self):
        """Test avec un pseudo trop long (plus de 30 caractères)"""
        long_pseudo = "a" * 31
        result = validate_pseudo(long_pseudo)
        assert result == "Le pseudo ne peut pas dépasser 30 caractères."
    
    def test_pseudo_with_special_chars(self):
        """Test avec des caractères spéciaux non autorisés"""
        result = validate_pseudo("test@user")
        assert "ne peut contenir que" in result
    
    def test_pseudo_with_space(self):
        """Test avec un espace"""
        result = validate_pseudo("test user")
        assert "ne peut contenir que" in result
    
    def test_pseudo_starts_with_dot(self):
        """Test avec un pseudo commençant par un point"""
        result = validate_pseudo(".testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_ends_with_dot(self):
        """Test avec un pseudo finissant par un point"""
        result = validate_pseudo("testuser.")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_starts_with_dash(self):
        """Test avec un pseudo commençant par un tiret"""
        result = validate_pseudo("-testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_starts_with_underscore(self):
        """Test avec un pseudo commençant par un underscore"""
        result = validate_pseudo("_testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_reserved_pseudo_login(self):
        """Test avec un pseudo réservé (login)"""
        result = validate_pseudo("login")
        assert "réservé" in result.lower()
    
    def test_reserved_pseudo_admin(self):
        """Test avec un pseudo réservé (admin)"""
        result = validate_pseudo("admin")
        assert "réservé" in result.lower()
    
    def test_reserved_pseudo_case_insensitive(self):
        """Test que les pseudos réservés sont vérifiés sans tenir compte de la casse"""
        result = validate_pseudo("LOGIN")
        assert "réservé" in result.lower()
    
    def test_pseudo_exact_min_length(self):
        """Test avec un pseudo de longueur minimale exacte (3 caractères)"""
        result = validate_pseudo("abc")
        assert result is None
    
    def test_pseudo_exact_max_length(self):
        """Test avec un pseudo de longueur maximale exacte (30 caractères)"""
        pseudo = "a" * 30
        result = validate_pseudo(pseudo)
        assert result is None


class TestValidatePassword:
    """Tests pour la fonction validate_password"""
    
    def test_valid_password(self):
        """Test avec un mot de passe valide"""
        result = validate_password("Test@1234")
        assert result is None
    
    def test_valid_complex_password(self):
        """Test avec un mot de passe complexe valide"""
        result = validate_password("MyP@ssw0rd!2024")
        assert result is None
    
    def test_password_too_short(self):
        """Test avec un mot de passe trop court"""
        result = validate_password("Test@12")
        assert result == "Le mot de passe doit contenir au moins 8 caractères."
    
    def test_password_no_uppercase(self):
        """Test avec un mot de passe sans majuscule"""
        result = validate_password("test@1234")
        assert result == "Le mot de passe doit contenir au moins une lettre majuscule."
    
    def test_password_no_lowercase(self):
        """Test avec un mot de passe sans minuscule"""
        result = validate_password("TEST@1234")
        assert result == "Le mot de passe doit contenir au moins une lettre minuscule."
    
    def test_password_no_digit(self):
        """Test avec un mot de passe sans chiffre"""
        result = validate_password("Test@abcd")
        assert result == "Le mot de passe doit contenir au moins un chiffre."
    
    def test_password_no_special_char(self):
        """Test avec un mot de passe sans caractère spécial"""
        result = validate_password("Test1234")
        assert result == "Le mot de passe doit contenir au moins un caractère spécial."
    
    def test_password_exact_min_length(self):
        """Test avec un mot de passe de longueur minimale exacte"""
        result = validate_password("Test@123")
        assert result is None
    
    def test_password_with_all_special_chars(self):
        """Test avec différents caractères spéciaux"""
        special_chars = "!@#$%^&*(),.?\":{}|<>_-"
        for char in special_chars:
            password = f"Test123{char}"
            result = validate_password(password)
            assert result is None, f"Échec avec le caractère spécial: {char}"


class TestValidateSubscriptionType:
    """Tests pour la fonction validate_subscription_type"""
    
    def test_valid_free_subscription(self):
        """Test avec un abonnement free valide"""
        result = validate_subscription_type("free")
        assert result == "free"
    
    def test_valid_plus_subscription(self):
        """Test avec un abonnement plus valide"""
        result = validate_subscription_type("plus")
        assert result == "plus"
    
    def test_valid_premium_subscription(self):
        """Test avec un abonnement premium valide"""
        result = validate_subscription_type("premium")
        assert result == "premium"
    
    def test_invalid_subscription_type(self):
        """Test avec un type d'abonnement invalide"""
        with pytest.raises(ValueError) as exc_info:
            validate_subscription_type("invalid")
        assert "Type d'abonnement invalide" in str(exc_info.value)
    
    def test_invalid_subscription_empty(self):
        """Test avec un type d'abonnement vide"""
        with pytest.raises(ValueError) as exc_info:
            validate_subscription_type("")
        assert "Type d'abonnement invalide" in str(exc_info.value)
    
    def test_invalid_subscription_case_sensitive(self):
        """Test que la validation est sensible à la casse"""
        with pytest.raises(ValueError):
            validate_subscription_type("FREE")
        with pytest.raises(ValueError):
            validate_subscription_type("Premium")
