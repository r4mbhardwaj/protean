"""
Default settings. Override these with settings in the module pointed to
by the PROTEAN_CONFIG environment variable.
"""

import os

####################
# CORE             #
####################

DEBUG = False

# A secret key for this particular Protean installation. Used in secret-key
# hashing algorithms.
SECRET_KEY = ''

####################
# GENERIC DATABASE #
####################

# Default no. of records to fetch per query
PER_PAGE = 10

####################
# ElasticSearch    #
####################

ELASTICSEARCH_HOSTS = ['localhost']
ELASTICSEARCH_USER = 'elastic'
ELASTICSEARCH_SECRET = os.environ.get('ELASTICSEARCH_SECRET') or 'changeme'

####################
# Logging          #
####################

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        }
    },
    'loggers': {
        'protean': {
            'handlers': ['console'],
            'level': 'INFO',
        }
    }
}

