from setuptools import setup, find_packages

setup(
    name="twitter-like",
    version="0.1",
    # find_packages liste automatiquement tous les sous-dossiers contenant un fichier __init__.py pour qu'ils soient inclus dans l'app
    packages=find_packages(),
)