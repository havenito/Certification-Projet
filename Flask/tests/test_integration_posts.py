"""
Tests d'intégration pour les posts et catégories
Ces tests vérifient les opérations sur la base de données
"""
from models.post import Post
from models.category import Category
from models import db


class TestPostsDatabase:
    """Tests de base de données pour les posts"""
    
    def test_create_post_in_db(self, app, sample_user):
        """Test de création d'un post en base de données"""
        with app.app_context():
            category = db.session.query(Category).first()
            
            post = Post(
                title='Test Post',
                content='Test content',
                user_id=sample_user.id,
                category_id=category.id
            )
            db.session.add(post)
            db.session.commit()
            
            # Vérifier création
            found = db.session.query(Post).filter_by(title='Test Post').first()
            assert found is not None
            assert found.content == 'Test content'
    
    def test_query_posts_by_user(self, app, sample_user):
        """Test de requête des posts par utilisateur"""
        with app.app_context():
            category = db.session.query(Category).first()
            
            post1 = Post(title='Post 1', content='Content 1', user_id=sample_user.id, category_id=category.id)
            post2 = Post(title='Post 2', content='Content 2', user_id=sample_user.id, category_id=category.id)
            db.session.add_all([post1, post2])
            db.session.commit()
            
            posts = db.session.query(Post).filter_by(user_id=sample_user.id).all()
            assert len(posts) >= 2
    
    def test_update_post(self, app, sample_user):
        """Test de mise à jour d'un post"""
        with app.app_context():
            category = db.session.query(Category).first()
            
            post = Post(title='Old Title', content='Old', user_id=sample_user.id, category_id=category.id)
            db.session.add(post)
            db.session.commit()
            post_id = post.id
            
            post.title = 'New Title'
            db.session.commit()
            
            updated = db.session.query(Post).filter_by(id=post_id).first()
            assert updated.title == 'New Title'
    
    def test_delete_post(self, app, sample_user):
        """Test de suppression d'un post"""
        with app.app_context():
            category = db.session.query(Category).first()
            
            post = Post(title='To Delete', content='Delete me', user_id=sample_user.id, category_id=category.id)
            db.session.add(post)
            db.session.commit()
            post_id = post.id
            
            db.session.delete(post)
            db.session.commit()
            
            deleted = db.session.query(Post).filter_by(id=post_id).first()
            assert deleted is None
    
    def test_count_posts(self, app, sample_user):
        """Test de comptage des posts"""
        with app.app_context():
            category = db.session.query(Category).first()
            
            for i in range(3):
                post = Post(title=f'Post {i}', content=f'Content {i}', user_id=sample_user.id, category_id=category.id)
                db.session.add(post)
            db.session.commit()
            
            count = db.session.query(Post).filter_by(user_id=sample_user.id).count()
            assert count >= 3


class TestCategoryDatabase:
    """Tests de base de données pour les catégories"""
    
    def test_create_category(self, app):
        """Test de création de catégorie"""
        with app.app_context():
            cat = Category(name='Sports')
            db.session.add(cat)
            db.session.commit()
            
            found = db.session.query(Category).filter_by(name='Sports').first()
            assert found is not None
    
    def test_query_all_categories(self, app):
        """Test de récupération de toutes les catégories"""
        with app.app_context():
            cat1 = Category(name='Tech')
            cat2 = Category(name='News')
            db.session.add_all([cat1, cat2])
            db.session.commit()
            
            categories = db.session.query(Category).all()
            assert len(categories) >= 2
