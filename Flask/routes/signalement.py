from flask import Blueprint, request, jsonify
from models.signalement import Signalement
from models.user import User
from models import db

bp_signalement = Blueprint('signalement', __name__)


# ============================================================
# Route : création d'un signalement (post, commentaire ou utilisateur)
# ============================================================
@bp_signalement.route('/api/signalement', methods=['POST'])
def create_signalement():
    data = request.json
    user_id = data.get('user_id')
    post_id = data.get('post_id')
    reported_user_id = data.get('reported_user_id')
    comment_id = data.get('comment_id')
    report_type = data.get('report_type')
    content = data.get('content')

    # Validation obligatoire : on bloque si on n'a pas l'auteur, le motif ou l'explication
    if not user_id or not content or not report_type:
        return jsonify({'error': 'Missing fields'}), 400

    # Passage en minuscules pour éviter les conflits avec le type ENUM configuré dans PostgreSQL
    report_type = report_type.lower() if report_type else None

    # Note : post_id, reported_user_id et comment_id sont tous optionnels ici — un signalement
    # peut donc théoriquement être créé sans cibler explicitement un post, un commentaire
    # ou un utilisateur précis (aucune vérification de cohérence n'est faite entre eux)
    signalement = Signalement(
        user_id=user_id,
        post_id=post_id,
        reported_user_id=reported_user_id,
        comment_id=comment_id,
        report_type=report_type,
        content=content
    )

    db.session.add(signalement)
    db.session.commit()
    return jsonify({'message': 'Signalement envoyé'}), 201


# ============================================================
# Route : mise à jour du statut d'un signalement par un modérateur
# (ex: passer de "en attente" à "traité" ou "rejeté")
# ============================================================
@bp_signalement.route('/api/signalement/<int:report_id>/status', methods=['PUT'])
def update_signalement_status(report_id):
    """ Permet aux modérateurs de changer l'état d'un signalement (ex: traité, rejeté) """
    data = request.get_json()
    statut = data.get('statut')

    signalement = Signalement.query.get(report_id)
    if not signalement:
        return jsonify({'error': 'Signalement non trouvé'}), 404

    signalement.statut = statut
    db.session.commit()
    return jsonify({'message': 'Statut mis à jour'})


# ============================================================
# Route : liste complète des signalements, destinée au panel de modération
# ============================================================
@bp_signalement.route('/api/signalement', methods=['GET'])
def get_signalements():
    """ Récupère la liste complète des signalements pour le panel de modération """
    signalements = Signalement.query.all()
    result = []

    for s in signalements:
        # On va chercher les profils complets pour afficher les pseudos plutôt que de bêtes IDs
        # Une requête User.query.get() par signalement, x2 (reporter + reported_user) :
        # pattern N+1, à optimiser avec un JOIN si le volume de signalements grossit
        reported_user = User.query.get(s.reported_user_id)
        reporter = User.query.get(s.user_id)

        # Construction d'un dictionnaire propre contenant le signalement et le passif du coupable
        result.append({
            'id': s.id,
            'reported_user_id': s.reported_user_id,
            'reported_user_pseudo': getattr(reported_user, 'pseudo', None),
            'reporter_id': s.user_id,
            'reporter_pseudo': getattr(reporter, 'pseudo', None),
            'post_id': s.post_id,
            'report_type': s.report_type,
            'content': s.content,
            'statut': s.statut,
            'date_signalement': s.date_signalement.strftime('%Y-%m-%d %H:%M:%S') if hasattr(s, 'date_signalement') else '',
            # Ces deux champs permettent aux modérateurs de voir l'historique de l'utilisateur visé d'un coup d'œil
            'reported_user_warns': getattr(reported_user, 'warn_count', 0) if reported_user else 0,
            'reported_user_is_banned': getattr(reported_user, 'is_banned', False) if reported_user else False,
        })

    return jsonify(result)


# ============================================================
# Route : alias de get_signalements, sur l'URL au pluriel
# Évite une erreur 404 si le frontend appelle par erreur '/api/signalements'
# (avec un 's') plutôt que '/api/signalement'. Réutilise directement la
# fonction de la route principale plutôt que de dupliquer la logique.
# ============================================================
@bp_signalement.route('/api/signalements', methods=['GET'])
def get_signalements_alias():
    """ Simple alias d'URL pour éviter les erreurs si le front appelle l'API avec un 's' """
    return get_signalements()