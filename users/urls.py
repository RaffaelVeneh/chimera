from django.urls import path
from . import views

urlpatterns = [
    path('send-request/<int:user_id>/', views.send_friend_request, name='send-friend-request'),
    path('process-request/<int:request_id>/<str:action>/', views.process_friend_request, name='process-friend-request'),
    path('remove-friend/<int:user_id>/', views.remove_friend, name='remove-friend'),
    path('cancel-request/<int:request_id>/', views.cancel_friend_request, name='cancel-friend-request'),
    path('manage/', views.manage_friends, name='manage-friends'),
]

