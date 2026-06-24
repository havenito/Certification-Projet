from flask import Blueprint, jsonify
from models import db
from models.user import User
from datetime import datetime, timedelta
from flask import request

warn_bp = Blueprint('warn_bp', __name__)


# ============================================================
# Route : ajoute un avertissement à un utilisateur, avec bannissement
# automatique au 3e avertissement
#
# Aucune vérification d'autorisation ici (pas de contrôle que l'appelant
# est bien un modérateur/admin) : n'importe qui connaissant l'URL et l'ID
# d'un utilisateur pourrait lui ajouter un avertissement, voire le faire
# bannir automatiquement en appelant cette route 3 fois. À sécuriser via
# une vérification de rôle (ex: décorateur @admin_required).
# ============================================================
@warn_bp.route('/api/warn/<int:user_id>', methods=['POST'])
def warn_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    # On incrémente le compteur de avertissements (sécurité si le champ est None de base)
    user.warn_count = (user.warn_count or 0) + 1

    # Seuil critique : si le mec atteint 3 avertissements, le système le bascule en banni direct
    # Note : ce bannissement automatique est permanent (is_banned=True, ban_until non défini
    # donc reste à sa valeur précédente — généralement None = ban à vie), contrairement à
    # ban_user qui permet de choisir une durée
    if user.warn_count >= 3:
        user.is_banned = True

    db.session.commit()
    return jsonify({
        'message': 'Warn ajouté',
        'warn_count': user.warn_count,
        'is_banned': user.is_banned
    })


# ============================================================
# Route : bannir un utilisateur, temporairement ou définitivement
#
# Même remarque que warn_user : aucune vérification d'autorisation,
# n'importe qui peut bannir n'importe quel utilisateur via cette route.
# ============================================================
@warn_bp.route('/api/ban/<int:user_id>', methods=['POST'])
def ban_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    data = request.get_json() or {}
    duration = data.get('duration', 0)  # La durée arrive du front en jours (0 correspond à un ban permanent)

    user.is_banned = True

    # Si on a reçu une durée supérieure à zéro, on calcule la date de fin, sinon c'est définitif
    if duration and int(duration) > 0:
        user.ban_until = datetime.utcnow() + timedelta(days=int(duration))
    else:
        user.ban_until = None  # None en BDD signifie ban à vie

    db.session.commit()
    return jsonify({'message': 'Utilisateur banni'})


# ============================================================
# Route : débannir un utilisateur (lève le ban temporaire ou permanent)
# Ne réinitialise pas warn_count : un utilisateur débanni après avoir atteint
# 3 avertissements gardera ces 3 avertissements en mémoire. S'il en reçoit un seul
# de plus après son retour, il repassera automatiquement banni (via warn_user,
# puisque warn_count sera déjà à 3 et l'incrémentation le passera à 4, donc >= 3).
# À vérifier si c'est le comportement voulu, ou si un débannissement devrait aussi
# remettre warn_count à 0 pour donner un vrai nouveau départ.
# ============================================================
@warn_bp.route('/api/unban/<int:user_id>', methods=['POST'])
def unban_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    # Reset complet des flags de bannissement pour réactiver le compte
    user.is_banned = False
    user.ban_until = None

    db.session.commit()
    return jsonify({'message': 'Utilisateur débanni'})