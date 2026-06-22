from flask import Blueprint, request, jsonify
from models import db
from models.post import Post
from models.user import User
from models.notification import Notification
from models.comment import Comment
from models.reply import Reply
from models.comment_media import CommentMedia
from models.reply_media import ReplyMedia
from models.comment_like import CommentLike
from models.reply_like import ReplyLike
from services.file_upload import upload_file, determine_media_type

comments_api = Blueprint('comments_api', __name__)


# ============================================================
# Route : création d'un commentaire sur un post
# Accepte soit du JSON (sans médias), soit du multipart/form-data
# (avec un fichier unique 'file' et/ou plusieurs fichiers 'files[]')
# ============================================================
@comments_api.route('/api/comments', methods=['POST'])
def create_comment():
    try:
        if request.is_json:
            # Cas JSON : pas de médias possibles
            data = request.get_json()
            content = data.get('content')
            post_id = data.get('post_id')
            user_id = data.get('user_id')
            media_files = []
        else:
            # Cas multipart : récupération des champs texte + fichiers
            content = request.form.get('content')
            post_id = request.form.get('post_id')
            user_id = request.form.get('user_id')

            media_files = []
            # Support d'un fichier unique envoyé sous la clé 'file'
            if 'file' in request.files:
                file = request.files['file']
                if file.filename:
                    media_files.append(file)

            # Support de plusieurs fichiers envoyés sous la clé 'files[]'
            if 'files[]' in request.files:
                files = request.files.getlist('files[]')
                for file in files:
                    if file.filename:
                        media_files.append(file)

        if not content:
            return jsonify({'error': 'Content is required'}), 400

        # On crée d'abord le commentaire (sans médias) pour obtenir son ID,
        # nécessaire pour lier les éventuels médias ensuite
        new_comment = Comment(content=content, post_id=post_id, user_id=user_id)
        db.session.add(new_comment)
        db.session.commit()

        # Upload de chaque fichier média et création de l'enregistrement CommentMedia associé
        for file in media_files:
            url, file_type = upload_file(file)

            if not url:
                continue  # Upload échoué -> on ignore ce fichier et on continue les autres

            media_type = determine_media_type(file_type)
            if not media_type:
                continue  # Type de média non reconnu -> on l'ignore aussi

            comment_media = CommentMedia(
                comment_id=new_comment.id,
                media_url=url,
                media_type=media_type
            )
            db.session.add(comment_media)

        db.session.commit()

        # Envoie une notification à l'auteur du post (sauf si l'auteur commente son propre post)
        notify_user_on_new_comment(new_comment)

        user = User.query.get(user_id)

        # Recharge les médias depuis la base pour les inclure dans la réponse
        comment_media_list = CommentMedia.query.filter_by(comment_id=new_comment.id).all()
        media = [{
            'id': m.id,
            'url': m.media_url,
            'type': m.media_type,
            'created_at': m.created_at.isoformat()
        } for m in comment_media_list]

        return jsonify({
            'message': 'Comment created successfully',
            'comment': {
                'id': new_comment.id,
                'content': new_comment.content,
                'created_at': new_comment.created_at.isoformat(),
                'post_id': new_comment.post_id,
                'user_id': new_comment.user_id,
                'media': media,
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else None,
                    'first_name': user.first_name if user else None,
                    'last_name': user.last_name if user else None,
                    'profile_picture': user.profile_picture if user else None
                }
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create comment: {str(e)}'}), 500


def notify_user_on_new_comment(comment):
    """
    Crée une notification pour l'auteur du post lorsqu'un nouveau commentaire est posté,
    sauf si l'auteur du commentaire est aussi l'auteur du post (pas de notification à soi-même).
    Les erreurs ici sont volontairement absorbées (juste loguées) pour ne pas faire échouer
    la création du commentaire si la notification échoue.
    """
    try:
        post = Post.query.get(comment.post_id)
        if post and post.user_id != comment.user_id:
            notification = Notification(
                post_id=post.id,
                comments_id=comment.id,
                user_id=post.user_id,
                replie_id=None,
                follow_id=None,
                type="comment"
            )
            db.session.add(notification)
            db.session.commit()

            print(f"Notification envoyée à l'utilisateur {post.user_id} pour un commentaire sur le post {post.id}.")
        else:
            # Ce message s'affiche aussi si l'auteur commente son propre post (cas normal, pas une vraie erreur)
            print("Erreur : Impossible de récupérer le post lié au commentaire.")
    except Exception as e:
        print(f"Erreur lors de la notification: {e}")


# ============================================================
# Route : tous les commentaires d'un post, avec leurs médias, likes et réponses
# (vue "complète" utilisée typiquement pour afficher un post avec ses commentaires)
# ============================================================
@comments_api.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_post_comments(post_id):
    try:
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
        result = []

        for comment in comments:
            user = User.query.get(comment.user_id)

            comment_media_list = CommentMedia.query.filter_by(comment_id=comment.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type,
                'created_at': m.created_at.isoformat()
            } for m in comment_media_list]

            likes_count = CommentLike.query.filter_by(comment_id=comment.id).count()

            # Récupère les réponses directes à ce commentaire (1 niveau de profondeur uniquement ici,
            # contrairement à get_comment qui gère aussi les sous-réponses)
            replies = Reply.query.filter_by(comment_id=comment.id).order_by(Reply.created_at.asc()).all()
            replies_data = []

            for reply in replies:
                reply_user = User.query.get(reply.user_id)

                reply_media_list = ReplyMedia.query.filter_by(replies_id=reply.id).all()
                reply_media = [{
                    'id': m.id,
                    'url': m.media_url,
                    'type': m.media_type,
                    'created_at': m.created_at.isoformat()
                } for m in reply_media_list]

                reply_likes_count = ReplyLike.query.filter_by(replies_id=reply.id).count()

                replies_data.append({
                    'id': reply.id,
                    'content': reply.content,
                    'created_at': reply.created_at.isoformat(),
                    'comment_id': reply.comment_id,
                    'user_id': reply.user_id,
                    'likes_count': reply_likes_count,
                    'media': reply_media,
                    'user': {
                        'id': reply_user.id if reply_user else None,
                        'pseudo': reply_user.pseudo if reply_user else None,
                        'first_name': reply_user.first_name if reply_user else None,
                        'last_name': reply_user.last_name if reply_user else None,
                        'profile_picture': reply_user.profile_picture if reply_user else None
                    }
                })

            result.append({
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'post_id': comment.post_id,
                'user_id': comment.user_id,
                'media': media,
                'likes_count': likes_count,
                'replies': replies_data,
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else None,
                    'first_name': user.first_name if user else None,
                    'last_name': user.last_name if user else None,
                    'profile_picture': user.profile_picture if user else None
                }
            })

        return jsonify({'comments': result}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to fetch comments: {str(e)}'}), 500


# ============================================================
# Route : liste brute de TOUS les commentaires (toutes données confondues)
# Version minimale, sans médias/likes/réponses ni infos utilisateur
# ============================================================
@comments_api.route('/api/comments', methods=['GET'])
def get_comments():
    comments = Comment.query.all()
    comments_list = [{'id': comment.id, 'content': comment.content, 'post_id': comment.post_id, 'user_id': comment.user_id} for comment in comments]

    return jsonify({'comments': comments_list}), 200


# ============================================================
# Route : mise à jour du contenu d'un commentaire
# ============================================================
@comments_api.route('/api/comments/<int:comment_id>', methods=['PUT'])
def update_comment(comment_id):
    data = request.get_json()
    content = data.get('content')

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    # Note : si content est une chaîne vide (""), elle est falsy donc ignorée
    if content:
        comment.content = content

    db.session.commit()

    return jsonify({'message': 'Comment updated successfully'}), 200


# ============================================================
# Route : suppression d'un commentaire
# ============================================================
@comments_api.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': 'Comment deleted successfully'}), 200


# ============================================================
# Route : détail complet d'un commentaire, avec arborescence des réponses
# sur 2 niveaux (réponses directes + sous-réponses de chaque réponse)
# ============================================================
@comments_api.route('/api/comments/<int:comment_id>', methods=['GET'])
def get_comment(comment_id):
    try:
        comment = Comment.query.get(comment_id)
        if not comment:
            return jsonify({'error': 'Comment not found'}), 404

        user = User.query.get(comment.user_id)

        comment_media_list = CommentMedia.query.filter_by(comment_id=comment.id).all()
        media = [{
            'id': m.id,
            'url': m.media_url,
            'type': m.media_type,
            'created_at': m.created_at.isoformat()
        } for m in comment_media_list]

        likes_count = CommentLike.query.filter_by(comment_id=comment.id).count()

        # Niveau 1 : réponses directes au commentaire
        replies = Reply.query.filter_by(comment_id=comment.id).order_by(Reply.created_at.asc()).all()
        replies_data = []

        for reply in replies:
            reply_user = User.query.get(reply.user_id)

            reply_media_list = ReplyMedia.query.filter_by(replies_id=reply.id).all()
            reply_media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type,
                'created_at': m.created_at.isoformat()
            } for m in reply_media_list]

            reply_likes_count = ReplyLike.query.filter_by(replies_id=reply.id).count()

            # Niveau 2 : réponses à cette réponse (sous-réponses).
            #  Cette structure ne gère que 2 niveaux de profondeur : si une sous-réponse
            # a elle-même des réponses, elles ne seront pas incluses ici (contrairement à
            # find_original_post dans chats_routes qui remonte récursivement sans limite).
            sub_replies = Reply.query.filter_by(replies_id=reply.id).order_by(Reply.created_at.asc()).all()
            sub_replies_data = []

            for sub_reply in sub_replies:
                sub_reply_user = User.query.get(sub_reply.user_id)

                sub_reply_media_list = ReplyMedia.query.filter_by(replies_id=sub_reply.id).all()
                sub_reply_media = [{
                    'id': m.id,
                    'url': m.media_url,
                    'type': m.media_type,
                    'created_at': m.created_at.isoformat()
                } for m in sub_reply_media_list]

                sub_reply_likes_count = ReplyLike.query.filter_by(replies_id=sub_reply.id).count()

                sub_replies_data.append({
                    'id': sub_reply.id,
                    'content': sub_reply.content,
                    'created_at': sub_reply.created_at.isoformat(),
                    'comment_id': sub_reply.comment_id,
                    'replies_id': sub_reply.replies_id,
                    'user_id': sub_reply.user_id,
                    'likes_count': sub_reply_likes_count,
                    'media': sub_reply_media,
                    'user': {
                        'id': sub_reply_user.id if sub_reply_user else None,
                        'pseudo': sub_reply_user.pseudo if sub_reply_user else None,
                        'first_name': sub_reply_user.first_name if sub_reply_user else None,
                        'last_name': sub_reply_user.last_name if sub_reply_user else None,
                        'profile_picture': sub_reply_user.profile_picture if sub_reply_user else None
                    }
                })

            replies_data.append({
                'id': reply.id,
                'content': reply.content,
                'created_at': reply.created_at.isoformat(),
                'comment_id': reply.comment_id,
                'user_id': reply.user_id,
                'likes_count': reply_likes_count,
                'media': reply_media,
                'sub_replies': sub_replies_data,
                'user': {
                    'id': reply_user.id if reply_user else None,
                    'pseudo': reply_user.pseudo if reply_user else None,
                    'first_name': reply_user.first_name if reply_user else None,
                    'last_name': reply_user.last_name if reply_user else None,
                    'profile_picture': reply_user.profile_picture if reply_user else None
                }
            })

        comment_data = {
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'post_id': comment.post_id,
            'user_id': comment.user_id,
            'likes_count': likes_count,
            'media': media,
            'replies': replies_data,
            'user': {
                'id': user.id if user else None,
                'pseudo': user.pseudo if user else None,
                'first_name': user.first_name if user else None,
                'last_name': user.last_name if user else None,
                'profile_picture': user.profile_picture if user else None
            }
        }

        return jsonify({'comment': comment_data}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to fetch comment: {str(e)}'}), 500


# ============================================================
# Route : liste brute des réponses directes à un commentaire
# (version minimale, sans médias/likes/sous-réponses ni infos utilisateur)
# Utilise ici la relation ORM `comment.replies` plutôt qu'une requête manuelle
# ============================================================
@comments_api.route('/api/comments/<int:comment_id>/replies', methods=['GET'])
def get_comment_replies(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404

    # `comment.replies` est une relation SQLAlchemy qui retourne les réponses liées à ce commentaire
    replies = comment.replies.all()
    replies_list = [{'id': reply.id, 'content': reply.content, 'comment_id': reply.comment_id, 'user_id': reply.user_id} for reply in replies]

    return jsonify({'replies': replies_list}), 200