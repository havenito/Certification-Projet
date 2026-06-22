from flask import Blueprint, request, jsonify
from models import db
from models.user import User
from models.category import Category
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token

categories_bp = Blueprint('categories', __name__)


# ============================================================
# Route : création d'une nouvelle catégorie
# ============================================================
@categories_bp.route('/api/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')

    # Le nom est obligatoire
    if not name:
        return jsonify({'error': 'Category name is required'}), 400

    # Vérifie l'unicité du nom de catégorie
    if Category.query.filter_by(name=name).first():
        return jsonify({'error': 'Category already exists'}), 400

    new_category = Category(name=name, description=description)
    db.session.add(new_category)
    db.session.commit()

    return jsonify({'message': 'Category created successfully', 'category_id': new_category.id}), 201


# ============================================================
# Route : liste de toutes les catégories
# ============================================================
@categories_bp.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        categories = Category.query.all()
        result = []
        for category in categories:
            result.append({
                'id': category.id,
                'name': category.name,
                'description': category.description
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Route : mise à jour d'une catégorie existante
# Met à jour uniquement les champs fournis (et non vides/falsy)
# ============================================================
@categories_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')

    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    # NB: si name/description sont fournis mais vides (""), ils ne seront pas appliqués
    # car la condition `if name:` est falsy pour une chaîne vide
    if name:
        category.name = name
    if description:
        category.description = description

    db.session.commit()

    return jsonify({'message': 'Category updated successfully'}), 200


# ============================================================
# Route : suppression d'une catégorie
# Attention : ne supprime pas les posts liés à cette catégorie
# (à vérifier selon la contrainte de clé étrangère en base)
# ============================================================
@categories_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    db.session.delete(category)
    db.session.commit()

    return jsonify({'message': 'Category deleted successfully'}), 200


# ============================================================
# Route : récupération d'une catégorie unique par son ID
# ============================================================
@categories_bp.route('/api/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    return jsonify({
        'id': category.id,
        'name': category.name,
        'description': category.description
    }), 200


# ============================================================
# Route : liste de tous les posts appartenant à une catégorie donnée
# Inclut les médias associés et le pseudo de l'auteur de chaque post
# ============================================================
@categories_bp.route('/api/categories/<int:category_id>/posts', methods=['GET'])
def get_posts_by_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    try:
        # Imports locaux pour éviter les imports circulaires entre modèles
        from models.post import Post
        from models.post_media import PostMedia
        from models.user import User

        posts = Post.query.filter_by(category_id=category.id).all()
        posts_list = []

        for post in posts:
            # Récupère tous les médias associés à ce post
            media_list = PostMedia.query.filter_by(post_id=post.id).all()
            media = []

            for item in media_list:
                media.append({
                    'id': item.id,
                    'url': item.media_url,
                    'type': item.media_type
                })

            # Récupère le pseudo de l'auteur du post (None si l'utilisateur n'existe plus)
            user = User.query.get(post.user_id)
            user_pseudo = user.pseudo if user else None

            post_data = {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'media': media,
                'published_at': post.published_at.isoformat() if post.published_at else None,
                'user_id': post.user_id,
                'user_pseudo': user_pseudo
            }

            posts_list.append(post_data)

        return jsonify({'posts': posts_list}), 200
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la récupération des posts: {str(e)}'}), 500