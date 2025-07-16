from django.urls import path
from . import views

urlpatterns = [
    path('send-request/<int:user_id>/', views.send_friend_request, name='send-friend-request'),
    path('process-request/<int:request_id>/<str:action>/', views.process_friend_request, name='process-friend-request'),
    path('remove-friend/<int:user_id>/', views.remove_friend, name='remove-friend'),
    path('cancel-request/<int:request_id>/', views.cancel_friend_request, name='cancel-friend-request'),
    path('manage/', views.manage_friends, name='manage-friends'),
    path('<uuid:public_id>/', views.profile_view, name='profile-view'),
    path('edit/', views.edit_profile, name='edit-profile'),
    path('<uuid:public_id>/display/', views.get_profile_display, name='get-profile-display'),
    path('<uuid:public_id>/edit-form/', views.get_profile_edit_form, name='get-profile-edit-form'),
    path('profile/upload-picture/', views.upload_profile_picture, name='upload-profile-picture'),
    path('profile/upload-banner/', views.upload_banner_picture, name='upload-banner-picture'),
]

