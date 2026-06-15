from flask import Blueprint, request, jsonify
from models.signalement import Signalement
from models.user import User
from models import db

bp_signalement = Blueprint('signalement', __name__)

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

@bp_signalement.route('/api/signalement', methods=['GET'])
def get_signalements():
    """ Récupère la liste complète des signalements pour le panel de modération """
    signalements = Signalement.query.all()
    result = []
    
    for s in signalements:
        # On va chercher les profils complets pour afficher les pseudos plutôt que de bêtes IDs
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

@bp_signalement.route('/api/signalements', methods=['GET'])
def get_signalements_alias():
    """ Simple alias d'URL pour éviter les erreurs si le front appelle l'API avec un 's' """
    return get_signalements()