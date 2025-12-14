# permissions.py - CORRIGEZ comme ceci :
from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """Accès réservé aux admins uniquement"""
    def has_permission(self, request, view):
        user = request.user
        
        # Vérification de base
        if not user or not user.is_authenticated:
            return False
        
        # 1. Les superutilisateurs Django sont automatiquement admin
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        
        # 2. Le staff Django sont aussi considérés comme admin
        if hasattr(user, 'is_staff') and user.is_staff:
            return True
        
        # 3. Vérifier votre champ personnalisé 'role'
        if hasattr(user, 'role'):
            return user.role == "admin"
        
        # 4. Par défaut, refuser
        return False

class IsProf(BasePermission):
    """Accès réservé aux profs uniquement"""
    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Les superutilisateurs peuvent aussi accéder aux vues prof
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        
        # Vérifier le rôle prof
        if hasattr(user, 'role'):
            return user.role == "prof"
        
        return False

from rest_framework.permissions import BasePermission

class IsAdminOrProf(BasePermission):
    """Accès réservé aux admins et professeurs"""
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(user, 'is_superuser', False):
            return True

        if hasattr(user, 'role'):
            return user.role in ["admin", "prof"]

        return False

# Optionnel : Ajoutez cette permission pour plus de flexibilité
class IsEtud(BasePermission):
    """Accès réservé aux étudiants uniquement"""
    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Les superutilisateurs peuvent aussi accéder aux vues étudiant
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        
        # Vérifier le rôle étudiant
        if hasattr(user, 'role'):
            return user.role == "etud"
        
        return False