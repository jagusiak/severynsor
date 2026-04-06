import os
from pathlib import Path
from django.urls import reverse_lazy
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-key')
DEBUG = os.environ.get('DEBUG', '1').lower() in ('1', 'true', 'yes', 'on')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '*').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',') if o.strip()]
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'localhost:8000')

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardian",
    "unfold.contrib.simple_history",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'polymorphic',
    'severynsor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

USE_X_FORWARDED_HOST = os.environ.get('USE_X_FORWARDED_HOST', '0').lower() in ('1', 'true', 'yes', 'on')
if os.environ.get('SECURE_PROXY_SSL_HEADER', '0').lower() in ('1', 'true', 'yes', 'on'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '0').lower() in ('1', 'true', 'yes', 'on')
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', '0').lower() in ('1', 'true', 'yes', 'on')

SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'postgres://severynsor_user:severynsor_password@db:5432/severynsor_db')
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SENSOR_GRAPH_LIMIT = 500

UNFOLD = {
    "SITE_TITLE": "Severynsor",
    "SITE_HEADER": "Severynsor",
    "INDEX_TITLE": "Dashboard",
    "SITE_SYMBOL": "sensors",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "type": "image/svg+xml",
            "href": lambda request: "/static/favicon.svg",
        }
    ],
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "show_collapse": True,
        "navigation": [
            {
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": "Sensors",
                        "icon": "sensors",
                        "link": reverse_lazy("admin:severynsor_sensor_changelist"),
                    },
                ],
            },
            {
                "title": "Settings",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Locations",
                        "icon": "place",
                        "link": reverse_lazy("admin:severynsor_location_changelist"),
                    },
                    {
                        "title": "Sensor Retrievers",
                        "icon": "download",
                        "link": reverse_lazy("admin:severynsor_sensorretriever_changelist"),
                    },
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
    "COLORS": {
        "primary": {
            "50": "oklch(97% 0.02 170)",
            "100": "oklch(93% 0.04 170)",
            "200": "oklch(86% 0.07 170)",
            "300": "oklch(77% 0.11 170)",
            "400": "oklch(67% 0.15 170)",
            "500": "oklch(57% 0.19 170)",
            "600": "oklch(47% 0.17 170)",
            "700": "oklch(37% 0.14 170)",
            "800": "oklch(27% 0.11 170)",
            "900": "oklch(17% 0.08 170)",
            "950": "oklch(12% 0.06 170)",
        },
    },
    "DASHBOARD_CALLBACK": "severynsor.dashboard.dashboard_callback",
}
