"""
Tests unitaires pour les fonctions de validation
Ces tests vérifient les fonctions basiques sans dépendance à la base de données
"""
import pytest
from routes.auth import validate_pseudo, validate_password, validate_subscription_type


class TestValidatePseudo:
    """
    Cette suite de tests vérifie les règles de sécurité et de validation appliquées aux pseudos 
    lors de l'inscription. L'objectif est d'isoler la fonction 'validate_pseudo' pour s'assurer 
    qu'aucun pseudo incorrect, dangereux ou usurpé ne puisse être validé dans Minouverse.
    """
    
    def test_valid_pseudo(self):
        """Cas nominal : Un pseudo standard (lettres/chiffres) doit passer sans erreur (None)"""
        result = validate_pseudo("testuser123")
        assert result is None
    
    def test_valid_pseudo_with_underscore(self):
        """Vérifie que l'underscore (_) est bien accepté au milieu du pseudo"""
        result = validate_pseudo("test_user")
        assert result is None
    
    def test_valid_pseudo_with_dash(self):
        """Vérifie que le tiret (-) est bien accepté au milieu du pseudo"""
        result = validate_pseudo("test-user")
        assert result is None
    
    def test_valid_pseudo_with_dot(self):
        """Vérifie que le point (.) est bien accepté au milieu du pseudo"""
        result = validate_pseudo("test.user")
        assert result is None
    
    def test_empty_pseudo(self):
        """Vérifie la sécurité 'Champ obligatoire' : un pseudo vide doit renvoyer une erreur"""
        result = validate_pseudo("")
        assert result == "Le pseudo est requis."
    
    def test_none_pseudo(self):
        """Sécurité anti-crash : si le front-end envoie une valeur null (None), on renvoie une erreur propre"""
        result = validate_pseudo(None)
        assert result == "Le pseudo est requis."
    
    def test_pseudo_too_short(self):
        """Vérifie la limite basse : un pseudo de moins de 3 caractères doit être refusé"""
        result = validate_pseudo("ab")
        assert result == "Le pseudo doit contenir au moins 3 caractères."
    
    def test_pseudo_too_long(self):
        """Vérifie la limite haute : évite l'injection de textes trop longs en BDD (max 30 caractères)"""
        long_pseudo = "a" * 31
        result = validate_pseudo(long_pseudo)
        assert result == "Le pseudo ne peut pas dépasser 30 caractères."
    
    def test_pseudo_with_special_chars(self):
        """Sécurité injection/Clean code : bloque les caractères interdits comme l'arobase (@)"""
        result = validate_pseudo("test@user")
        assert "ne peut contenir que" in result
    
    def test_pseudo_with_space(self):
        """UX/Routage : bloque les espaces qui casseraient la structure des URLs (ex: minouverse.com/mon pseudo)"""
        result = validate_pseudo("test user")
        assert "ne peut contenir que" in result
    
    def test_pseudo_starts_with_dot(self):
        """Règle esthétique/technique : interdit de commencer par un point pour éviter des bugs d'affichage"""
        result = validate_pseudo(".testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_ends_with_dot(self):
        """Règle esthétique/technique : interdit de terminer par un point"""
        result = validate_pseudo("testuser.")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_starts_with_dash(self):
        """Règle technique : interdit de commencer par un tiret"""
        result = validate_pseudo("-testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_pseudo_starts_with_underscore(self):
        """Règle technique : interdit de commencer par un underscore"""
        result = validate_pseudo("_testuser")
        assert "ne peut pas commencer ou finir" in result
    
    def test_reserved_pseudo_login(self):
        """SÉCURITÉ CRITIQUE : Interdit d'utiliser 'login' comme pseudo pour ne pas casser les routes de l'application"""
        result = validate_pseudo("login")
        assert "réservé" in result.lower()
    
    def test_reserved_pseudo_admin(self):
        """ANTI-USURPATION : Empêche un membre lambda de s'appeler 'admin' et de tromper les autres utilisateurs"""
        result = validate_pseudo("admin")
        assert "réservé" in result.lower()
    
    def test_reserved_pseudo_case_insensitive(self):
        """SÉCURITÉ DOUBLE : On s'assure que bloquer 'login' bloque AUSSI 'LOGIN' ou 'LogIn' (sensibilité à la casse)"""
        result = validate_pseudo("LOGIN")
        assert "réservé" in result.lower()
    
    def test_pseudo_exact_min_length(self):
        """Test aux limites : On vérifie que la valeur limite exacte de 3 caractères fonctionne parfaitement"""
        result = validate_pseudo("abc")
        assert result is None
    
    def test_pseudo_exact_max_length(self):
        """Test aux limites : On vérifie que la valeur limite exacte de 30 caractères fonctionne parfaitement"""
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
