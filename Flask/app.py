from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from config import Config
from models import db
from routes.auth import auth_bp, bcrypt
from routes.posts import posts_bp
from routes.replies import replies_api
from routes.comments import comments_api
from services.file_upload import init_cloudinary
from routes.categories import categories_bp
from routes.follows import follows_api
from routes.subscriptions import subscriptions_bp
from routes.likes import likes_bp
from routes.favorites import favorites_bp
from routes.polls import polls_bp
from routes.notifications import notifications_api
from routes.comment_likes import comment_likes_bp
from routes.reply_likes import reply_likes_bp
from routes.chat import chats_bp
from routes.search import search_bp
from routes.signalement import bp_signalement
from routes.warn import warn_bp
from routes.classement import classement_bp

from routes.websocket_chat import init_socketio

# Instance Flask-Mail créée au niveau module : un seul objet Mail partagé,
# initialisé plus tard via mail.init_app(app) dans create_app()
mail = Mail()


def create_app(config_class=Config):
    """
    Application factory : construit et configure l'instance Flask plutôt que
    d'avoir une variable `app` globale. Ce pattern permet par exemple de créer
    plusieurs instances de l'app avec des configurations différentes (utile
    pour les tests, qui peuvent vouloir une config dédiée).
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialisation des extensions Flask sur cette instance précise de l'app
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)
    mail.init_app(app)

    # Configuration de Cloudinary (service d'hébergement des médias uploadés)
    init_cloudinary(app)

    # Enregistrement de tous les blueprints (groupes de routes) de l'application.
    # Chaque blueprint correspond à un fichier de routes dédié à un domaine fonctionnel
    # (auth, posts, commentaires, likes, abonnements Stripe, modération, etc.)
    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(replies_api)
    app.register_blueprint(comments_api)
    app.register_blueprint(follows_api)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(likes_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(polls_bp)
    app.register_blueprint(notifications_api)
    app.register_blueprint(comment_likes_bp)
    app.register_blueprint(reply_likes_bp)
    app.register_blueprint(chats_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(bp_signalement)
    app.register_blueprint(warn_bp)
    app.register_blueprint(classement_bp)

    # Initialise Flask-SocketIO sur cette instance d'app (gère le chat en temps réel)
    socketio = init_socketio(app)

    # Création des tables en base de données au démarrage, si elles n'existent pas déjà.
    # Les imports de modèles ici (PostMedia, CommentMedia, etc.) sont nécessaires pour
    # que SQLAlchemy "connaisse" ces modèles et les inclue dans db.create_all(), même
    # s'ils ne sont pas utilisés directement dans ce fichier.
    with app.app_context():
        from models.post_media import PostMedia
        from models.comment_media import CommentMedia
        from models.comment_like import CommentLike
        from models.reply_media import ReplyMedia
        from models.reply_like import ReplyLike
        from models.subscription import Subscription
        from models.favorite import Favorite
        db.create_all()

    # Route de "health check" très simple, utile pour vérifier que le serveur
    # répond (monitoring, configuration d'un load balancer, etc.)
    @app.route('/api/health')
    def health():
        return jsonify({"status": "ok"}), 200

    # On retourne à la fois l'app Flask ET l'instance socketio, car c'est socketio.run()
    # (et non app.run()) qui doit démarrer le serveur pour que les WebSockets fonctionnent
    return app, socketio


if __name__ == '__main__':
    app, socketio = create_app()
    # debug=True et allow_unsafe_werkzeug=True ne doivent JAMAIS être utilisés en
    # production : debug=True active le débogueur interactif Werkzeug, qui permet
    # l'exécution de code Python arbitraire depuis le navigateur en cas d'erreur non gérée
    # (faille de sécurité critique si exposé publiquement), et allow_unsafe_werkzeug
    # contourne volontairement la protection de Flask-SocketIO empêchant l'utilisation du
    # serveur de développement Werkzeug en production. Pour un déploiement réel, il faudrait
    # un serveur de production (ex: gunicorn avec eventlet/gevent, ou un déploiement dédié
    # pour Socket.IO) et debug=False.
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)