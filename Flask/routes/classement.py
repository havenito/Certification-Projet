from flask import Blueprint, jsonify
from models.user import User
from models.follow import Follow
from models import db

classement_bp = Blueprint('classement', __name__)


# ============================================================
# Route : top 10 des utilisateurs ayant le plus de followers
# ============================================================
@classement_bp.route('/api/classement/top10', methods=['GET'])
def classement_top10():
    # Jointure entre User et Follow pour compter le nombre de followers de chaque utilisateur.
    # outerjoin (LEFT JOIN) permet d'inclure aussi les utilisateurs sans aucun follower
    # (sinon un simple JOIN les exclurait complètement du résultat).
    users = (
        db.session.query(User, db.func.count(Follow.follower_id).label('followers_count'))
        .outerjoin(Follow, User.id == Follow.followed_id)
        .group_by(User.id)
        .order_by(db.desc('followers_count'))
        .limit(10)
        .all()
    )
    result = []
    for user, followers_count in users:
        result.append({
            "id": user.id,
            "pseudo": user.pseudo,
            "profile_picture": user.profile_picture,
            "followers_count": followers_count
        })
    return jsonify({"top10": result})


# ============================================================
# Route : rang d'un utilisateur spécifique dans le classement par followers
#
#  Performance : contrairement à classement_top10, cette route récupère et trie
# TOUS les utilisateurs (pas de LIMIT), puis parcourt la liste en Python pour
# trouver la position de l'utilisateur recherché. Sur une base avec beaucoup
# d'utilisateurs, cela devient coûteux. Une alternative plus performante serait
# de calculer le rang directement en SQL (ex: fonction de fenêtrage RANK() / ROW_NUMBER()
# côté base de données) plutôt que de charger tous les utilisateurs en mémoire.
# ============================================================
@classement_bp.route('/api/classement/user/<int:user_id>', methods=['GET'])
def classement_user(user_id):
    # Même logique de comptage des followers que pour le top 10, mais sans limite,
    # car on a besoin du classement complet pour déterminer le rang exact
    users = (
        db.session.query(User.id, User.pseudo, User.profile_picture, db.func.count(Follow.follower_id).label('followers_count'))
        .outerjoin(Follow, User.id == Follow.followed_id)
        .group_by(User.id)
        .order_by(db.desc('followers_count'))
        .all()
    )
    rank = None
    # enumerate(..., start=1) donne directement le rang (1er, 2e, 3e...) puisque
    # la liste est déjà triée par nombre de followers décroissant
    for idx, (uid, pseudo, profile_picture, followers_count) in enumerate(users, start=1):
        if uid == user_id:
            rank = {
                "rank": idx,
                "pseudo": pseudo,
                "profile_picture": profile_picture,
                "followers_count": followers_count
            }
            break  # Inutile de continuer une fois l'utilisateur trouvé

    # Si l'utilisateur n'existe pas (ou n'a pas été trouvé dans la liste), rank reste None
    return jsonify({"rank": rank})