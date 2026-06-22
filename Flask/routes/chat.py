from flask import Blueprint, request, jsonify
from models import db
from models.user import User
from models.chat import Chat
from datetime import datetime, timedelta, timezone
import traceback

chats_bp = Blueprint('chats_api', __name__)


# ============================================================
# Route : création d'un message de chat
# ============================================================
@chats_bp.route('/api/chats', methods=['POST'])
def create_chat():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Aucune donnée fournie'}), 400

        conversation_id = data.get('conversation_id')
        sender_id = data.get('sender_id')
        content = data.get('content')
        reply_to_id = data.get('reply_to_id')

        if not conversation_id or not sender_id or not content:
            return jsonify({'error': 'conversation_id, sender_id et content sont requis'}), 400

        # Vérifie que l'expéditeur existe bien en base
        sender = User.query.get(sender_id)
        if not sender:
            return jsonify({'error': 'Utilisateur expéditeur non trouvé'}), 404

        new_chat = Chat(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            reply_to_id=reply_to_id
        )

        # Horodatage en UTC au moment de l'envoi
        new_chat.send_at = datetime.now(timezone.utc)

        db.session.add(new_chat)
        db.session.commit()

        return jsonify({
            'message': 'Message créé avec succès',
            'chat_id': new_chat.id,
            'chat': new_chat.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la création du chat: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : liste de TOUS les messages de chat (toutes conversations confondues)
#  Pas de pagination ni de filtre : à utiliser avec précaution si gros volume
# ============================================================
@chats_bp.route('/api/chats', methods=['GET'])
def get_chats():
    try:
        chats = Chat.query.order_by(Chat.send_at.asc()).all()
        chats_list = [chat.to_dict() for chat in chats]

        return jsonify({
            'chats': chats_list,
            'total': len(chats_list)
        }), 200

    except Exception as e:
        print(f"Erreur lors de la récupération des chats: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : récupération d'un message unique par son ID
# ============================================================
@chats_bp.route('/api/chats/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    try:
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({'error': 'Message non trouvé'}), 404

        return jsonify(chat.to_dict()), 200

    except Exception as e:
        print(f"Erreur lors de la récupération du chat {chat_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : mise à jour d'un message (édition de contenu ou de la réponse ciblée)
# ============================================================
@chats_bp.route('/api/chats/<int:chat_id>', methods=['PUT'])
def update_chat(chat_id):
    try:
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({'error': 'Message non trouvé'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Aucune donnée fournie'}), 400

        # Mise à jour partielle : seuls les champs présents dans la requête sont modifiés
        if 'content' in data:
            chat.content = data['content']
        if 'reply_to_id' in data:
            chat.reply_to_id = data['reply_to_id']

        db.session.commit()

        return jsonify({
            'message': 'Message mis à jour avec succès',
            'chat': chat.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la mise à jour du chat {chat_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : suppression d'un message
#  Ne supprime pas les éventuelles réponses (replies) pointant vers ce message
# ============================================================
@chats_bp.route('/api/chats/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    try:
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({'error': 'Message non trouvé'}), 404

        db.session.delete(chat)
        db.session.commit()

        return jsonify({'message': 'Message supprimé avec succès'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la suppression du chat {chat_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : liste des réponses directes à un message donné
# ============================================================
@chats_bp.route('/api/chats/<int:chat_id>/replies', methods=['GET'])
def get_replies(chat_id):
    try:
        parent_chat = Chat.query.get(chat_id)
        if not parent_chat:
            return jsonify({'error': 'Message parent non trouvé'}), 404

        # Récupère tous les messages dont reply_to_id pointe vers ce message
        replies = Chat.query.filter_by(reply_to_id=chat_id).order_by(Chat.send_at.asc()).all()
        replies_list = [reply.to_dict() for reply in replies]

        return jsonify({
            'parent_chat_id': chat_id,
            'replies': replies_list,
            'total_replies': len(replies_list)
        }), 200

    except Exception as e:
        print(f"Erreur lors de la récupération des réponses pour le chat {chat_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : informations sur l'expéditeur d'un message donné
# ============================================================
@chats_bp.route('/api/chats/<int:chat_id>/sender', methods=['GET'])
def get_chat_sender(chat_id):
    try:
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({'error': 'Message non trouvé'}), 404

        sender = User.query.get(chat.sender_id)
        if not sender:
            return jsonify({'error': 'Expéditeur non trouvé'}), 404

        return jsonify({
            'id': sender.id,
            'username': sender.pseudo,
            'email': sender.email,
            # getattr() avec valeur par défaut pour éviter une erreur si l'attribut n'existe pas
            'first_name': getattr(sender, 'first_name', None),
            'last_name': getattr(sender, 'last_name', None),
            'profile_picture': getattr(sender, 'profile_picture', None),
            'subscription': getattr(sender, 'subscription', 'free')
        }), 200

    except Exception as e:
        print(f"Erreur lors de la récupération de l'expéditeur pour le chat {chat_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : tous les messages d'une conversation (par conversation_id),
# avec la liste des participants ayant envoyé au moins un message
# ============================================================
@chats_bp.route('/api/conversations/<int:conversation_id>/chats', methods=['GET'])
def get_conversation_chats(conversation_id):
    try:
        chats = Chat.query.filter_by(conversation_id=conversation_id).order_by(Chat.send_at.asc()).all()
        chats_list = [chat.to_dict() for chat in chats]

        # set() pour dédupliquer les IDs des expéditeurs (un même utilisateur peut envoyer plusieurs messages)
        participants_ids = set(chat.sender_id for chat in chats)
        participants = []

        for user_id in participants_ids:
            user = User.query.get(user_id)
            if user:
                participants.append({
                    'id': user.id,
                    'username': user.pseudo,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'profile_picture': user.profile_picture,
                    'subscription': user.subscription
                })

        return jsonify({
            'conversation_id': conversation_id,
            'chats': chats_list,
            'total_messages': len(chats_list),
            'participants': participants
        }), 200

    except Exception as e:
        print(f"Erreur lors de la récupération des chats de la conversation {conversation_id}: {str(e)}")
        return jsonify({'error': f'Erreur interne du serveur: {str(e)}'}), 500


# ============================================================
# Route : liste de toutes les conversations d'un utilisateur, avec dernier message
# et infos sur l'autre participant.
#
#  PARTIE FRAGILE : le conversation_id est un entier "encodé" qui concatène les
# deux IDs des participants (ex: user1=12, user2=345 -> conversation_id=12345 ou
# 120345 selon le padding). La fonction extract_participants_from_conversation_id
# tente de "décoder" cet entier pour retrouver les deux IDs d'origine, en testant
# plusieurs heuristiques (présence d'un zéro, suffixe à 3 chiffres, brute-force des
# positions de split). C'est une solution risquée car ambiguë : plusieurs paires
# d'IDs peuvent produire le même entier concaténé. Une solution plus robuste serait
# de stocker explicitement les deux participant_id en base plutôt que de les encoder
# dans un seul entier.
# ============================================================
@chats_bp.route('/api/chats/conversations/<int:user_id>', methods=['GET'])
def get_user_conversations(user_id):
    try:
        print(f"=== Getting conversations for user_id: {user_id} ===")

        user = User.query.get(user_id)
        if not user:
            print(f" User {user_id} not found")
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        print(f" User found: {user.email}")

        def extract_participants_from_conversation_id(conv_id):
            """
            Extrait les IDs des participants à partir de l'ID de conversation.
            L'ID de conversation est construit en concaténant les deux IDs utilisateurs
            (voir create_private_message où conversation_id = f"{id1}{id2:03d}").
            Cette fonction essaie de "deviner" où couper la chaîne pour retrouver les
            deux IDs d'origine, via plusieurs heuristiques successives.
            """
            conv_str = str(conv_id)
            print(f" Analyzing conversation ID: {conv_str}")

            # Heuristique 1 : si un '0' est présent au milieu de la chaîne (hors premier/dernier caractère),
            # on suppose que c'est le padding utilisé lors de la construction de l'ID, et on coupe juste après.
            if '0' in conv_str[1:-1]:
                zero_pos = conv_str.index('0', 1)
                user1_id = int(conv_str[:zero_pos])
                user2_id = int(conv_str[zero_pos+1:])
                print(f"  → Split at zero: {user1_id}, {user2_id}")
                return [user1_id, user2_id]

            # Heuristique 2 : on suppose que le deuxième ID a été paddé sur 3 chiffres
            # (cohérent avec le format `{sorted_ids[1]:03d}` utilisé à la création)
            if len(conv_str) >= 4:
                user1_id = int(conv_str[:-3])
                user2_id = int(conv_str[-3:])
                if user1_id > 0 and user2_id > 0:
                    print(f"  → Split with 3-digit suffix: {user1_id}, {user2_id}")
                    return [user1_id, user2_id]

            # Heuristique 3 (fallback) : brute-force de toutes les positions de coupe possibles,
            # on retourne la première qui donne deux entiers positifs valides
            for split_pos in range(1, len(conv_str)):
                try:
                    user1_id = int(conv_str[:split_pos])
                    user2_id = int(conv_str[split_pos:])
                    if user1_id > 0 and user2_id > 0:
                        print(f"  → Split at position {split_pos}: {user1_id}, {user2_id}")
                        return [user1_id, user2_id]
                except ValueError:
                    continue

            print(f"  →  Could not extract participants from {conv_str}")
            return []

        # Récupère tous les conversation_id distincts présents en base
        all_conversations = db.session.query(Chat.conversation_id).distinct().all()
        print(f" Total conversations in database: {len(all_conversations)}")

        user_conversations = []
        conversation_ids = set()

        # Pour chaque conversation_id existant, on tente de décoder les participants
        # et on garde celles où l'utilisateur courant apparaît
        for (conv_id,) in all_conversations:
            participants = extract_participants_from_conversation_id(conv_id)

            if user_id in participants:
                conversation_ids.add(conv_id)
                print(f"   User {user_id} participates in conversation {conv_id}")

        # Sécurité supplémentaire : on ajoute aussi directement toutes les conversations
        # où l'utilisateur est explicitement l'expéditeur (évite de rater une conversation
        # si le décodage par heuristique échoue)
        sent_conversations = db.session.query(Chat.conversation_id).filter_by(sender_id=user_id).distinct().all()
        for conv in sent_conversations:
            conversation_ids.add(conv[0])

        print(f" Final conversation_ids for user {user_id}: {conversation_ids}")

        for conv_id in conversation_ids:
            try:
                # Récupère tous les messages de cette conversation, du plus récent au plus ancien
                conversation_chats = Chat.query.filter_by(conversation_id=conv_id).order_by(Chat.send_at.desc()).all()

                if not conversation_chats:
                    continue

                # Identifie l'autre participant de la conversation (celui qui n'est pas user_id)
                participants = extract_participants_from_conversation_id(conv_id)
                other_user_id = participants[1] if participants[0] == user_id else participants[0]

                if not other_user_id:
                    continue

                other_user = User.query.get(other_user_id)
                if not other_user:
                    continue

                other_user_details = {
                    'id': other_user.id,
                    'username': other_user.pseudo,
                    'email': other_user.email,
                    'first_name': other_user.first_name,
                    'last_name': other_user.last_name,
                    'profile_picture': other_user.profile_picture,
                    'subscription': other_user.subscription
                }

                print(f"   Other user details: {other_user_details}")  # Debug log

                # Le premier élément de la liste (triée par date desc) est le dernier message envoyé
                last_message_details = None
                if conversation_chats:
                    last_chat = conversation_chats[0]
                    last_message_details = {
                        'id': last_chat.id,
                        'content': last_chat.content,
                        'sender_id': last_chat.sender_id,
                        'send_at': last_chat.send_at.isoformat().replace('+00:00', 'Z') if last_chat.send_at else None
                    }

                # TODO: le compteur de messages non lus n'est pas réellement calculé (toujours à 0)
                unread_count = 0

                conversation_data = {
                    'conversation_id': conv_id,
                    'other_user': other_user_details,
                    'last_message': last_message_details,
                    'unread_count': unread_count,
                    'total_messages': len(conversation_chats)
                }

                user_conversations.append(conversation_data)
                print(f"   Added conversation {conv_id} with {other_user.email} (subscription: {other_user.subscription})")

            except Exception as e:
                # On ignore les conversations problématiques individuellement,
                # plutôt que de faire échouer toute la requête
                print(f"   Error processing conversation {conv_id}: {str(e)}")
                continue

        # Trie les conversations par date du dernier message (plus récent en premier)
        # Les conversations sans dernier message sont placées en dernier (date "epoch")
        user_conversations.sort(
            key=lambda x: x['last_message']['send_at'] if x.get('last_message') and x['last_message'].get('send_at') else '1970-01-01T00:00:00Z',
            reverse=True
        )

        print(f" Returning {len(user_conversations)} conversations for user {user_id}")

        for conv in user_conversations:
            print(f"  - Conv {conv['conversation_id']}: {conv['other_user']['email']} (subscription: {conv['other_user'].get('subscription', 'NOT_SET')}) ({conv['total_messages']} messages)")

        return jsonify({
            'user_id': user_id,
            'conversations': user_conversations,
            'total_conversations': len(user_conversations)
        }), 200

    except Exception as e:
        print(f" ERROR in get_user_conversations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Erreur interne: {str(e)}',
            'user_id': user_id,
            'conversations': [],
            'total_conversations': 0
        }), 500


# ============================================================
# Route : messages d'une conversation, avec filtre optionnel "depuis un timestamp"
# (utile pour le polling côté client : ne récupérer que les nouveaux messages)
# ============================================================
@chats_bp.route('/api/chats/conversation/<int:conversation_id>', methods=['GET'])
def get_conversation_messages(conversation_id):
    since_timestamp = request.args.get('since')

    query = Chat.query.filter_by(conversation_id=conversation_id)

    # Si un timestamp "since" est fourni en query param, on ne garde que les messages plus récents
    if since_timestamp:
        query = query.filter(Chat.send_at > since_timestamp)

    messages = query.order_by(Chat.send_at.asc()).all()

    return jsonify({
        'messages': [message.to_dict() for message in messages]
    })


# ============================================================
# Route : création d'un message privé entre deux utilisateurs (sender -> recipient)
#
# Construit elle-même le conversation_id en concatenant les deux IDs (triés pour que
# la conversation soit la même quel que soit l'expéditeur), avec padding à 3 chiffres
# sur le second ID. Voir la remarque dans extract_participants_from_conversation_id
# ci-dessus sur la fragilité de cet encodage.
#
# Contient aussi une protection anti-doublon (ex: double-clic, retry réseau) basée
# sur un message identique envoyé dans les 5 dernières secondes.
# ============================================================
@chats_bp.route('/api/chats/private', methods=['POST'])
def create_private_message():
    try:
        data = request.get_json()
        print(f" HTTP Message request: {data}")

        sender_id = data.get('sender_id')
        recipient_id = data.get('recipient_id')
        content = data.get('content')

        if not all([sender_id, recipient_id, content]):
            return jsonify({'error': 'Données manquantes'}), 400

        # Vérifier que les utilisateurs existent
        sender = User.query.get(sender_id)
        recipient = User.query.get(recipient_id)

        if not sender or not recipient:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # Trie les IDs pour que la conversation entre A et B ait toujours le même
        # conversation_id, peu importe qui envoie le message en premier
        sorted_ids = sorted([sender_id, recipient_id])
        # Le second ID est paddé sur 3 chiffres avant d'être concaténé au premier
        conversation_id = int(f"{sorted_ids[0]}{sorted_ids[1]:03d}")

        # VÉRIFICATION ANTI-DOUBLON : Regarder s'il n'y a pas déjà un message identique récent
        # (protège contre les doubles soumissions, ex: double-clic ou retry réseau côté client)
        recent_threshold = datetime.now(timezone.utc) - timedelta(seconds=5)
        existing_message = Chat.query.filter(
            Chat.conversation_id == conversation_id,
            Chat.sender_id == sender_id,
            Chat.content == content,
            Chat.send_at >= recent_threshold
        ).first()

        if existing_message:
            print(f" HTTP: Duplicate message detected, returning existing message: {existing_message.id}")

            # On renvoie le message existant plutôt que d'en créer un nouveau,
            # avec un code 200 (au lieu de 201) pour indiquer qu'aucune création n'a eu lieu
            response_data = {
                'success': True,
                'message': 'Message déjà existant',
                'chat': {
                    'id': existing_message.id,
                    'conversation_id': conversation_id,
                    'sender_id': sender_id,
                    'content': content,
                    'send_at': existing_message.send_at.isoformat().replace('+00:00', 'Z'),
                    'reply_to_id': None
                }
            }

            return jsonify(response_data), 200

        new_chat = Chat(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content
        )

        new_chat.send_at = datetime.now(timezone.utc)

        db.session.add(new_chat)
        db.session.commit()

        print(f" HTTP: NEW message saved with ID: {new_chat.id}")

        response_data = {
            'success': True,
            'message': 'Message envoyé avec succès',
            'chat': {
                'id': new_chat.id,
                'conversation_id': conversation_id,
                'sender_id': sender_id,
                'content': content,
                'send_at': new_chat.send_at.isoformat().replace('+00:00', 'Z'),
                'reply_to_id': None
            }
        }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        print(f" Error in HTTP message creation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erreur lors de la création du message: {str(e)}'}), 500


# ============================================================
# Route : polling simplifié des nouveaux messages reçus par un utilisateur
# depuis un timestamp donné (paramètre "since" en query string)
# ============================================================
@chats_bp.route('/api/chats/new/<int:user_id>')
def get_new_messages_simple(user_id):
    """
    Récupère les nouveaux messages pour un utilisateur depuis un timestamp donné
    """
    try:
        since_param = request.args.get('since')

        if since_param:
            try:
                since_timestamp = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            except:
                # Si le timestamp fourni est invalide, on retombe sur les 30 dernières secondes
                since_timestamp = datetime.utcnow() - timedelta(seconds=30)
        else:
            # Par défaut, on ne regarde que les 30 dernières secondes
            since_timestamp = datetime.utcnow() - timedelta(seconds=30)

        # Récupère les conversations où l'utilisateur a déjà envoyé un message
        user_chats = Chat.query.filter_by(sender_id=user_id).all()
        conversation_ids = set(chat.conversation_id for chat in user_chats)

        #  Heuristique fragile : on parcourt TOUS les chats de la base et on vérifie
        # si l'ID utilisateur apparaît comme sous-chaîne du conversation_id. Cela peut
        # produire des faux positifs (ex: user_id=12 correspond aussi à un conversation_id
        # contenant "12" ailleurs que comme identifiant réel d'un participant).
        all_chats = Chat.query.all()
        for chat in all_chats:
            conv_id_str = str(chat.conversation_id)
            user_id_str = str(user_id)
            if user_id_str in conv_id_str:
                conversation_ids.add(chat.conversation_id)

        # Récupère les nouveaux messages dans ces conversations, envoyés par quelqu'un d'autre
        # que l'utilisateur courant (pas la peine de notifier l'utilisateur de ses propres messages)
        new_messages = []
        for conv_id in conversation_ids:
            messages = Chat.query.filter(
                Chat.conversation_id == conv_id,
                Chat.send_at > since_timestamp,
                Chat.sender_id != user_id
            ).order_by(Chat.send_at.asc()).all()

            for message in messages:
                message_dict = message.to_dict()
                message_dict['conversation_id'] = conv_id
                new_messages.append(message_dict)

        return jsonify({
            'success': True,
            'messages': new_messages,
            'timestamp': datetime.utcnow().isoformat(),
            'count': len(new_messages)
        }), 200

    except Exception as e:
        print(f"Erreur lors de la récupération des nouveaux messages: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Route : gestion de la requête preflight CORS (OPTIONS) pour l'endpoint
# /api/chats/conversation/<id>, nécessaire pour que le navigateur autorise
# le GET correspondant depuis une origine différente
# ============================================================
@chats_bp.route('/api/chats/conversation/<int:conversation_id>', methods=['OPTIONS'])
def handle_conversation_options(conversation_id):
    """Gérer les requêtes preflight CORS"""
    return '', 200