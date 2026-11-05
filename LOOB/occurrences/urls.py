from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('new/', views.new_entry, name='new_entry'),
    path('entry/<int:pk>/', views.occurrence_detail, name='occurrence_detail'),
    path('entry/<int:pk>/amend/', views.amend_occurrence, name='amend_occurrence'),
    path('manager/officers/', views.officer_roster, name='officer_roster'),
    
    # Forced password change route for first-time officer login
    path('change-password/', views.ForcedPasswordChangeView.as_view(), name='force_password_change'),
]