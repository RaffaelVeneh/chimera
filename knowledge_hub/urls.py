from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.paper_search, name='paper-search'),
]