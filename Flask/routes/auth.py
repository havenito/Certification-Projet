from flask import Blueprint, request, jsonify, current_app, make_response
from models import db
from models.user import User
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, decode_token, get_jwt_identity
from flask_mail import Message
from datetime import timedelta
import re
import os
from urllib.parse import quote
from services.file_upload import upload_file 

bcrypt = Bcrypt()
auth_bp = Blueprint('auth', __name__)

# Liste des types d'abonnement valides (utilisée pour valider la colonne ENUM en base)
SUBSCRIPTION_TYPES = ['free', 'plus', 'premium']

# Pseudos réservés interdits
# Ces pseudos correspondent à des routes/chemins de l'application
# (pages, dossiers statiques, etc.) et ne doivent pas pouvoir être pris par un utilisateur,
# sinon cela créerait des conflits de routing (ex: /profile/admin vs /admin).
RESERVED_PSEUDOS = [
    'login', 'register', 'comment', 'edit-profile', 'favorites', 'followers', 
    'following', 'post', 'reply', 'foryou', 'message', 'home', 'polls', 
    'search', 'premium', 'api', 'auth', 'forgot-password', 'reset-password', 
    'notifications', 'admin', 'user', 'reports', 'dashboard', 'settings',
    'profile', 'about', 'help', 'support', 'contact', 'terms', 'privacy',
    'www', 'mail', 'email', 'ftp', 'blog', 'news', 'static', 'assets',
    'css', 'js', 'img', 'images', 'upload', 'download', 'test', 'demo'
]


def validate_subscription_type(subscription_type):
    """Valide que le type d'abonnement est autorisé par l'ENUM"""
    if subscription_type not in SUBSCRIPTION_TYPES:
        raise ValueError(f"Type d'abonnement invalide: {subscription_type}. Valeurs autorisées: {SUBSCRIPTION_TYPES}")
    return subscription_type


def validate_pseudo(pseudo):
    """
    Valide que le pseudo n'est pas réservé et respecte les critères de format.
    Retourne un message d'erreur (str) si invalide, ou None si valide.
    """
    if not pseudo:
        return "Le pseudo est requis."

    # Normalisation pour comparer indépendamment de la casse / espaces
    normalized_pseudo = pseudo.strip().lower()

    # Vérifie que le pseudo ne correspond pas à une route réservée
    if normalized_pseudo in [reserved.lower() for reserved in RESERVED_PSEUDOS]:
        return f"Le pseudo '{pseudo}' est réservé et ne peut pas être utilisé."

    # Longueur minimale
    if len(pseudo) < 3:
        return "Le pseudo doit contenir au moins 3 caractères."

    # Longueur maximale
    if len(pseudo) > 30:
        return "Le pseudo ne peut pas dépasser 30 caractères."

    # Seuls lettres, chiffres, points, tirets et underscores sont autorisés
    if not re.match(r'^[a-zA-Z0-9_.-]+$', pseudo):
        return "Le pseudo ne peut contenir que des lettres, chiffres, points, tirets et underscores."

    # Interdit de commencer ou finir par un caractère spécial
    if pseudo.startswith(('.', '-', '_')) or pseudo.endswith(('.', '-', '_')):
        return "Le pseudo ne peut pas commencer ou finir par un point, tiret ou underscore."

    return None


# --- Password vérification ---
def validate_password(password):
    """
    Vérifie que le mot de passe respecte la politique de sécurité minimale :
    8 caractères, majuscule, minuscule, chiffre et caractère spécial.
    Retourne un message d'erreur (str) si invalide, ou None si valide.
    """
    if len(password) < 8:
        return "Le mot de passe doit contenir au moins 8 caractères."
    if not re.search(r'[A-Z]', password):
        return "Le mot de passe doit contenir au moins une lettre majuscule."
    if not re.search(r'[a-z]', password):
        return "Le mot de passe doit contenir au moins une lettre minuscule."
    if not re.search(r'[0-9]', password):
        return "Le mot de passe doit contenir au moins un chiffre."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_-]', password):
        return "Le mot de passe doit contenir au moins un caractère spécial."
    return None


def validate_image_file(file, user_subscription, file_type='image'):
    """
    Valide un fichier image selon le type d'abonnement de l'utilisateur.
    - Vérifie que le fichier est bien une image.
    - Les GIFs ne sont autorisés que pour les abonnements 'plus' et 'premium'.
    Retourne un tuple (fichier_valide_ou_None, message_erreur_ou_None).
    """
    if not file:
        return None, None

    # Vérifier que c'est bien un fichier image (via le content-type MIME)
    if not file.content_type or not file.content_type.startswith('image/'):
        return None, f"Le fichier doit être une image pour {file_type}."

    is_gif = file.content_type == 'image/gif'

    # Si c'est un GIF et que l'utilisateur n'a pas d'abonnement premium/plus, on refuse
    if is_gif and user_subscription not in ['plus', 'premium']:
        return None, f"Les GIFs ne sont disponibles que pour les abonnements Plus et Premium. Votre {file_type} doit être une image statique (JPEG, PNG, WebP)."

    # Types d'images autorisés par défaut (sans GIF)
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    # On ajoute le GIF à la liste des formats autorisés uniquement pour plus/premium
    if user_subscription in ['plus', 'premium']:
        allowed_types.append('image/gif')

    if file.content_type not in allowed_types:
        if user_subscription in ['plus', 'premium']:
            return None, f"Format non supporté. Formats autorisés: JPEG, PNG, WebP, GIF."
        else:
            return None, f"Format non supporté. Formats autorisés: JPEG, PNG, WebP. Les GIFs sont réservés aux abonnements Plus et Premium."

    return file, None


# ============================================================
# Route : création d'un nouvel utilisateur (inscription)
# Accepte soit du multipart/form-data (avec fichiers image)
# soit du JSON classique.
# ============================================================
@auth_bp.route('/api/users', methods=['POST'])
def create_user():
    profile_picture_to_save = None
    banner_image_to_save = None
    data_source = None
    biography_data = None

    # --- Cas 1 : requête multipart (upload de fichiers possible) ---
    if request.content_type and 'multipart/form-data' in request.content_type:
        data_source = request.form
        email = data_source.get('email', '').strip().lower()
        password = data_source.get('password', '').strip()
        first_name = data_source.get('first_name', '').strip()
        last_name_data = data_source.get('last_name')
        last_name = last_name_data.strip() if isinstance(last_name_data, str) else last_name_data
        pseudo = data_source.get('pseudo', '').strip()
        biography_data = data_source.get('biography', '').strip() or None

        # Le champ isPublic arrive en string ('true'/'false') depuis le form-data
        is_public_str = data_source.get('isPublic', 'true')
        private = not (is_public_str.lower() == 'true')

        roles = data_source.get('roles', 'user').strip()

        # Pour les nouveaux utilisateurs, l'abonnement par défaut est 'free'
        user_subscription = 'free'

        # Upload de la photo de profil si présente dans la requête
        if 'profile_picture' in request.files:
            profile_picture_file = request.files['profile_picture']
            validated_file, error_msg = validate_image_file(profile_picture_file, user_subscription, 'photo de profil')
            if error_msg:
                return jsonify({'error': error_msg}), 400
            if validated_file:
                url, file_type = upload_file(validated_file)
                if url:
                    profile_picture_to_save = url
                else:
                    return jsonify({'error': 'Erreur lors du téléchargement de la photo de profil'}), 500

        # Upload de l'image de bannière si présente dans la requête
        if 'banner_image' in request.files:
            banner_file = request.files['banner_image']
            validated_file, error_msg = validate_image_file(banner_file, user_subscription, 'bannière')
            if error_msg:
                return jsonify({'error': error_msg}), 400
            if validated_file:
                url, file_type = upload_file(validated_file)
                if url:
                    banner_image_to_save = url
                else:
                    return jsonify({'error': 'Erreur lors du téléchargement de la bannière'}), 500
    else:
        # --- Cas 2 : requête JSON classique (pas de fichiers, juste des URLs) ---
        json_data = request.get_json()
        if not json_data:
            return jsonify({'error': 'Aucune donnée fournie'}), 400
        data_source = json_data

        email = data_source.get('email', '').strip().lower()
        password = data_source.get('password', '').strip()
        first_name = data_source.get('first_name', '').strip()
        last_name_data = data_source.get('last_name')
        last_name = last_name_data.strip() if isinstance(last_name_data, str) else last_name_data
        # En JSON, on attend directement des URLs d'images déjà uploadées
        profile_picture_to_save = data_source.get('profile_picture')
        banner_image_to_save = data_source.get('banner')
        pseudo = data_source.get('pseudo', '').strip()
        biography_data = data_source.get('biography', '').strip() or None
        private = data_source.get('private', False)
        roles = data_source.get('roles', 'user').strip()

    # --- Validation des champs obligatoires ---
    if not all([email, password, first_name, pseudo]):
        return jsonify({'error': 'Les champs email, mot de passe, prénom et pseudo sont obligatoires'}), 400

    # Validation du format du pseudo (longueur, caractères, mots réservés)
    if pseudo_error := validate_pseudo(pseudo):
        return jsonify({'error': pseudo_error}), 400

    # Validation de la robustesse du mot de passe
    if err := validate_password(password):
        return jsonify({'error': err}), 400

    # Vérifie l'unicité de l'email
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Un utilisateur avec cet email existe déjà'}), 400

    # Vérifie l'unicité du pseudo
    if User.query.filter_by(pseudo=pseudo).first():
        return jsonify({'error': 'Ce pseudo est déjà utilisé'}), 400

    # Hashage sécurisé du mot de passe avant stockage en base
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    # L'abonnement par défaut d'un nouvel utilisateur est toujours 'free'
    default_subscription = 'free'
    validate_subscription_type(default_subscription)

    # Création de l'objet utilisateur en mémoire
    new_user = User(
        email=email,
        password=hashed_password,
        roles=roles,
        first_name=first_name,
        last_name=last_name,
        profile_picture=profile_picture_to_save,
        pseudo=pseudo,
        private=private,
        biography=biography_data,
        banner=banner_image_to_save,
        subscription=default_subscription
    )

    # Persistance en base de données
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        'message': 'Utilisateur créé avec succès',
        'user_id': new_user.id,
        'profile_picture': new_user.profile_picture,
        'banner': new_user.banner,
        'subscription': new_user.subscription
    }), 201


# ============================================================
# Route générique d'upload de fichier (non liée à un champ utilisateur précis)
# ============================================================
@auth_bp.route('/api/upload', methods=['POST'])
def upload_profile_image():
    # Vérifie qu'un fichier a bien été envoyé dans la requête
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    # Le navigateur envoie un objet fichier vide si l'utilisateur n'a rien sélectionné
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        url, file_type = upload_file(file)
        if url:
            return jsonify({'url': url, 'type': file_type}), 200
        else:
            return jsonify({'error': 'Failed to upload file'}), 500
    return jsonify({'error': 'File processing error'}), 400


from datetime import datetime


# ============================================================
# Route : connexion utilisateur (login classique email/mot de passe)
# ============================================================
@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email et mot de passe requis'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': "Aucun compte n'existe avec cet email."}), 401

    # Si l'utilisateur était banni temporairement et que la date de fin est dépassée,
    # on lève automatiquement le ban avant de continuer le processus de login
    if user.is_banned and user.ban_until:
        if datetime.utcnow() > user.ban_until:
            user.is_banned = False
            user.ban_until = None
            db.session.commit()

    # Si l'utilisateur est toujours banni, on bloque la connexion
    if user.is_banned:
        if user.ban_until:
            return jsonify({'error': f'Votre compte est banni jusqu\'au {user.ban_until.strftime("%d/%m/%Y %H:%M:%S")}.'}), 403
        return jsonify({'error': 'Votre compte a été banni.'}), 403

    # Si le compte n'a pas de mot de passe, c'est un compte créé via OAuth (Google/GitHub)
    if user.password is None:
        return jsonify({'error': 'Ce compte a été créé via un fournisseur externe (Google/GitHub). Veuillez vous connecter en utilisant le bouton correspondant.'}), 401

    # Vérification du mot de passe via bcrypt
    if bcrypt.check_password_hash(user.password, password):
        user_data = {
            'id': user.id,
            'email': user.email,
            'roles': user.roles,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'pseudo': user.pseudo,
            'profile_picture': user.profile_picture,
            'private': user.private,
            'biography': user.biography,
            'banner': user.banner,
            'subscription': user.subscription_level
        }
        return jsonify({'message': 'Connexion réussie', 'user': user_data}), 200
    else:
        return jsonify({'error': 'Mot de passe incorrect.'}), 401


# ============================================================
# Route : liste de tous les utilisateurs
# ============================================================
@auth_bp.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    result = []

    for user_obj in users:
        result.append({
            'id': user_obj.id,
            'email': user_obj.email,
            'first_name': user_obj.first_name,
            'last_name': user_obj.last_name,
            'roles': user_obj.roles,
            'profile_picture': user_obj.profile_picture,
            'pseudo': user_obj.pseudo,
            'private': user_obj.private,
            # hasattr() permet d'éviter une erreur si le modèle n'a pas ces colonnes
            'created_at': user_obj.created_at.isoformat() if hasattr(user_obj, 'created_at') and user_obj.created_at else None,
            'updated_at': user_obj.updated_at.isoformat() if hasattr(user_obj, 'updated_at') and user_obj.updated_at else None,
            'banner': user_obj.banner,
            'subscription': user_obj.subscription
        })

    return jsonify(result)


# ============================================================
# Route : mise à jour d'un utilisateur (profil, photo, bannière, etc.)
# Gère aussi le préflight CORS (OPTIONS)
# ============================================================
@auth_bp.route('/api/users/<int:user_id>', methods=['PUT', 'OPTIONS'])
def update_user(user_id):
    # Réponse au préflight CORS envoyé par le navigateur avant la vraie requête PUT
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

    user_to_update = User.query.get(user_id)
    if not user_to_update:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    # Valeurs par défaut = valeurs actuelles, modifiées seulement si besoin
    profile_picture_url_to_set = user_to_update.profile_picture
    banner_image_url_to_set = user_to_update.banner
    data_source = None

    # --- Cas 1 : requête multipart (nouveaux fichiers image possibles) ---
    if request.content_type and 'multipart/form-data' in request.content_type:
        data_source = request.form

        user_subscription = user_to_update.subscription or 'free'

        # Mise à jour de la photo de profil si un nouveau fichier est fourni
        if 'profile_picture' in request.files:
            profile_picture_file = request.files['profile_picture']
            validated_file, error_msg = validate_image_file(profile_picture_file, user_subscription, 'photo de profil')
            if error_msg:
                return jsonify({'error': error_msg}), 400
            if validated_file:
                try:
                    url, file_type = upload_file(validated_file)
                    if url:
                        profile_picture_url_to_set = url
                    else:
                        return jsonify({'error': 'Erreur lors du téléchargement de la photo de profil'}), 500
                except ValueError as e:
                    return jsonify({'error': str(e)}), 400
        # Si aucun fichier n'est fourni mais que l'utilisateur demande la suppression explicite
        elif data_source.get('delete_profile_picture') == 'true':
            profile_picture_url_to_set = None

        # Mise à jour de la bannière si un nouveau fichier est fourni
        if 'banner_image' in request.files:
            banner_file = request.files['banner_image']
            validated_file, error_msg = validate_image_file(banner_file, user_subscription, 'bannière')
            if error_msg:
                return jsonify({'error': error_msg}), 400
            if validated_file:
                try:
                    url, file_type = upload_file(validated_file)
                    if url:
                        banner_image_url_to_set = url
                    else:
                        return jsonify({'error': 'Erreur lors du téléchargement de la bannière'}), 500
                except ValueError as e:
                    return jsonify({'error': str(e)}), 400
        elif data_source.get('delete_banner_image') == 'true':
            banner_image_url_to_set = None

    # --- Cas 2 : requête JSON classique ---
    elif request.is_json:
        data_source = request.get_json()
        if not data_source:
            return jsonify({'error': 'Aucune donnée fournie'}), 400
    else:
        return jsonify({'error': 'Type de contenu non supporté'}), 400

    # --- Mise à jour des champs textuels, uniquement s'ils sont présents dans la requête ---
    if data_source:
        if 'first_name' in data_source:
            user_to_update.first_name = data_source['first_name']
        if 'last_name' in data_source:
            user_to_update.last_name = data_source['last_name']
        if 'pseudo' in data_source:
            new_pseudo = data_source['pseudo'].strip()
            # On ne revalide/ne vérifie l'unicité que si le pseudo a réellement changé
            if new_pseudo != user_to_update.pseudo:
                if pseudo_error := validate_pseudo(new_pseudo):
                    return jsonify({'error': pseudo_error}), 400
                if User.query.filter_by(pseudo=new_pseudo).first():
                    return jsonify({'error': 'Ce pseudo est déjà utilisé'}), 400
                user_to_update.pseudo = new_pseudo
        if 'biography' in data_source:
            user_to_update.biography = data_source['biography']
        if 'isPublic' in data_source:
            is_public = data_source['isPublic']
            # isPublic peut arriver soit en string ('true'/'false') soit en booléen selon la source
            if isinstance(is_public, str):
                user_to_update.private = not (is_public.lower() == 'true')
            else:
                user_to_update.private = not bool(is_public)

    # Application des nouvelles URLs d'images (modifiées ou inchangées)
    user_to_update.profile_picture = profile_picture_url_to_set
    user_to_update.banner = banner_image_url_to_set

    db.session.commit()

    return jsonify({
        'message': 'Utilisateur mis à jour avec succès',
        'user': {
            'id': user_to_update.id,
            'first_name': user_to_update.first_name,
            'last_name': user_to_update.last_name,
            'pseudo': user_to_update.pseudo,
            'profile_picture': user_to_update.profile_picture,
            'banner': user_to_update.banner,
            'biography': user_to_update.biography,
            'private': user_to_update.private,
            'subscription': user_to_update.subscription
        }
    }), 200


# ============================================================
# Route : suppression complète d'un utilisateur et de toutes ses données liées
# (cascade manuelle car les relations ne sont apparemment pas en ON DELETE CASCADE)
# ============================================================
@auth_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user_to_delete = User.query.get(user_id)
        if not user_to_delete:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # 1. Annuler les abonnements Stripe (paiement) avant de supprimer les enregistrements locaux
        from models.subscription import Subscription
        subscriptions = Subscription.query.filter_by(user_id=user_id).all()
        for subscription in subscriptions:
            if subscription.stripe_subscription_id:
                try:
                    import stripe
                    import os
                    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
                    stripe.Subscription.cancel(subscription.stripe_subscription_id)
                except Exception as stripe_error:
                    # On log l'erreur Stripe mais on continue la suppression locale
                    print(f"Erreur lors de l'annulation de l'abonnement Stripe: {stripe_error}")

            db.session.delete(subscription)

        # 2. Supprimer les likes de l'utilisateur
        from models.like import Like
        likes = Like.query.filter_by(user_id=user_id).all()
        for like in likes:
            db.session.delete(like)

        # 3. Supprimer les relations de suivi (en tant que follower ET en tant que suivi)
        from models.follow import Follow
        follows_as_follower = Follow.query.filter_by(follower_id=user_id).all()
        for follow in follows_as_follower:
            db.session.delete(follow)

        follows_as_followed = Follow.query.filter_by(followed_id=user_id).all()
        for follow in follows_as_followed:
            db.session.delete(follow)

        # 4. Supprimer les favoris
        from models.favorite import Favorite
        favorites = Favorite.query.filter_by(user_id=user_id).all()
        for favorite in favorites:
            db.session.delete(favorite)

        # 5. Supprimer les notifications
        from models.notification import Notification
        notifications = Notification.query.filter_by(user_id=user_id).all()
        for notification in notifications:
            db.session.delete(notification)

        # 6. Supprimer les signalements (faits par l'utilisateur ET ceux le concernant)
        from models.signalement import Signalement
        signalements_by_user = Signalement.query.filter_by(user_id=user_id).all()
        for signalement in signalements_by_user:
            db.session.delete(signalement)

        signalements_against_user = Signalement.query.filter_by(reported_user_id=user_id).all()
        for signalement in signalements_against_user:
            db.session.delete(signalement)

        # 7. Supprimer les messages de chat envoyés par l'utilisateur
        from models.chat import Chat
        chats = Chat.query.filter_by(sender_id=user_id).all()
        for chat in chats:
            db.session.delete(chat)

        # 8. Supprimer les réponses (replies) de l'utilisateur
        from models.reply import Reply
        replies = Reply.query.filter_by(user_id=user_id).all()
        for reply in replies:
            db.session.delete(reply)

        # 9. Supprimer les commentaires de l'utilisateur (et leurs réponses associées)
        from models.comment import Comment
        comments = Comment.query.filter_by(user_id=user_id).all()
        for comment in comments:
            # Supprimer d'abord les réponses aux commentaires pour éviter les contraintes de clé étrangère
            comment_replies = Reply.query.filter_by(comment_id=comment.id).all()
            for reply in comment_replies:
                db.session.delete(reply)
            db.session.delete(comment)

        # 10. Supprimer les posts de l'utilisateur et toutes leurs dépendances
        from models.post import Post
        from models.post_media import PostMedia
        posts = Post.query.filter_by(user_id=user_id).all()
        for post in posts:
            # Supprimer les médias du post
            post_media = PostMedia.query.filter_by(post_id=post.id).all()
            for media in post_media:
                db.session.delete(media)

            # Supprimer les likes du post
            post_likes = Like.query.filter_by(post_id=post.id).all()
            for like in post_likes:
                db.session.delete(like)

            # Supprimer les commentaires du post (et leurs réponses)
            post_comments = Comment.query.filter_by(post_id=post.id).all()
            for comment in post_comments:
                comment_replies = Reply.query.filter_by(comment_id=comment.id).all()
                for reply in comment_replies:
                    db.session.delete(reply)
                db.session.delete(comment)

            # Supprimer les favoris pointant vers ce post
            post_favorites = Favorite.query.filter_by(post_id=post.id).all()
            for favorite in post_favorites:
                db.session.delete(favorite)

            # Supprimer les signalements pointant vers ce post
            post_signalements = Signalement.query.filter_by(post_id=post.id).all()
            for signalement in post_signalements:
                db.session.delete(signalement)

            db.session.delete(post)

        # 11. Supprimer les sondages (polls) créés par l'utilisateur et leurs votes
        from models.poll import Poll
        from models.pollvote import PollVote
        polls = Poll.query.filter_by(user_id=user_id).all()
        for poll in polls:
            # Supprimer les votes du sondage
            poll_votes = PollVote.query.filter_by(poll_id=poll.id).all()
            for vote in poll_votes:
                db.session.delete(vote)
            db.session.delete(poll)

        # Supprimer également les votes que cet utilisateur a faits sur les sondages d'autres personnes
        user_votes = PollVote.query.filter_by(user_id=user_id).all()
        for vote in user_votes:
            db.session.delete(vote)

        # 12. Enfin, supprimer l'utilisateur lui-même une fois toutes ses données liées nettoyées
        db.session.delete(user_to_delete)
        db.session.commit()

        return jsonify({'message': 'Utilisateur et toutes ses données supprimés avec succès'}), 200

    except Exception as e:
        # En cas d'erreur à n'importe quelle étape, on annule toute la transaction
        db.session.rollback()
        print(f"Erreur lors de la suppression de l'utilisateur: {e}")
        return jsonify({'error': f'Erreur lors de la suppression: {str(e)}'}), 500


# ============================================================
# Route : demande de réinitialisation de mot de passe (envoi d'email avec lien/token)
# ============================================================
@auth_bp.route('/api/request-password-reset', methods=['POST'])
def request_password_reset():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'Email requis'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        # Sécurité : on ne révèle pas si l'email existe ou non en base
        # (évite l'énumération de comptes existants)
        return jsonify({'message': "Si un compte avec cet email existe, un lien de réinitialisation a été envoyé."}), 200

    # Les comptes créés via OAuth n'ont pas de mot de passe, donc pas de réinitialisation possible
    if user.password is None:
        return jsonify({'error': 'Ce compte a été créé via un fournisseur externe (Google/GitHub). La réinitialisation de mot de passe n\'est pas applicable.'}), 400

    # Génère un token JWT spécifique à la réinitialisation, valide 15 minutes
    reset_token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(minutes=15),
        additional_claims={'reset_password': True}
    )

    # Construit l'URL de réinitialisation envoyée par email (token encodé pour l'URL)
    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={quote(reset_token)}"

    msg = Message(
        subject="Réinitialisation de votre mot de passe Minouverse",
        recipients=[user.email],
        body=f"Bonjour {user.first_name or user.pseudo},\n\n"
             f"Pour réinitialiser votre mot de passe, veuillez cliquer sur le lien suivant :\n{reset_url}\n\n"
             f"Ce lien expirera dans 15 minutes.\n\n"
             f"Si vous n'avez pas demandé cette réinitialisation, veuillez ignorer cet email.\n\n"
             f"L'équipe Minouverse"
    )
    try:
        # Récupère l'extension Flask-Mail initialisée sur l'application
        mail_ext = current_app.extensions.get('mail')
        if not mail_ext:
            current_app.logger.error("Flask-Mail extension not initialized.")
            return jsonify({'error': "Erreur de configuration du service d'email."}), 500
        mail_ext.send(msg)
        return jsonify({'message': 'Un lien de réinitialisation a été envoyé à votre adresse email.'}), 200
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'envoi de l'email de réinitialisation : {e}")
        return jsonify({'error': "Erreur lors de l'envoi de l'email. Veuillez réessayer plus tard."}), 500


# ============================================================
# Route : réinitialisation effective du mot de passe via le token reçu par email
# ============================================================
@auth_bp.route('/api/reset-password', methods=['POST'])
def reset_password_with_token():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400

    token = data.get('token')
    new_password = data.get('new_password', '').strip()

    if not token or not new_password:
        return jsonify({'error': 'Token et nouveau mot de passe requis'}), 400

    # Le nouveau mot de passe doit respecter la même politique de sécurité qu'à l'inscription
    if err := validate_password(new_password):
        return jsonify({'error': err}), 400

    try:
        # Décodage et vérification de la signature/expiration du token JWT
        decoded_token = decode_token(token)
        # Vérifie que le token a bien été émis pour une réinitialisation de mot de passe
        # (et pas un simple token d'authentification réutilisé)
        if not decoded_token.get('reset_password'):
            return jsonify({'error': 'Token invalide ou non destiné à la réinitialisation du mot de passe'}), 401

        user_id = decoded_token['sub']
        user = User.query.get(user_id)

        if not user:
            return jsonify({'error': 'Utilisateur introuvable ou token invalide'}), 404

        # Mise à jour du mot de passe avec un nouveau hash bcrypt
        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()
        return jsonify({'message': 'Mot de passe mis à jour avec succès'}), 200

    except Exception as e:
        # Capture les erreurs de décodage JWT (token expiré, signature invalide, etc.)
        current_app.logger.error(f"Erreur lors de la réinitialisation du mot de passe : {e}")
        return jsonify({'error': 'Token invalide, expiré ou une erreur est survenue'}), 401


# ============================================================
# Route : récupération du profil public d'un utilisateur par son pseudo
# Inclut ses statistiques (followers/following), ses posts et médias associés
# ============================================================
@auth_bp.route('/api/users/profile/<string:pseudo>', methods=['GET'])
def get_user_by_pseudo(pseudo):
    user = User.query.filter_by(pseudo=pseudo).first()

    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    # Calcul du nombre de followers et d'abonnements
    from models.follow import Follow
    followers_count = Follow.query.filter_by(followed_id=user.id).count()
    following_count = Follow.query.filter_by(follower_id=user.id).count()

    from models.post import Post
    from models.post_media import PostMedia

    # Récupère tous les posts de l'utilisateur, du plus récent au plus ancien
    user_posts = Post.query.filter_by(user_id=user.id).order_by(Post.published_at.desc()).all()
    posts = []
    media = []  # Liste à plat de tous les médias, toutes publications confondues

    for post in user_posts:
        post_media_list = PostMedia.query.filter_by(post_id=post.id).all()
        post_media = []

        for media_item in post_media_list:
            media_data = {
                'id': media_item.id,
                'url': media_item.media_url,
                'type': media_item.media_type,
                'created_at': media_item.created_at.isoformat() if media_item.created_at else None
            }
            post_media.append(media_data)
            # On ajoute aussi le média à la liste globale "media" du profil
            media.append(media_data)

        post_data = {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'published_at': post.published_at.isoformat() if post.published_at else None,
            'media': post_media,
            'category_id': post.category_id,
            'user_id': post.user_id
        }
        posts.append(post_data)

    # TODO: les likes ne sont actuellement pas récupérés (liste vide en dur)
    likes = []

    result = {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'roles': user.roles,
        'profile_picture': user.profile_picture,
        'pseudo': user.pseudo,
        'private': user.private,
        'biography': user.biography,
        'banner': user.banner,
        'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None,
        'updated_at': user.updated_at.isoformat() if hasattr(user, 'updated_at') and user.updated_at else None,
        'followers_count': followers_count,
        'following_count': following_count,
        'posts': posts,
        'media': media,
        'likes': likes,
        'subscription': user.subscription_level
    }

    return jsonify(result)


# ============================================================
# Route : récupération d'un utilisateur par son ID (version allégée, sans relations)
# ============================================================
@auth_bp.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Récupérer un utilisateur par son ID"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        return jsonify({
            'id': user.id,
            'pseudo': user.pseudo,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'profile_picture': user.profile_picture,
            'biography': user.biography,
            'private': user.private,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }), 200
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : récupération de tous les commentaires ET réponses d'un utilisateur,
# triés par date, avec le post d'origine pour chaque élément
# ============================================================
@auth_bp.route('/api/users/<int:user_id>/comments-replies', methods=['GET'])
def get_user_comments_and_replies(user_id):
    """Récupérer tous les commentaires et réponses d'un utilisateur"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        from models.comment import Comment
        from models.reply import Reply
        from models.post import Post
        from models.comment_media import CommentMedia
        from models.reply_media import ReplyMedia
        from models.comment_like import CommentLike
        from models.reply_like import ReplyLike

        # Liste finale combinant commentaires ET réponses (mêlangés puis triés)
        comments_and_replies = []

        # --- Traitement des commentaires de l'utilisateur ---
        comments = Comment.query.filter_by(user_id=user_id).order_by(Comment.created_at.desc()).all()

        for comment in comments:
            # Récupère le post d'origine sur lequel porte le commentaire
            original_post = Post.query.get(comment.post_id)
            original_post_data = None

            if original_post:
                post_user = User.query.get(original_post.user_id)
                original_post_data = {
                    'id': original_post.id,
                    'title': original_post.title,
                    'content': original_post.content,
                    'user': {
                        'id': post_user.id if post_user else None,
                        'pseudo': post_user.pseudo if post_user else None,
                        'first_name': post_user.first_name if post_user else None,
                        'last_name': post_user.last_name if post_user else None,
                        'profile_picture': post_user.profile_picture if post_user else None
                    } if post_user else None
                }

            comment_media = CommentMedia.query.filter_by(comment_id=comment.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type
            } for m in comment_media]

            likes_count = CommentLike.query.filter_by(comment_id=comment.id).count()
            replies_count = Reply.query.filter_by(comment_id=comment.id).count()

            comments_and_replies.append({
                'id': comment.id,
                'type': 'comment',
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'media': media,
                'likes_count': likes_count,
                'replies_count': replies_count,
                'originalPost': original_post_data
            })

        # --- Traitement des réponses (replies) de l'utilisateur ---
        # Une réponse peut être attachée soit à un commentaire (comment_id),
        # soit à une autre réponse (replies_id) -> structure en arbre/imbriquée
        replies = Reply.query.filter_by(user_id=user_id).order_by(Reply.created_at.desc()).all()

        for reply in replies:
            original_post_data = None

            # Cas A : la réponse répond directement à un commentaire
            if reply.comment_id:
                original_comment = Comment.query.get(reply.comment_id)
                if original_comment:
                    original_post = Post.query.get(original_comment.post_id)
                    if original_post:
                        post_user = User.query.get(original_post.user_id)
                        original_post_data = {
                            'id': original_post.id,
                            'title': original_post.title,
                            'content': original_post.content,
                            'user': {
                                'id': post_user.id if post_user else None,
                                'pseudo': post_user.pseudo if post_user else None,
                                'first_name': post_user.first_name if post_user else None,
                                'last_name': post_user.last_name if post_user else None,
                                'profile_picture': post_user.profile_picture if post_user else None
                            } if post_user else None
                        }
            # Cas B : la réponse répond à une autre réponse -> on remonte récursivement
            # la chaîne de réponses jusqu'à trouver le commentaire racine, puis le post
            elif reply.replies_id:
                def find_original_post(reply_obj):
                    """Remonte récursivement la chaîne de réponses jusqu'au post d'origine."""
                    if reply_obj.comment_id:
                        comment = Comment.query.get(reply_obj.comment_id)
                        return Post.query.get(comment.post_id) if comment else None
                    elif reply_obj.replies_id:
                        parent_reply = Reply.query.get(reply_obj.replies_id)
                        return find_original_post(parent_reply) if parent_reply else None
                    return None

                original_post = find_original_post(reply)
                if original_post:
                    post_user = User.query.get(original_post.user_id)
                    original_post_data = {
                        'id': original_post.id,
                        'title': original_post.title,
                        'content': original_post.content,
                        'user': {
                            'id': post_user.id if post_user else None,
                            'pseudo': post_user.pseudo if post_user else None,
                            'first_name': post_user.first_name if post_user else None,
                            'last_name': post_user.last_name if post_user else None,
                            'profile_picture': post_user.profile_picture if post_user else None
                        } if post_user else None
                    }

            reply_media = ReplyMedia.query.filter_by(replies_id=reply.id).all()
            media = [{
                'id': m.id,
                'url': m.media_url,
                'type': m.media_type
            } for m in reply_media]

            likes_count = ReplyLike.query.filter_by(replies_id=reply.id).count()
            sub_replies_count = Reply.query.filter_by(replies_id=reply.id).count()

            comments_and_replies.append({
                'id': reply.id,
                'type': 'reply',
                'content': reply.content,
                'created_at': reply.created_at.isoformat(),
                'media': media,
                'likes_count': likes_count,
                'replies_count': sub_replies_count,
                'originalPost': original_post_data
            })

        # Fusionne commentaires et réponses puis trie par date décroissante (plus récent en premier)
        comments_and_replies.sort(key=lambda x: x['created_at'], reverse=True)

        return jsonify({'commentsAndReplies': comments_and_replies}), 200

    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : statut de bannissement d'un utilisateur
# Lève automatiquement le ban temporaire si la date d'expiration est dépassée
# ============================================================
@auth_bp.route('/api/users/<int:user_id>/ban-status', methods=['GET'])
def get_user_ban_status(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # Vérifier si le ban temporaire est expiré, et le lever automatiquement si c'est le cas
        if user.ban_until and user.ban_until <= datetime.utcnow():
            user.is_banned = False
            user.ban_until = None
            db.session.commit()

        return jsonify({
            'is_banned': user.is_banned,
            'ban_until': user.ban_until.isoformat() if user.ban_until else None,
            'warn_count': user.warn_count or 0
        })

    except Exception as e:
        return jsonify({'error': f'Erreur lors de la vérification du statut: {str(e)}'}), 500