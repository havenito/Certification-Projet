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
connected_users = {}

def init_socketio(app):
    """ Config de base au démarrage de Flask (CORS, logs, etc.) """
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    socketio.init_app(app, 
                      cors_allowed_origins=[frontend_url, "http://127.0.0.1:3000", "http://localhost:8080", "null"],
                      logger=True, 
                      engineio_logger=True)
    return socketio

@socketio.on('connect')
def handle_connect():
    # Un client vient de se connecter, on loggue sa session unique (sid)
    print(f'Client connecté: {request.sid}')
    emit('status', {'message': 'Connecté au serveur WebSocket'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client déconnecté: {request.sid}')
    # Nettoyage obligatoire : si le mec part, on vire son SID de notre dictionnaire global
    for user_id, sid in list(connected_users.items()):
        if sid == request.sid:
            del connected_users[user_id]
            break

@socketio.on('join_user')
def handle_join_user(data):
    """ On met l'utilisateur dans son propre canal privé (utile pour ses notifications) """
    user_id = data.get('user_id')
    if user_id:
        connected_users[user_id] = request.sid
        join_room(f"user_{user_id}")
        emit('status', {'message': f'Rejoint la room user_{user_id}'})
        print(f'Utilisateur {user_id} a rejoint sa room')

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """ Quand l'utilisateur ouvre une fenêtre de tchat """
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')
    
    if conversation_id and user_id:
        join_room(f"conv_{conversation_id}")
        emit('status', {'message': f'Rejoint la conversation {conversation_id}'})
        print(f'Utilisateur {user_id} a rejoint la conversation {conversation_id}')

@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """ Quand l'utilisateur quitte une conversation """
    conversation_id = data.get('conversation_id')
    user_id = data.get('user_id')
    
    if conversation_id and user_id:
        leave_room(f"conv_{conversation_id}")
        emit('status', {'message': f'Quitté la conversation {conversation_id}'})
        print(f'Utilisateur {user_id} a quitté la conversation {conversation_id}')

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
        temp_id = data.get('tempId') # ID temporaire généré par le front (pour l'affichage en attente de validation)

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
        if not conversation_id or isinstance(conversation_id, str):
            sorted_ids = sorted([sender_id, recipient_id])
            conversation_id = int(f"{sorted_ids[0]}{sorted_ids[1]:03d}")
        
        try:
            conversation_id = int(conversation_id)
        except (ValueError, TypeError):
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
        db.session.commit() # On valide en BDD
        
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
        room_name = f"conv_{conversation_id}"
        print(f"Broadcasting to room: {room_name}")
        socketio.emit('new_message', message_data, room=room_name, include_self=False)
        
        # 2. On envoie une notification globale à l'autre utilisateur s'il est connecté mais sur une autre page du site
        user_room = f"user_{recipient_id}"
        socketio.emit('message_notification', {
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'content': content,
            'timestamp': new_chat.send_at.isoformat().replace('+00:00', 'Z')
        }, room=user_room)

        # 3. Enfin, on confirme à l'envoyeur que sa BDD a bien enregistré le message pour remplacer son statut "en attente" par le vrai ID
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