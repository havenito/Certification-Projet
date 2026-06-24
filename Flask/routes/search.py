from flask import Blueprint, request, jsonify
from models.user import User
from models.category import Category

search_bp = Blueprint('search', __name__)


# ============================================================
# Route : recherche d'utilisateurs par pseudo
# Recherche "contient" (le terme peut apparaître n'importe où dans le pseudo)
# ============================================================
@search_bp.route('/api/users/search', methods=['GET'])
def search_users():
    query = request.args.get('q', '')

    # Si le champ de recherche est vide, on renvoie une liste vide direct pour économiser la BDD
    if not query:
        return jsonify({'users': []})

    # Le ilike permet de chercher sans bloquer sur les majuscules/minuscules, et les % cherchent n'importe où dans le pseudo
    users = User.query.filter(User.pseudo.ilike(f"%{query}%")).all()
    return jsonify({'users': [u.to_dict() for u in users]})


# ============================================================
# Route : recherche de catégories par nom
# Même logique de recherche "contient" que pour les utilisateurs
# ============================================================
@search_bp.route('/api/categories/search', methods=['GET'])
def search_categories():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'categories': []})

    categories = Category.query.filter(Category.name.ilike(f"%{query}%")).all()
    return jsonify({'categories': [ {"id": c.id, "name": c.name} for c in categories ]})


# ============================================================
# Route : autocomplétion des @mentions dans la rédaction d'un post
# Recherche "commence par" (et non "contient"), volontairement plus restrictive
# que search_users, et limitée à 5 résultats pour rester adaptée à une petite
# pop-up de suggestions en temps réel pendant la saisie
# ============================================================
@search_bp.route('/api/users/search-mention', methods=['GET'])
def search_mention():
    """ Endpoint optimisé pour l'autocomplétion des @mentions quand un utilisateur écrit un post """
    query = request.args.get('q', '')

    # On n'interroge pas la base tant que l'utilisateur n'a pas tapé au moins un caractère après le @
    if len(query) < 1:
        return jsonify([])

    # Ici, pas de % au début du ilike : on veut uniquement les pseudos qui COMMENCENT par ce qui est tapé
    # Le limit(5) évite de charger des centaines d'utilisateurs pour rien dans la petite pop-up du front
    users = User.query.filter(
        User.pseudo.ilike(f'{query}%')
    ).limit(5).all()

    # On renvoie uniquement le strict nécessaire pour l'affichage de la liste des suggestions
    # (contrairement à search_users qui renvoie le profil complet via to_dict())
    return jsonify([{
        'id': u.id,
        'pseudo': u.pseudo,
        'profile_picture': u.profile_picture,
        'first_name': u.first_name
    } for u in users])