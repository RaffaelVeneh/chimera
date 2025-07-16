from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

class CustomAccountAdapter(DefaultAccountAdapter):

    def get_signup_redirect_url(self, request):
        """
        Overrides the default signup redirect URL.
        Sends the user to the main project list after they sign up.
        """
        # This points to the URL defined in settings.LOGIN_REDIRECT_URL
        return settings.LOGIN_REDIRECT_URL