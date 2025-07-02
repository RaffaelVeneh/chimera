from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    # This function is crucial for making the signals work
    def ready(self):
        import users.signals

