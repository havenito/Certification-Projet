import os
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db
from models.user import User
from models.chat import Chat
import json
from datetime import datetime, timezone, timedelta

# Instance globale pour gérer les WebSockets dans toute l'app
socketio = SocketIO()

# Le dico pour garder sous le coude la correspondance entre l'ID de l'user et son SID (sa session socket active)
# Stocké en mémoire process : si l'app tourne sur plusieurs workers/instances (ex: gunicorn
# avec plusieurs processus, ou plusieurs serveurs derrière un load balancer), ce dictionnaire
# ne sera PAS partagé entre eux. Un utilisateur connecté sur le worker A ne sera pas visible
# par le worker B. Pour passer à l'échelle, il faudrait un message broker partagé (ex: Redis,
# via flask_socketio avec message_queue=...) plutôt qu'un simple dict en mémoire.
connected_users = {}


def init_socketio(app):
    """ Config de base au démarrage de Flask (CORS, logs, etc.) """
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')

    socketio.init_app(app,
                      cors_allowed_origins=[frontend_url, "http://127.0.0.1:3000", "http://localhost:8080", "null"],
                      logger=True,
                      engineio_logger=True)
    return socketio


# ============================================================
# Événement : connexion d'un nouveau client WebSocket
# ============================================================
@socketio.on('connect')
def handle_connect():
    # Un client vient de se connecter, on loggue sa session unique (sid)
    print(f'Client connecté: {request.sid}')
    emit('status', {'message': 'Connecté au serveur WebSocket'})


# ============================================================
# Événement : déconnexion d'un client (fermeture d'onglet, perte réseau, etc.)
# ============================================================
@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client déconnecté: {request.sid}')
    # Nettoyage obligatoire : si le mec part, on vire son SID de notre dictionnaire global
    # Parcours linéaire de tout le dictionnaire pour retrouver le SID : sur un grand nombre
    # d'utilisateurs connectés simultanément, ce nettoyage devient O(n) à chaque déconnexion.
    # Un mapping inverse {sid: user_id} en plus de {user_id: sid} éviterait cette recherche.
    for user_id, sid in list(connected_users.items()):
        if sid == request.sid:
            del connected_users[user_id]
            break


# ============================================================
# Événement : un utilisateur rejoint sa room personnelle (pour recevoir
# ses notifications même s'il n'est pas dans une conversation précise)
#
# Aucune vérification d'identité : n'importe quel client pourrait envoyer
# 'join_user' avec n'importe quel user_id et recevoir ainsi les notifications
# destinées à un autre utilisateur. Idéalement, user_id devrait être déduit
# d'une authentification (token/session) côté serveur, pas transmis tel quel
# par le client et accepté sans vérification.
# ============================================================
@socketio.on('join_user')
def handle_join_user(data):
    """ On met l'utilisateur dans son propre canal privé (utile pour ses notifications) """
    user_id = data.get('user_id')
    if user_id:
        connected_users[user_id] = request.sid
        join_room(f"user_{user_id}")
        emit('status', {'message': f'Rejoint la room user_{user_id}'})
        print(f'Utilisateur {user_id} a rejoint sa room')


# ============================================================
# Événement : un utilisateur ouvre une fenêtre de discussion (rejoint la room
# de la conversation pour recevoir les messages en temps réel)
#
# Même remarque que join_user : aucune vérification que cet utilisateur
# fait bien partie de cette conversation. N'importe qui connaissant un
# conversation_id pourrait potentiellement rejoindre la room et lire les
# messages échangés en temps réel.
# ============================================================
@socketio.on('join_conversation')
def handle_join_conversation(data):
    """ Quand l'utilisateur ouvre une fenêtre de tchat """
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')

    if conversation_id and user_id:
        join_room(f"conv_{conversation_id}")
        emit('status', {'message': f'Rejoint la conversation {conversation_id}'})
        print(f'Utilisateur {user_id} a rejoint la conversation {conversation_id}')


# ============================================================
# Événement : l'utilisateur ferme/quitte la fenêtre de discussion
# (quitte la room, donc ne recevra plus les messages de cette conversation
# en temps réel jusqu'à ce qu'il la rejoigne à nouveau)
# ============================================================
@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """ Quand l'utilisateur quitte une conversation """
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')

    if conversation_id and user_id:
        leave_room(f"conv_{conversation_id}")
        emit('status', {'message': f'Quitté la conversation {conversation_id}'})
        print(f'Utilisateur {user_id} a quitté la conversation {conversation_id}')


# ============================================================
# Événement : envoi d'un message de chat en temps réel
#
# C'est l'équivalent WebSocket de la route HTTP create_private_message vue dans
# chats_routes.py : même logique de génération de conversation_id (concaténation
# triée des deux IDs), même protection anti-doublon sur 5 secondes. La différence
# principale est que ce flux notifie immédiatement les autres clients connectés
# via les rooms Socket.IO, sans que le destinataire ait besoin de faire un polling
# HTTP pour voir le nouveau message.
# ============================================================
@socketio.on('send_message')
def handle_send_message(data):
    """ Le gros morceau : réception, sauvegarde et renvoi d'un message en temps réel """
    try:
        print(f"\n=== SENDING MESSAGE VIA WEBSOCKET ===")
        print(f"Received data: {data}")

        sender_id = data.get('sender_id')
        recipient_id = data.get('recipient_id')
        content = data.get('content')
        conversation_id = data.get('conversation_id')
        temp_id = data.get('tempId')  # ID temporaire généré par le front (pour l'affichage en attente de validation)

        # Sécurité de base : si on n'a pas ça, on peut rien faire
        if not all([sender_id, recipient_id, content]):
            print("Missing required data")
            emit('error', {'message': 'Données manquantes'})
            return

        sender = User.query.get(sender_id)
        recipient = User.query.get(recipient_id)

        if not sender or not recipient:
            print("User not found")
            emit('error', {'message': 'Utilisateur non trouvé'})
            return

        # Si pas de conversation_id valide (ou reçu en string), on en génère un unique basé sur les IDs des 2 users
        # (même logique de "concaténation triée" que dans create_private_message côté HTTP,
        # voir l'avertissement détaillé sur la fragilité de cet encodage dans chats_routes.py)
        if not conversation_id or isinstance(conversation_id, str):
            sorted_ids = sorted([sender_id, recipient_id])
            conversation_id = int(f"{sorted_ids[0]}{sorted_ids[1]:03d}")

        try:
            conversation_id = int(conversation_id)
        except (ValueError, TypeError):
            # Si la conversion échoue (valeur incohérente reçue du client), on retombe
            # sur la génération automatique plutôt que de planter
            sorted_ids = sorted([sender_id, recipient_id])
            conversation_id = int(f"{sorted_ids[0]}{sorted_ids[1]:03d}")

        print(f"Final conversation_id: {conversation_id}")

        # Sécurité anti-double clic / spam : on regarde si le même message a été envoyé il y a moins de 5 secondes
        recent_threshold = datetime.now(timezone.utc) - timedelta(seconds=5)
        existing_message = Chat.query.filter(
            Chat.conversation_id == conversation_id,
            Chat.sender_id == sender_id,
            Chat.content == content,
            Chat.send_at >= recent_threshold
        ).first()

        if existing_message:
            # Si c'est un doublon, on stoppe tout, on ne crée rien en BDD, mais on renvoie quand même le premier message au front
            print(f"Duplicate message detected, returning existing message: {existing_message.id}")

            message_data = {
                'id': existing_message.id,
                'conversation_id': conversation_id,
                'sender_id': sender_id,
                'content': content,
                'send_at': existing_message.send_at.isoformat().replace('+00:00', 'Z'),
                'sender_info': {
                    'id': sender.id,
                    'first_name': getattr(sender, 'first_name', ''),
                    'last_name': getattr(sender, 'last_name', ''),
                    'email': sender.email
                }
            }

            # On confirme au front que c'est ok pour rassurer l'interface de l'expéditeur
            # Note : 'message_sent' n'est émis qu'à l'expéditeur (emit() sans room cible le
            # client courant), donc ce cas de doublon ne rebroadcast pas 'new_message' aux
            # autres participants — logique, puisque le message existe déjà chez eux aussi
            emit('message_sent', {
                'success': True,
                'message_id': existing_message.id,
                'conversation_id': conversation_id,
                'timestamp': existing_message.send_at.isoformat().replace('+00:00', 'Z'),
                'tempId': temp_id,
                'message_data': message_data
            })
            return

        # Si tout est bon et pas de doublon, création classique dans la base de données
        new_chat = Chat(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            reply_to_id=None
        )

        new_chat.send_at = datetime.now(timezone.utc)

        db.session.add(new_chat)
        db.session.commit()  # On valide en BDD

        print(f"NEW message saved to DB with ID: {new_chat.id}")

        # Formatage propre de l'objet pour l'envoyer proprement en JSON aux clients
        message_data = {
            'id': new_chat.id,
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'content': content,
            'send_at': new_chat.send_at.isoformat().replace('+00:00', 'Z'),
            'sender_info': {
                'id': sender.id,
                'first_name': getattr(sender, 'first_name', ''),
                'last_name': getattr(sender, 'last_name', ''),
                'email': sender.email
            }
        }

        # 1. On arrose la room de la conversation pour que l'autre personne reçoive le message en direct (sans l'envoyer à soi-même)
        # include_self=False évite que l'expéditeur reçoive son propre message en double
        # (il a déjà sa propre copie affichée via la confirmation 'message_sent' plus bas)
        room_name = f"conv_{conversation_id}"
        print(f"Broadcasting to room: {room_name}")
        socketio.emit('new_message', message_data, room=room_name, include_self=False)

        # 2. On envoie une notification globale à l'autre utilisateur s'il est connecté mais sur une autre page du site
        # (par exemple s'il n'a pas la fenêtre de chat ouverte mais navigue ailleurs sur le site,
        # il recevra quand même une notification via sa room personnelle "user_<id>")
        user_room = f"user_{recipient_id}"
        socketio.emit('message_notification', {
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'content': content,
            'timestamp': new_chat.send_at.isoformat().replace('+00:00', 'Z')
        }, room=user_room)

        # 3. Enfin, on confirme à l'envoyeur que sa BDD a bien enregistré le message pour remplacer son statut "en attente" par le vrai ID
        # (le tempId permet au frontend de retrouver le message optimiste affiché immédiatement
        # et de le remplacer/mettre à jour avec l'ID définitif renvoyé par le serveur)
        emit('message_sent', {
            'success': True,
            'message_id': new_chat.id,
            'conversation_id': conversation_id,
            'timestamp': new_chat.send_at.isoformat().replace('+00:00', 'Z'),
            'tempId': temp_id,
            'message_data': message_data
        })

        print(f"Message successfully sent from {sender_id} to {recipient_id}")
        print(f"=== END SENDING MESSAGE ===\n")

    except Exception as e:
        # Rollback d'urgence pour ne pas bloquer ou corrompre SQL Alchemy si le commit foire
        db.session.rollback()
        print(f"CRITICAL ERROR in send_message: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Erreur lors de l\'envoi: {str(e)}'})


# ============================================================
# Événement : indicateur "X est en train d'écrire..."
# Ne touche pas à la base de données : purement transitoire, broadcasté en
# direct aux autres participants de la conversation
# ============================================================
@socketio.on('typing')
def handle_typing(data):
    """ Envoi des events de type "Enzo est en train d'écrire..." """
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')
    is_typing = data.get('is_typing', False)

    if conversation_id and user_id:
        # On bombarde l'info à tout le monde dans le tchat (sauf à celui qui tape, logique)
        emit('user_typing', {
            'user_id': user_id,
            'is_typing': is_typing,
            'conversation_id': conversation_id
        }, room=f"conv_{conversation_id}", include_self=False)