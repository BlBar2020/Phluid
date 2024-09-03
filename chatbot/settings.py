# Import necessary modules
from pathlib import Path
from dotenv import load_dotenv
import os

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv()

# Print the loaded API key for verification
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
print(f"API Key loaded in settings.py: {OPENAI_API_KEY}")
if not OPENAI_API_KEY:
    raise ValueError("Missing environment variable: OPENAI_API_KEY")

# Set the session cookie age to 30 minutes (1800 seconds)
SESSION_COOKIE_AGE = 1800

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Set the secret key for Django
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')


# Set the debug mode
DEBUG = True

# Set the allowed hosts for the server
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'phluid.ai', 'www.phluid.ai']

# Environment Variables Handling
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("Missing environment variable: OPENAI_API_KEY")

POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
if not POLYGON_API_KEY:
    raise ValueError("Missing environment variable: POLYGON_API_KEY")


# Define the installed apps for the project
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_static",
    "audney",
]

# Define the middleware for the project
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'audney.session_timeout_middleware.SessionIdleTimeoutMiddleware',
]

# Set the root URL configuration
ROOT_URLCONF = "chatbot.urls"

# Set the template configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Set the WSGI application
WSGI_APPLICATION = "chatbot.wsgi.application"

# Set the database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'CONN_MAX_AGE': 1800,  # Keep database connection open for 1800 seconds
    }
}

# Set the password validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator", },
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator", },
]

# Set the internationalization settings
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Set the static files settings
BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Set the default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'mail.privateemail.com'  # SMTP server address
EMAIL_PORT = 587  # Port for sending email (use 465 for SSL)
EMAIL_USE_TLS = True  # Use TLS encryption
EMAIL_HOST_USER = 'blake@phluid.ai'  # Your SMTP server username
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
if not EMAIL_HOST_PASSWORD:
    raise ValueError("Missing environment variable: EMAIL_HOST_PASSWORD")  # Your SMTP server password

# Set the logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django_debug.log'),
            'formatter': 'verbose',
        },
        'console': {  # Add this handler for console output
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            # Use both file and console handlers
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

LOGIN_URL = '/login'
