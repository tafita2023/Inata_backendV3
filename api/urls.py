from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    utilisateur_connecte, UpdateProfilView,UpdatePhotoView, CreateStripeSessionView, stripe_webhook,
    UserListView, UpdateUserView, DeleteUserView, SecureRegisterView, GenerateInvitationLink,
    ClasseViewSet, MatiereViewSet, SalleViewSet, ProfesseurListView, EmploiDuTempsView, PaiementListCreateView,
    ajouter_frais, frais_disponibles, FraisPaiementViewSet, FraisAdminListView, matieres_professeur, NoteViewSet,
    EtudiantsParClasse, EvaluationViewSet, TacheViewSet, EvenementViewSet, AbsenceViewSet, AbsenceProfesseurViewSet,
    FraisPaiementDetailView, AdminPaiementCreateView, AdminEvaluationListView, AdminNoteListView,
    DevoirListCreateView, download_devoir, DevoirEtudiantView, MatiereEtudiantView, NotesEtudiantView, emploi_etudiant,
    etudiant_info, promotion_etudiants, UserDetailView, admin_notes_etudiants, BulletinView, DownloadBulletinView, 
    DownloadBulletinsClasseView, UniteViewSet, SalaireClasseMatiereViewSet, debug_permissions
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'absences/prof', AbsenceProfesseurViewSet, basename='absences-prof')
router.register(r'evenements', EvenementViewSet, basename='evenement')
router.register(r'taches', TacheViewSet, basename='taches')
router.register(r'admin/classes', ClasseViewSet, basename='classes')
router.register(r'admin/unites', UniteViewSet, basename='unites')
router.register(r'admin/matieres', MatiereViewSet, basename='matieres')
router.register(r'admin/salle', SalleViewSet, basename='salle')
router.register(r'admin/frais-classe', FraisPaiementViewSet, basename='frais-classe')
router.register(r'absences', AbsenceViewSet, basename='absence')
router.register(r'salaires-prof', SalaireClasseMatiereViewSet, basename='salaire-prof')
router.register(r'professeur/notes', NoteViewSet, basename='prof-notes')
router.register(r'professeur/evaluations', EvaluationViewSet, basename='evaluations')
urlpatterns = [

    # Router
    path('', include(router.urls)),
    path('api/debug-permissions/', debug_permissions, name='debug_permissions'),

    # Utilisateur
    path('utilisateur-connecte/', utilisateur_connecte, name='utilisateur-connecte'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('admin/generate-invite/', GenerateInvitationLink.as_view(), name='generate-invite'),
    path('register/<str:token>/', SecureRegisterView.as_view(), name='secure-register'),
    path('user/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('user/modifier-profil/', UpdateProfilView.as_view(), name='update-profile'),
    path('user/modifier-photo/', UpdatePhotoView.as_view(), name='update-photo'),

    # Paiement
    path('etudiant/frais_disponibles/', frais_disponibles, name='frais_disponibles'),
    path('paiements/stripe-session/', CreateStripeSessionView.as_view(), name='stripe-session'),
    path('paiements/stripe-webhook/', stripe_webhook, name='stripe-webhook'),
    path('etudiant/paiements/', PaiementListCreateView.as_view(), name='paiement-list-create'),
    path('etudiant/ajouter-frais/', ajouter_frais, name='ajouter_frais'),
    path('etudiant/emplois-du-temps/', emploi_etudiant, name='emploi_etudiant'),
    path('etudiant/devoirs/', DevoirEtudiantView.as_view(), name='devoirs-etudiant'),
    path('etudiant/matieres/', MatiereEtudiantView.as_view(), name='matieres-etudiant'),
    path('etudiant/notes/<int:matiere_id>/', NotesEtudiantView.as_view(), name='notes-etudiant'),
    path('etudiant/info/', etudiant_info, name='etudiant_info'),

    # Admin
    path('admin/utilisateurs/', UserListView.as_view(), name='user-list'),
    path('admin/promotion/', promotion_etudiants, name='promouvoir-etudiants'),
    path('admin/utilisateurs/modifier/<int:user_id>/', UpdateUserView.as_view(), name='update-user'),
    path('admin/utilisateurs/supprimer/<int:user_id>/', DeleteUserView.as_view(), name='delete-user'),
    path('admin/professeurs/', ProfesseurListView.as_view(), name='professeurs-list'),
    path('admin/emplois-du-temps/', EmploiDuTempsView.as_view(), name='emploi-du-temps'),
    path('admin/paiements/', FraisAdminListView.as_view(), name='paiement-list'),
    path('admin/paiements/ajouter/', AdminPaiementCreateView.as_view(), name='paiement-create'),
    path('admin/frais/', FraisAdminListView.as_view(), name='admin-frais'),
    path('admin/classes/<int:classe_id>/etudiants/', EtudiantsParClasse.as_view(), name='admin-etudiants-par-classe'),
    path('admin/frais-classe/<int:classe>/', FraisPaiementDetailView.as_view(), name='frais-classe-detail'),
    path('admin/evaluations/', AdminEvaluationListView.as_view(), name='admin-evaluations'),
    
    path('admin/notes/', AdminNoteListView.as_view(), name='admin-notes'),
    path('admin/notes/etudiants/', admin_notes_etudiants, name='admin-notes-etudiants'),
    path('admin/bulletins/', BulletinView.as_view(), name='admin-bulletins'),
    path('admin/bulletins/download/<int:etudiant_id>/', DownloadBulletinView.as_view(), name='download-bulletin'),
    path('admin/bulletins/download/class/<str:classe_niveau>/', DownloadBulletinsClasseView.as_view(), name='download-bulletins-classe'),

    # Professeur
    path('professeur/emplois-du-temps/', EmploiDuTempsView.as_view(), name='emploi-du-temps-prof'),
    path('professeur/matieres/', matieres_professeur, name='prof_matieres'),
    path('professeur/classes/<int:classe_id>/etudiants/', EtudiantsParClasse.as_view(), name='prof-etudiants-par-classe'),
    path('professeur/devoirs/', DevoirListCreateView.as_view(), name='professeur-devoirs'),
    path('professeur/telecharger/<str:filename>', download_devoir, name='download_devoir'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)