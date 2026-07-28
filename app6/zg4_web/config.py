import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    # Upewnij się, że katalog instance istnieje
    instance_path = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_path, 'zgrzewanie.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False