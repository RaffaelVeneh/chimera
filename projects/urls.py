from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='projects-index'),
    path('new/', views.create_project, name='create-project'),
    path('<int:project_id>/', views.project_detail, name='project-detail'),
    path('<int:project_id>/edit/', views.edit_project, name='edit-project'),
    path('<int:project_id>/delete/', views.delete_project, name='delete-project'),
    path('logout/', views.logout_view, name='logout'),
    path('<int:project_id>/add-task/', views.add_task, name='add-task'),
    path('tasks/<int:task_id>/toggle/', views.toggle_task, name='toggle-task'),
    path('<int:project_id>/add-comment/', views.add_comment, name='add-comment'),
    path('<int:project_id>/manage/', views.manage_collaborators, name='manage-collaborators'),
    path('<int:project_id>/add-collaborator/<int:user_id>/', views.add_collaborator, name='add-collaborator'),
    path('<int:project_id>/remove-collaborator/<int:user_id>/', views.remove_collaborator, name='remove-collaborator'),
    path('<int:project_id>/add-file/', views.add_file, name='add-file'),
    path('files/<int:file_id>/view/', views.view_file, name='view-file'),
]