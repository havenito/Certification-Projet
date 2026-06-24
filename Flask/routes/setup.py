from setuptools import setup, find_packages

# Fichier de configuration du packaging Python (setuptools).
# Il permet d'installer ce projet comme un package Python (ex: via `pip install -e .`
# en mode développement), ce qui rend les imports internes (ex: `from models import db`,
# `from services.file_upload import upload_file`) utilisables depuis n'importe où dans
# le projet sans avoir à manipuler manuellement le PYTHONPATH.
setup(
    # Nom du package, utilisé notamment si publié sur PyPI ou référencé comme dépendance
    name="twitter-like",

    # Numéro de version du package (à incrémenter manuellement à chaque changement notable)
    version="0.1",

    # find_packages liste automatiquement tous les sous-dossiers contenant un fichier
    # __init__.py pour qu'ils soient inclus dans l'app
    packages=find_packages(),
)