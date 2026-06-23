from flask import Blueprint, request, jsonify
from models import db
from models.poll import Poll
from models.category import Category
from models.pollvote import PollVote
from models.user import User
import sqlalchemy as sa

polls_bp = Blueprint('polls', __name__)


# ============================================================
# Route : liste paginée de tous les sondages, du plus récent au plus ancien,
# chacun enrichi avec les infos de sa catégorie
# ============================================================
@polls_bp.route('/api/polls', methods=['GET'])
def get_polls():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        # Pagination native fournie par Flask-SQLAlchemy
        polls_paginated = Poll.query.order_by(Poll.date_created.desc()).paginate(
            page=page,
            per_page=limit,
            error_out=False  # Ne lève pas d'erreur 404 si la page demandée est hors limites
        )

        polls_with_category = []
        for poll in polls_paginated.items:
            poll_dict = poll.to_dict()
            category = Category.query.get(poll.category_id)
            # Placeholder si la catégorie a été supprimée depuis
            poll_dict['category'] = {
                'id': category.id if category else None,
                'name': category.name if category else 'Catégorie supprimée',
                'description': category.description if category else None
            }
            polls_with_category.append(poll_dict)

        return jsonify({
            "polls": polls_with_category,
            "page": page,
            "limit": limit,
            "has_next": polls_paginated.has_next,
            "total_pages": polls_paginated.pages,
            "current_page": polls_paginated.page
        })
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : création d'un nouveau sondage
# ============================================================
@polls_bp.route('/api/polls', methods=['POST'])
def create_poll():
    try:
        data = request.get_json()
        question = data.get('question')
        description = data.get('description', '').strip()
        # Nettoie la liste d'options : retire les espaces inutiles et ignore les options vides
        options = [opt.strip() for opt in data.get('options', []) if opt.strip()]
        user_id = data.get('user_id')
        category_id = data.get('category_id')

        # Un sondage doit avoir une question, au moins 2 options valides, un créateur et une catégorie
        if not question or len(options) < 2 or not user_id or category_id is None:
            return jsonify({'error': 'Données manquantes ou invalides'}), 400

        category = Category.query.get(category_id)
        if not category:
            return jsonify({'error': 'Catégorie introuvable'}), 404

        poll = Poll(
            question=question,
            description=description if description else None,
            options=options,
            # Initialise le compteur de votes à 0 pour chaque option, dans le même ordre que `options`
            votes=[0]*len(options),
            user_id=int(user_id),
            category_id=int(category_id)
        )
        db.session.add(poll)
        db.session.commit()

        poll_dict = poll.to_dict()
        poll_dict['category'] = {
            'id': category.id,
            'name': category.name,
            'description': category.description
        }

        return jsonify({'poll': poll_dict}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : détail d'un sondage par son ID
# ============================================================
@polls_bp.route('/api/polls/<int:poll_id>', methods=['GET'])
def get_poll(poll_id):
    try:
        poll = Poll.query.get(poll_id)
        if not poll:
            return jsonify({'error': 'Sondage introuvable'}), 404

        poll_dict = poll.to_dict()
        category = Category.query.get(poll.category_id)
        poll_dict['category'] = {
            'id': category.id if category else None,
            'name': category.name if category else 'Catégorie supprimée',
            'description': category.description if category else None
        }

        return jsonify({'poll': poll_dict})
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : voter pour une option d'un sondage
# Un utilisateur ne peut voter qu'une seule fois par sondage (vérifié via PollVote)
# ============================================================
@polls_bp.route('/api/polls/<int:poll_id>/vote', methods=['POST'])
def vote_poll(poll_id):
    try:
        poll = Poll.query.get(poll_id)
        if not poll:
            return jsonify({'error': 'Sondage introuvable'}), 404

        data = request.get_json()
        option = data.get('option')
        user_id = data.get('user_id')
        # Vérifie que l'option est un entier valide correspondant à un index existant dans poll.options
        if option is None or not isinstance(option, int) or option < 0 or option >= len(poll.options):
            return jsonify({'error': 'Option invalide'}), 400
        if not user_id:
            return jsonify({'error': 'ID utilisateur requis'}), 400

        # Empêche un même utilisateur de voter plusieurs fois sur le même sondage
        existing_vote = PollVote.query.filter_by(poll_id=poll_id, user_id=int(user_id)).first()
        if existing_vote:
            return jsonify({'error': 'Vous avez déjà voté pour ce sondage'}), 400

        # Incrémente le compteur de votes pour l'option choisie (stocké comme liste JSON sur le modèle)
        poll.votes[option] += 1
        # flag_modified est nécessaire car SQLAlchemy ne détecte pas automatiquement
        # les mutations "en place" sur un champ JSON/liste (poll.votes[option] += 1
        # modifie l'objet Python sans déclencher la détection de changement par défaut)
        sa.orm.attributes.flag_modified(poll, "votes")
        # Enregistre le vote individuel pour pouvoir vérifier plus tard si l'utilisateur a déjà voté
        db.session.add(PollVote(poll_id=poll_id, user_id=int(user_id), option=option))
        db.session.commit()

        poll_dict = poll.to_dict()
        category = Category.query.get(poll.category_id)
        poll_dict['category'] = {
            'id': category.id if category else None,
            'name': category.name if category else 'Catégorie supprimée',
            'description': category.description if category else None
        }

        return jsonify({'poll': poll_dict})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : vérifie si un utilisateur a déjà voté pour un sondage donné,
# et renvoie l'option choisie si c'est le cas
# ============================================================
@polls_bp.route('/api/polls/<int:poll_id>/vote-status/<int:user_id>', methods=['GET'])
def check_vote_status(poll_id, user_id):
    """Vérifier si un utilisateur a déjà voté pour un sondage"""
    try:
        existing_vote = PollVote.query.filter_by(poll_id=poll_id, user_id=user_id).first()
        return jsonify({
            'has_voted': existing_vote is not None,
            'voted_option': existing_vote.option if existing_vote else None
        })
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : liste paginée des sondages appartenant à une catégorie donnée
# ============================================================
@polls_bp.route('/api/polls/category/<int:category_id>', methods=['GET'])
def get_polls_by_category(category_id):
    """Obtenir les sondages d'une catégorie spécifique avec pagination"""
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'error': 'Catégorie introuvable'}), 404

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        polls_paginated = Poll.query.filter_by(category_id=category_id).order_by(Poll.date_created.desc()).paginate(
            page=page,
            per_page=limit,
            error_out=False
        )

        polls_with_category = []
        for poll in polls_paginated.items:
            poll_dict = poll.to_dict()
            # Ici pas besoin de re-vérifier si la catégorie existe : on sait déjà
            # qu'elle existe puisqu'on l'a récupérée et vérifiée plus haut
            poll_dict['category'] = {
                'id': category.id,
                'name': category.name,
                'description': category.description
            }
            polls_with_category.append(poll_dict)

        return jsonify({
            "polls": polls_with_category,
            "page": page,
            "limit": limit,
            "has_next": polls_paginated.has_next,
            "total_pages": polls_paginated.pages,
            "current_page": polls_paginated.page,
            "category": {
                'id': category.id,
                'name': category.name,
                'description': category.description
            }
        })
    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500


# ============================================================
# Route : liste de tous les sondages créés par un utilisateur donné
# ============================================================
@polls_bp.route('/api/users/<int:user_id>/polls', methods=['GET'])
def get_user_polls(user_id):
    """Obtenir les sondages créés par un utilisateur, avec pagination"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        # Paramètres de pagination, identiques aux autres routes de listing (get_polls, get_polls_by_category)
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        polls_paginated = Poll.query.filter_by(user_id=user_id).order_by(Poll.date_created.desc()).paginate(
            page=page,
            per_page=limit,
            error_out=False  # Ne lève pas d'erreur 404 si la page demandée est hors limites
        )

        result = []
        for poll in polls_paginated.items:
            poll_dict = poll.to_dict()
            category = Category.query.get(poll.category_id)
            poll_dict['category'] = {
                'id': category.id if category else None,
                'name': category.name if category else 'Catégorie supprimée',
                'description': category.description if category else None
            }
            result.append(poll_dict)

        return jsonify({
            'polls': result,
            'page': page,
            'limit': limit,
            'has_next': polls_paginated.has_next,
            'total_pages': polls_paginated.pages,
            'current_page': polls_paginated.page
        })

    except Exception as e:
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500

# ============================================================
# Route : suppression d'un sondage
# Seul le créateur du sondage (user_id transmis dans le body) peut le supprimer
# Supprime également tous les votes associés avant de supprimer le sondage lui-même
# ============================================================
@polls_bp.route('/api/polls/<int:poll_id>', methods=['DELETE'])
def delete_poll(poll_id):
    """Supprimer un sondage"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'ID utilisateur requis'}), 400

        poll = Poll.query.get(poll_id)
        if not poll:
            return jsonify({'error': 'Sondage introuvable'}), 404

        # Vérification d'autorisation : seul le créateur du sondage peut le supprimer
        # Cette vérification se base uniquement sur le user_id envoyé dans le corps
        # de la requête, sans authentification forte (ex: token JWT) — un client
        # malveillant pourrait potentiellement envoyer n'importe quel user_id.
        if poll.user_id != int(user_id):
            return jsonify({'error': 'Non autorisé'}), 403

        # Supprime d'abord tous les votes liés à ce sondage (contrainte de clé étrangère)
        PollVote.query.filter_by(poll_id=poll_id).delete()

        db.session.delete(poll)
        db.session.commit()

        return jsonify({'message': 'Sondage supprimé avec succès'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500