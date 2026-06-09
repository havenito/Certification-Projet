from flask import Blueprint, request, jsonify
from models.user import User
from models.category import Category

search_bp = Blueprint('search', __name__)

@search_bp.route('/api/users/search', methods=['GET'])
def search_users():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'users': []})
    users = User.query.filter(User.pseudo.ilike(f"%{query}%")).all()
    return jsonify({'users': [u.to_dict() for u in users]})

@search_bp.route('/api/categories/search', methods=['GET'])
def search_categories():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'categories': []})
    categories = Category.query.filter(Category.name.ilike(f"%{query}%")).all()
    return jsonify({'categories': [ {"id": c.id, "name": c.name} for c in categories ]})

@search_bp.route('/api/users/search-mention', methods=['GET'])
def search_mention():
    query = request.args.get('q', '')
    if len(query) < 1:
        return jsonify([])
    
    users = User.query.filter(
        User.pseudo.ilike(f'{query}%')
    ).limit(5).all()
    
    return jsonify([{
        'id': u.id,
        'pseudo': u.pseudo,
        'profile_picture': u.profile_picture,
        'first_name': u.first_name
    } for u in users])