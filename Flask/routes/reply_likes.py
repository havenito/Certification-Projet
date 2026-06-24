from flask import Blueprint, request, jsonify
from models import db
from models.reply_like import ReplyLike
from models.reply import Reply
from models.user import User

reply_likes_bp = Blueprint('reply_likes', __name__)


# ============================================================
# Route : like / unlike d'une réponse (toggle)
# Si l'utilisateur a déjà liké -> on retire le like
# Sinon -> on ajoute le like
# ============================================================
@reply_likes_bp.route('/api/replies/<int:reply_id>/like', methods=['POST'])
def toggle_reply_like(reply_id):
    """ Système de switch : on ajoute le like si absents, ou on le retire s'il existe déjà """
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'user_id requis'}), 400

        reply = Reply.query.get(reply_id)
        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # On vérifie si l'utilisateur a déjà mis un like sur cette réponse spécifique
        existing_like = ReplyLike.query.filter_by(user_id=user_id, replies_id=reply_id).first()

        if existing_like:
            # Cas 1 : Le like existe, donc l'utilisateur reclique pour l'enlever (Unlike)
            db.session.delete(existing_like)
            db.session.commit()

            # On recalcule le total après la suppression pour renvoyer le compteur à jour au front
            likes_count = ReplyLike.query.filter_by(replies_id=reply_id).count()

            return jsonify({
                'message': 'Like retiré',
                'liked': False,
                'likes_count': likes_count
            }), 200
        else:
            # Cas 2 : Pas de like trouvé, on crée une nouvelle entrée en base (Like)
            new_like = ReplyLike(user_id=user_id, replies_id=reply_id)
            db.session.add(new_like)
            db.session.commit()

            likes_count = ReplyLike.query.filter_by(replies_id=reply_id).count()

            return jsonify({
                'message': 'Réponse likée',
                'liked': True,
                'likes_count': likes_count
            }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : liste des likes d'une réponse, avec les infos des utilisateurs concernés
# ============================================================
@reply_likes_bp.route('/api/replies/<int:reply_id>/likes', methods=['GET'])
def get_reply_likes(reply_id):
    """ Récupère le compteur de likes et la liste des profils des utilisateurs qui ont liké """
    try:
        reply = Reply.query.get(reply_id)
        if not reply:
            return jsonify({'error': 'Réponse non trouvée'}), 404

        likes = ReplyLike.query.filter_by(replies_id=reply_id).all()
        likes_count = len(likes)

        # On extrait les infos de profil minimales pour l'affichage de la pop-up des likes sur le front
        # Une requête User.query.get() par like (pattern N+1) : pourrait être optimisé
        # avec un seul JOIN si le nombre de likes devient important
        users_who_liked = []
        for like in likes:
            user = User.query.get(like.user_id)
            if user:
                users_who_liked.append({
                    'id': user.id,
                    'pseudo': user.pseudo,
                    'profile_picture': user.profile_picture
                })

        return jsonify({
            'reply_id': reply_id,
            'likes_count': likes_count,
            'users': users_who_liked
        }), 200

    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : vérifie si un utilisateur donné a liké une réponse donnée
# (utile côté frontend pour afficher l'état initial du bouton like)
# ============================================================
@reply_likes_bp.route('/api/users/<int:user_id>/replies/<int:reply_id>/like-status', methods=['GET'])
def check_reply_like_status(user_id, reply_id):
    """ Petit endpoint utilitaire pour que le front sache si le bouton doit être allumé ou éteint au chargement """
    try:
        like = ReplyLike.query.filter_by(user_id=user_id, replies_id=reply_id).first()
        return jsonify({
            'liked': like is not None  # Renvoie True si une ligne existe, sinon False
        }), 200
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500