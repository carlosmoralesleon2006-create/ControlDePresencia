class Config:
    DEBUG = True
    # Tu URI actual
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://Charlie4ever:michus123@Charlie4ever.mysql.eu.pythonanywhere-services.com/Charlie4ever$flaskydb'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'Clave secreta durisima'
    JWT_SECRET_KEY = 'JWTDAM'

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }