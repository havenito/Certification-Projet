from flask import Blueprint, request, jsonify
from models import db
from models.post import Post
from models.user import User
from models.category import Category
from models.comment import Comment
from services.file_upload import upload_file, determine_media_type
from models.like import Like

posts_bp = Blueprint('posts', __name__)


# ============================================================
# Route : upload générique d'un fichier (non lié à un post précis)
# Doublon fonctionnel de /api/upload dans auth_bp — à vérifier si les deux
# routes sont vraiment nécessaires, ou si une seule devrait être conservée
# ============================================================
@posts_bp.route('/api/upload', methods=['POST'])
def upload_file_route():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    url, file_type = upload_file(file)

    if not url:
        return jsonify({'error': 'File upload failed'}), 500

    return jsonify({'url': url, 'file_type': file_type})


# ============================================================
# Route : création d'un nouveau post
# Gère aussi l'upload de plusieurs médias et la détection automatique
# des mentions (@pseudo) dans le contenu pour créer des notifications
# ============================================================
@posts_bp.route('/api/create_post', methods=['POST'])
def create_post():
    try:
        title = request.form['title']
        content = request.form['content']
        published_at = request.form['published_at']
        # post_id ici semble être un champ optionnel du formulaire (peut-être pour
        # un repost/citation d'un autre post ?), pas l'ID généré du nouveau post
        post_id = request.form.get('post_id')
        user_id = request.form['user_id']
        category_id = request.form['category_id']

        post = Post(
            title=title,
            content=content,
            published_at=published_at,
            user_id=user_id,
            category_id=category_id,
            post_id=post_id
        )

        # On enregistre d'abord le post pour obtenir son ID, nécessaire pour
        # lier les médias et les notifications ensuite
        db.session.add(post)
        db.session.commit()

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

        for file in media_files:
            url, file_type = upload_file(file)

            if not url:
                continue  # Upload échoué -> on ignore ce fichier

            media_type = determine_media_type(file_type)
            if not media_type:
                continue  # Type de média non reconnu -> on ignore aussi

            from models.post_media import PostMedia
            post_media = PostMedia(
                post_id=post.id,
                media_url=url,
                media_type=media_type
            )
            db.session.add(post_media)

        db.session.commit()

        # ── BLOC DES MENTIONS CORRIGÉ ET SÉCURISÉ ──
        import re
        from models.notification import Notification

        # Extraction de tous les mots commençant par @ (ex: "@john" -> "john")
        mentions = re.findall(r'@(\w+)', content)

        # set() pour dédupliquer : éviter de notifier plusieurs fois le même utilisateur
        # s'il est mentionné plusieurs fois dans le même post
        for pseudo in set(mentions):
            # Utilisation de .ilike() pour ignorer les problèmes de majuscules/minuscules
            mentioned_user = User.query.filter(User.pseudo.ilike(pseudo)).first()

            if mentioned_user:
                # Nettoyage et conversion des IDs pour éviter les faux négatifs de types (int vs str)
                id_mentionne = str(mentioned_user.id).strip()
                id_auteur = str(user_id).strip()

                # Vérification que l'auteur ne s'auto-mentionne pas
                # (pas de notification si quelqu'un se mentionne lui-même)
                if id_mentionne != id_auteur:
                    notif = Notification(
                        user_id=mentioned_user.id,
                        post_id=post.id,
                        type='mention'
                    )
                    db.session.add(notif)
                    print(f"[NOTIF SUCCESS] Notification créée pour @{mentioned_user.pseudo}")

        # Validation finale des notifications en BDD
        db.session.commit()
        # ──────────────────────────────────────────

        return jsonify({
            'message': 'Post created successfully',
            'post_id': post.id,
            'media_count': len(media_files)
        })

    except KeyError as e:
        # Un champ obligatoire du formulaire (title, content, user_id, etc.) est manquant
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create post: {str(e)}'}), 500


# ============================================================
# Route : notifications d'un utilisateur, version "posts" du fichier
# ============================================================
@posts_bp.route('/api/user_notifications/<int:user_id>', methods=['GET'])
def get_user_notifications(user_id):
    try:
        from models.notification import Notification
        from models.user import User
        from models.post import Post

        notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.id.desc()).all()

        result = []
        for n in notifications:
            post_data = None
            post_author = None

            if n.post_id:
                post = Post.query.get(n.post_id)
                if post:
                    post_author = User.query.get(post.user_id) if hasattr(post, 'user_id') else None
                    post_data = {
                        'id': post.id,
                        'user_pseudo': post_author.pseudo if post_author else "user"
                    }

            # Détermine "l'acteur" de la notification (celui qui a déclenché l'action) :
            # priorité à l'auteur du post lié, sinon tentative de trouver un attribut
            # générique sur le modèle Notification (peu fiable, voir avertissement plus haut)
            if post_author:
                actor = post_author
            else:
                actor_id = None
                for attr in ['sender_id', 'actor_id', 'creator_id']:
                    if hasattr(n, attr) and getattr(n, attr):
                        actor_id = getattr(n, attr)
                        if actor_id != user_id:
                            break
                actor = User.query.get(actor_id) if actor_id else None

            result.append({
                'id': n.id,
                'post_id': n.post_id,
                'type': n.type,
                'created_at': n.created_at.isoformat() if hasattr(n, 'created_at') and n.created_at else None,
                'post_data': post_data,
                'actor_user': {
                    # ⚠️ "Stripe"/"STRIPE" comme valeurs de fallback : probablement
                    # un reste de test/debug, pas une vraie valeur métier voulue
                    'pseudo': actor.pseudo if actor else "Stripe",
                    'first_name': actor.first_name if actor else "STRIPE",
                    'last_name': actor.last_name if actor else "STRIPE",
                    'profile_picture': actor.profile_picture if actor and hasattr(actor, 'profile_picture') else None,
                    'subscription': actor.subscription if actor and hasattr(actor, 'subscription') else 'free'
                }
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': f'Erreur backend: {str(e)}'}), 500


# ============================================================
# Route : mise à jour d'un post existant (titre, contenu, catégorie, médias)
# Accepte PUT ou POST (probablement pour compatibilité avec un client qui
# n'arrive pas à envoyer du multipart/form-data en PUT)
# ============================================================
@posts_bp.route('/api/update_post/<int:post_id>', methods=['PUT', 'POST'])
def update_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'error': 'Post not found'}), 404

        # Mise à jour partielle : chaque champ n'est modifié que s'il est présent dans la requête
        if 'title' in request.form:
            post.title = request.form['title']

        if 'content' in request.form:
            post.content = request.form['content']

        if 'category_id' in request.form:
            post.category_id = request.form['category_id']

        # Suppression de médias existants, transmise sous forme de liste JSON d'IDs
        if 'delete_media_ids' in request.form:
            import json
            from models.post_media import PostMedia
            try:
                media_ids_to_delete = json.loads(request.form['delete_media_ids'])

                if isinstance(media_ids_to_delete, list):
                    for media_id in media_ids_to_delete:
                        media_to_delete = PostMedia.query.get(media_id)
                        # Vérifie que le média appartient bien à CE post avant de le supprimer
                        # (empêche de supprimer un média d'un autre post en falsifiant l'ID)
                        if media_to_delete and media_to_delete.post_id == post.id:
                            db.session.delete(media_to_delete)

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Erreur lors du parsing des IDs de médias à supprimer: {e}")

        media_files = []

        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                media_files.append(file)

        # Note : la clé utilisée ici est 'new_files[]', différente de 'files[]'
        # utilisée dans create_post — à garder en tête côté frontend
        if 'new_files[]' in request.files:
            files = request.files.getlist('new_files[]')
            for file in files:
                if file.filename:
                    media_files.append(file)

        for file in media_files:
            url, file_type = upload_file(file)

            if not url:
                continue

            media_type = determine_media_type(file_type)
            if not media_type:
                continue

            from models.post_media import PostMedia
            post_media = PostMedia(
                post_id=post.id,
                media_url=url,
                media_type=media_type
            )
            db.session.add(post_media)

        db.session.commit()

        # Recharge la liste complète des médias actuels (après suppression/ajout) pour la réponse
        from models.post_media import PostMedia
        media_list = PostMedia.query.filter_by(post_id=post.id).all()
        media = []

        for item in media_list:
            media.append({
                'id': item.id,
                'url': item.media_url,
                'type': item.media_type
            })

        return jsonify({
            'message': 'Post updated successfully',
            'post': {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'media': media
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update post: {str(e)}'}), 500


# ============================================================
# Route : détail brut d'un post par son ID (sans likes/commentaires/auteur enrichi)
# ============================================================
@posts_bp.route('/api/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    from models.post_media import PostMedia
    media_list = PostMedia.query.filter_by(post_id=post.id).all()
    media = []

    for item in media_list:
        media.append({
            'id': item.id,
            'url': item.media_url,
            'type': item.media_type
        })

    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'published_at': post.published_at,
        'media': media,
        'user_id': post.user_id,
        'category_id': post.category_id
    })


# ============================================================
# Route : suppression d'un post
# ============================================================
@posts_bp.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({'error': 'Post not found'}), 404

        db.session.delete(post)
        db.session.commit()

        return jsonify({'message': 'Post deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete post: {str(e)}'}), 500


# ============================================================
# Route : liste de TOUS les posts (toutes catégories/utilisateurs confondus)
# avec auteur, catégorie, médias, likes et commentaires comptés.
# ⚠️ Pas de pagination ici, contrairement à get_foryou_posts et get_following_posts
# qui paginent. Sur une base avec beaucoup de posts, cette route sera coûteuse.
# ============================================================
@posts_bp.route('/api/posts', methods=['GET'])
def get_all_posts():
    try:
        posts = Post.query.order_by(Post.published_at.desc()).all()
        result = []

        for post in posts:
            user = User.query.get(post.user_id)
            category = Category.query.get(post.category_id)

            from models.post_media import PostMedia
            media_list = PostMedia.query.filter_by(post_id=post.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type
            } for m in media_list]

            likes_count = Like.query.filter_by(post_id=post.id).count()
            comments_count = Comment.query.filter_by(post_id=post.id).count()

            result.append({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'publishedAt': post.published_at.isoformat(),
                'media': media,
                'userId': post.user_id,
                'categoryId': post.category_id,
                'likes': likes_count,
                'comments': comments_count,
                # Placeholder si l'auteur ou la catégorie ont été supprimés depuis
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else 'Utilisateur supprimé',
                    'profilePicture': user.profile_picture if user else None,
                    'firstName': user.first_name if user else None,
                    'lastName': user.last_name if user else None
                },
                'category': {
                    'id': category.id if category else None,
                    'name': category.name if category else 'Catégorie supprimée',
                    'description': category.description if category else None
                }
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Route : suppression d'un média précis (image/vidéo) lié à un post
# ============================================================
@posts_bp.route('/api/media/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    try:
        from models.post_media import PostMedia
        media_to_delete = PostMedia.query.get(media_id)

        if not media_to_delete:
            return jsonify({'error': 'Média non trouvé'}), 404

        db.session.delete(media_to_delete)
        db.session.commit()

        return jsonify({'message': 'Média supprimé avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la suppression du média: {str(e)}'}), 500


# ============================================================
# Route : tous les posts créés par un utilisateur donné
# ⚠️ Pas de pagination ici non plus (contrairement à foryou/following).
# Les champs sont aussi dupliqués en camelCase ET snake_case
# (ex: 'published_at' et 'publishedAt') pour compatibilité avec différentes
# parties du frontend qui attendent des conventions de nommage différentes.
# ============================================================
@posts_bp.route('/api/users/<int:user_id>/posts', methods=['GET'])
def get_user_posts(user_id):
    try:
        posts = Post.query.filter_by(user_id=user_id).order_by(Post.published_at.desc()).all()
        result = []

        # L'utilisateur n'est récupéré qu'une seule fois ici (contrairement à get_all_posts
        # qui refait une requête User.query.get() par post), ce qui est plus efficace
        # puisque tous les posts appartiennent au même utilisateur
        user = User.query.get(user_id)

        for post in posts:
            category = Category.query.get(post.category_id)

            from models.post_media import PostMedia
            media_list = PostMedia.query.filter_by(post_id=post.id).all()
            media = []

            for item in media_list:
                media.append({
                    'id': item.id,
                    'url': item.media_url,
                    'type': item.media_type,
                    'created_at': item.created_at.isoformat() if item.created_at else None
                })

            likes_count = Like.query.filter_by(post_id=post.id).count()
            comments_count = Comment.query.filter_by(post_id=post.id).count()

            result.append({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'published_at': post.published_at.isoformat() if post.published_at else None,
                'publishedAt': post.published_at.isoformat() if post.published_at else None,
                'media': media,
                'user_id': post.user_id,
                'userId': post.user_id,
                'category_id': post.category_id,
                'categoryId': post.category_id,
                'likes': likes_count,
                'comments': comments_count,
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else 'Utilisateur supprimé',
                    'profilePicture': user.profile_picture if user else None,
                    'firstName': user.first_name if user else None,
                    'lastName': user.last_name if user else None
                },
                'category': {
                    'id': category.id if category else None,
                    'name': category.name if category else 'Catégorie supprimée',
                    'description': category.description if category else None
                }
            })

        return jsonify({'posts': result})
    except Exception as e:
        return jsonify({'error': f'Failed to fetch user posts: {str(e)}'}), 500


# ============================================================
# Route : fil "Pour vous" — tous les posts des comptes PUBLICS (non privés),
# paginé, du plus récent au plus ancien
# ============================================================
@posts_bp.route('/api/posts/foryou', methods=['GET'])
def get_foryou_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        # JOIN avec User pour ne récupérer que les posts d'utilisateurs au compte public
        posts = (
            Post.query
                .join(User, Post.user_id == User.id)
                .filter(User.private == False)
                .order_by(Post.published_at.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
        )

        result = []
        for post in posts.items:
            user = User.query.get(post.user_id)
            category = Category.query.get(post.category_id)

            from models.post_media import PostMedia
            media_list = PostMedia.query.filter_by(post_id=post.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type
            } for m in media_list]

            likes_count = Like.query.filter_by(post_id=post.id).count()
            comments_count = Comment.query.filter_by(post_id=post.id).count()

            result.append({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'publishedAt': post.published_at.isoformat(),
                'media': media,
                'userId': post.user_id,
                'categoryId': post.category_id,
                'likes': likes_count,
                'comments': comments_count,
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else 'Utilisateur supprimé',
                    'profilePicture': user.profile_picture if user else None,
                    'firstName': user.first_name if user else None,
                    'lastName': user.last_name if user else None
                },
                'category': {
                    'id': category.id if category else None,
                    'name': category.name if category else 'Catégorie supprimée',
                    'description': category.description if category else None
                }
            })

        return jsonify({
            'posts': result,
            'hasNext': posts.has_next,
            'nextPage': posts.next_num if posts.has_next else None,
            'totalPages': posts.pages,
            'currentPage': page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Route : fil "Abonnements" — posts des utilisateurs suivis par user_id, paginé
# ============================================================
@posts_bp.route('/api/posts/following/<int:user_id>', methods=['GET'])
def get_following_posts(user_id):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        # Récupère la liste des IDs des utilisateurs suivis par user_id
        from models.follow import Follow
        following_ids = db.session.query(Follow.followed_id).filter_by(follower_id=user_id).all()
        following_ids = [f[0] for f in following_ids]

        # Si l'utilisateur ne suit personne, on retourne directement une liste vide
        # sans interroger la table Post (évite une requête .in_([]) inutile)
        if not following_ids:
            return jsonify({
                'posts': [],
                'hasNext': False,
                'nextPage': None,
                'totalPages': 0,
                'currentPage': page
            })

        # Récupère les posts de tous les utilisateurs suivis, paginés
        posts = Post.query.filter(Post.user_id.in_(following_ids)).order_by(Post.published_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        result = []
        for post in posts.items:
            user = User.query.get(post.user_id)
            category = Category.query.get(post.category_id)

            from models.post_media import PostMedia
            media_list = PostMedia.query.filter_by(post_id=post.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type
            } for m in media_list]

            likes_count = Like.query.filter_by(post_id=post.id).count()
            comments_count = Comment.query.filter_by(post_id=post.id).count()

            result.append({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'publishedAt': post.published_at.isoformat(),
                'media': media,
                'userId': post.user_id,
                'categoryId': post.category_id,
                'likes': likes_count,
                'comments': comments_count,
                'user': {
                    'id': user.id if user else None,
                    'pseudo': user.pseudo if user else 'Utilisateur supprimé',
                    'profilePicture': user.profile_picture if user else None,
                    'firstName': user.first_name if user else None,
                    'lastName': user.last_name if user else None
                },
                'category': {
                    'id': category.id if category else None,
                    'name': category.name if category else 'Catégorie supprimée',
                    'description': category.description if category else None
                }
            })

        return jsonify({
            'posts': result,
            'hasNext': posts.has_next,
            'nextPage': posts.next_num if posts.has_next else None,
            'totalPages': posts.pages,
            'currentPage': page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500