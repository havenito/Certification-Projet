from flask import Blueprint, request, jsonify
from models import db
from models.like import Like
from models.post import Post
from models.user import User
from models.category import Category

likes_bp = Blueprint('likes', __name__)


# ============================================================
# Route : like / unlike d'un post (toggle)
# Si l'utilisateur a déjà liké -> on retire le like
# Sinon -> on ajoute le like
# ============================================================
@likes_bp.route('/api/posts/<int:post_id>/like', methods=['POST'])
def toggle_like(post_id):
    """Toggle like sur un post"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'user_id requis'}), 400

        post = Post.query.get(post_id)
        if not post:
            return jsonify({'error': 'Post non trouvé'}), 404

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # Vérifie si l'utilisateur a déjà liké ce post
        existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()

        if existing_like:
            # Le like existe déjà -> on le supprime (unlike)
            db.session.delete(existing_like)
            db.session.commit()

            likes_count = Like.query.filter_by(post_id=post_id).count()

            return jsonify({
                'message': 'Like retiré',
                'liked': False,
                'likes_count': likes_count
            }), 200
        else:
            # Pas encore de like -> on en crée un
            new_like = Like(user_id=user_id, post_id=post_id)
            db.session.add(new_like)
            db.session.commit()

            likes_count = Like.query.filter_by(post_id=post_id).count()

            return jsonify({
                'message': 'Post liké',
                'liked': True,
                'likes_count': likes_count
            }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : liste des likes d'un post, avec les infos des utilisateurs concernés
# ============================================================
@likes_bp.route('/api/posts/<int:post_id>/likes', methods=['GET'])
def get_post_likes(post_id):
    """Obtenir les likes d'un post"""
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'error': 'Post non trouvé'}), 404

        likes = Like.query.filter_by(post_id=post_id).all()
        likes_count = len(likes)
        # Pour chaque like, on récupère les infos publiques de l'utilisateur correspondant
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
            'post_id': post_id,
            'likes_count': likes_count,
            'users': users_who_liked
        }), 200

    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : vérifie si un utilisateur donné a liké un post donné
# (utile côté frontend pour afficher l'état initial du bouton like)
# ============================================================
@likes_bp.route('/api/users/<int:user_id>/posts/<int:post_id>/like-status', methods=['GET'])
def check_like_status(user_id, post_id):
    """Vérifier si un utilisateur a liké un post"""
    try:
        like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
        return jsonify({
            'liked': like is not None
        }), 200
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : tous les likes d'un utilisateur, toutes catégories confondues
# (posts likés + commentaires likés + réponses likées), fusionnés et triés
# par date de création décroissante.
#
# C'est la route la plus lourde du fichier : pour chaque type de contenu liké,
# elle recharge l'objet complet (post/commentaire/réponse), son auteur, ses
# médias, son nombre de likes, et parfois le contenu "parent" (post d'origine
# pour un commentaire, commentaire d'origine pour une réponse). Le tout sans
# pagination : sur un compte avec beaucoup de likes, cette route peut devenir
# coûteuse en nombre de requêtes SQL (pattern N+1 répété à plusieurs niveaux).
# ============================================================
@likes_bp.route('/api/users/<int:user_id>/likes', methods=['GET'])
def get_user_likes(user_id):
    """Obtenir tous les likes d'un utilisateur (posts, commentaires et réponses)"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # Liste finale qui va accueillir les 3 types de contenus likés mélangés
        all_likes = []

        # --- 1. Posts likés par l'utilisateur ---
        post_likes = Like.query.filter_by(user_id=user_id).order_by(Like.id.desc()).all()

        for like in post_likes:
            post = Post.query.get(like.post_id)
            if post:
                post_user = User.query.get(post.user_id)

                from models.post_media import PostMedia
                media_list = PostMedia.query.filter_by(post_id=post.id).all()
                media = [{
                    'id': m.id,
                    'url': m.media_url,
                    'type': m.media_type
                } for m in media_list]

                category = None
                if post.category_id:
                    from models.category import Category
                    cat = Category.query.get(post.category_id)
                    if cat:
                        category = {
                            'id': cat.id,
                            'name': cat.name,
                            'description': cat.description
                        }

                from models.comment import Comment
                comments_count = Comment.query.filter_by(post_id=post.id).count()

                likes_count = Like.query.filter_by(post_id=post.id).count()

                # NB: certains champs sont dupliqués en camelCase ET snake_case
                # (ex: 'firstName' et 'first_name') probablement pour compatibilité
                # avec différentes parties du frontend qui attendent des conventions différentes
                all_likes.append({
                    'id': post.id,
                    'type': 'post',
                    'title': post.title,
                    'content': post.content,
                    'publishedAt': post.published_at.isoformat() if post.published_at else None,
                    'created_at': post.published_at.isoformat() if post.published_at else None,
                    'media': media,
                    'likes': likes_count,
                    'likes_count': likes_count,
                    'comments': comments_count,
                    'category': category,
                    'user': {
                        'id': post_user.id if post_user else None,
                        'pseudo': post_user.pseudo if post_user else None,
                        'firstName': post_user.first_name if post_user else None,
                        'lastName': post_user.last_name if post_user else None,
                        'profilePicture': post_user.profile_picture if post_user else None,
                        'first_name': post_user.first_name if post_user else None,
                        'last_name': post_user.last_name if post_user else None,
                        'profile_picture': post_user.profile_picture if post_user else None
                    } if post_user else None
                })

        # --- 2. Commentaires likés par l'utilisateur ---
        from models.comment_like import CommentLike
        from models.comment_media import CommentMedia

        comment_likes = CommentLike.query.filter_by(user_id=user_id).order_by(CommentLike.id.desc()).all()

        for like in comment_likes:
            comment = Comment.query.get(like.comment_id)
            if comment:
                comment_user = User.query.get(comment.user_id)

                comment_media_list = CommentMedia.query.filter_by(comment_id=comment.id).all()
                media = [{
                    'id': m.id,
                    'url': m.media_url,
                    'type': m.media_type
                } for m in comment_media_list]

                # Récupère un résumé minimal du post d'origine du commentaire (pour contexte)
                original_post = None
                if comment.post_id:
                    post = Post.query.get(comment.post_id)
                    if post:
                        post_user = User.query.get(post.user_id)
                        original_post = {
                            'id': post.id,
                            'title': post.title,
                            'content': post.content,
                            'user': {
                                'pseudo': post_user.pseudo if post_user else None
                            }
                        }

                likes_count = CommentLike.query.filter_by(comment_id=comment.id).count()

                all_likes.append({
                    'id': comment.id,
                    'type': 'comment',
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None,
                    'media': media,
                    'likes_count': likes_count,
                    'originalPost': original_post,
                    'user': {
                        'id': comment_user.id if comment_user else None,
                        'pseudo': comment_user.pseudo if comment_user else None,
                        'firstName': comment_user.first_name if comment_user else None,
                        'lastName': comment_user.last_name if comment_user else None,
                        'profilePicture': comment_user.profile_picture if comment_user else None,
                        'first_name': comment_user.first_name if comment_user else None,
                        'last_name': comment_user.last_name if comment_user else None,
                        'profile_picture': comment_user.profile_picture if comment_user else None
                    } if comment_user else None
                })

        # --- 3. Réponses (replies) likées par l'utilisateur ---
        from models.reply_like import ReplyLike
        from models.reply import Reply
        from models.reply_media import ReplyMedia

        reply_likes = ReplyLike.query.filter_by(user_id=user_id).order_by(ReplyLike.id.desc()).all()

        for like in reply_likes:
            reply = Reply.query.get(like.replies_id)
            if reply:
                reply_user = User.query.get(reply.user_id)

                reply_media_list = ReplyMedia.query.filter_by(replies_id=reply.id).all()
                media = [{
                    'id': m.id,
                    'url': m.media_url,
                    'type': m.media_type
                } for m in reply_media_list]

                # Récupère un résumé minimal du commentaire d'origine de la réponse (pour contexte)
                original_comment = None
                if reply.comment_id:
                    comment = Comment.query.get(reply.comment_id)
                    if comment:
                        comment_user = User.query.get(comment.user_id)
                        original_comment = {
                            'id': comment.id,
                            'content': comment.content,
                            'user': {
                                'pseudo': comment_user.pseudo if comment_user else None
                            }
                        }

                likes_count = ReplyLike.query.filter_by(replies_id=reply.id).count()

                all_likes.append({
                    'id': reply.id,
                    'type': 'reply',
                    'content': reply.content,
                    'created_at': reply.created_at.isoformat() if reply.created_at else None,
                    'media': media,
                    'likes_count': likes_count,
                    'originalComment': original_comment,
                    'user': {
                        'id': reply_user.id if reply_user else None,
                        'pseudo': reply_user.pseudo if reply_user else None,
                        'firstName': reply_user.first_name if reply_user else None,
                        'lastName': reply_user.last_name if reply_user else None,
                        'profilePicture': reply_user.profile_picture if reply_user else None,
                        'first_name': reply_user.first_name if reply_user else None,
                        'last_name': reply_user.last_name if reply_user else None,
                        'profile_picture': reply_user.profile_picture if reply_user else None
                    } if reply_user else None
                })

        # Fusionne les 3 types de likes (posts, commentaires, réponses) et trie le tout
        # par date de création décroissante (plus récent en premier), tous types confondus
        all_likes.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return jsonify({'likes': all_likes}), 200

    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500