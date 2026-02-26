from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('menu-types/', views.menu_types, name='menu_types'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='user_login'),
    path('individual-menu/', views.individual_menu, name='individual_menu'),
    path('results/', views.results, name='results'),
    path('refresh-meal/', views.refresh_meal, name='refresh_meal'),
    path('api/favorite/toggle/', views.toggle_favorite, name='toggle_favorite'),
    path('api/meal/replace/', views.replace_meal_ajax, name='replace_meal'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.user_logout, name='user_logout'),
    path('verify-email/', views.verify_email, name='verify_email'),
]