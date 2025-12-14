from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from collections import defaultdict
import stripe
from django.conf import settings
from django.http import FileResponse, Http404
import os
from collections import OrderedDict
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from django.http import HttpResponse
from datetime import datetime
import io, base64
from django.db import models
from django.db.models import Avg
from rest_framework.exceptions import PermissionDenied
from .models import (
    User, InvitationLink, Classe, Matiere, EmploiDuTemps, Salle,
    Paiement, FraisMensuel, FraisPaiement, Note, Evaluation, Tache, 
    Evenement, Absence, Exercice, Unite, SalaireClasseMatiere, PaiementProf
)
from .serializers import (
    UserSerializer, PaiementSerializer,
    ClasseSerializer, MatiereSerializer,
    EmploiDuTempsSerializer, SalleSerializer, 
    FraisMensuelAdminSerializer, FraisPaiementSerializer, 
    NoteSerializer, ProfNoteSerializer, EvaluationSerializer, TacheSerializer, 
    EvenementSerializer, AbsenceSerializer, AbsenceProfesseurSerializer,
    PaiementManualSerializer, NoteAdminSerializer, ExerciceSerializer, 
    UniteSerializer, SalaireClasseMatiereSerializer, PaiementProfSerializer
)
# Supprimez les imports en double et gardez seulement celui depuis le répertoire courant
from .permissions import IsAdmin
stripe.api_key = settings.STRIPE_SECRET_KEY

# ---------------- Utilisateur connecté ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def utilisateur_connecte(request):
    user = request.user
    print(f"Utilisateur authentifié: {user.email}")
    
    photo_url = None
    
    if hasattr(user, 'photo') and user.photo:
        photo_url = request.build_absolute_uri(user.photo.url)
    
    return Response({
        'id': user.id,
        'email': user.email,
        'role': getattr(user, 'role', 'unknown'),
        'nom': getattr(user, 'nom', ''),
        'prenom': getattr(user, 'prenom', ''),
        'phone': getattr(user, 'phone', ''),
        'photo': photo_url,
    })

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Utilisateur créé avec succès",
                "user": UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        print("❌ Erreurs de validation :", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(username=email, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Connexion réussie',
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'nom': user.nom,
                'prenom': user.prenom,
                'role': user.role,
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Email ou mot de passe incorrect'}, status=status.HTTP_401_UNAUTHORIZED)

# ---------------- Utilisateurs ----------------
class UserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UpdateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé"}, status=404)
        data = request.data
        if 'role' in data:
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = data['is_active']
        user.save()
        return Response({
            "message": "Utilisateur mis à jour avec succès",
            "user": UserSerializer(user).data
        }, status=200)

class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            user.delete()
            return Response({"message": "Utilisateur supprimé avec succès"}, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé"}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def promotion_etudiants(request):
    """
    Permet à l'admin de promouvoir les étudiants :
    - Passe en classe supérieure si moyenne >= 10
    - Marque 'Diplômé' s'ils sont dans la dernière classe
    - Sinon, ils redoublent
    """
    try:
        promus = 0
        redoublants = 0
        diplomes = 0
        erreurs = []

        etudiants = User.objects.filter(role='etud', is_active=True).select_related('classe')

        for etu in etudiants:
            if not etu.classe:
                erreurs.append(f"{etu.nom} {etu.prenom} n'a pas de classe assignée.")
                continue

            notes = Note.objects.filter(etudiant=etu)

            if not notes.exists():
                erreurs.append(f"Aucune note trouvée pour {etu.nom} {etu.prenom}.")
                continue

            moyenne = notes.aggregate(Avg('valeur'))['valeur__avg'] or 0
            current_classe = etu.classe
            next_classe = Classe.objects.filter(ordre__gt=current_classe.ordre).order_by('ordre').first()

            if moyenne >= 10 and next_classe:
                etu.classe = next_classe
                etu.annee = etu.annee + 1
                etu.save()
                promus += 1
            elif moyenne >= 10 and not next_classe:
                etu.role = 'diplome'
                etu.save()
                diplomes += 1
            else:
                redoublants += 1

        return Response({
            "message": "Promotion terminée avec succès",
            "promus": promus,
            "redoublants": redoublants,
            "diplomes": diplomes,
            "erreurs": erreurs
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# ---------------- Invitation et Inscription ----------------
class GenerateInvitationLink(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Changé: admin seulement

    def post(self, request):
        # Plus besoin de vérifier manuellement le rôle, la permission IsAdmin le fait
        role_map = {'admin': 'admin', 'prof': 'prof', 'etud': 'etud'}
        role = role_map.get(request.data.get("role"))
        if not role:
            return Response({"error": "Rôle invalide"}, status=400)
        classe = None
        classe_id = request.data.get("classe_id")
        if role == 'etud':
            if not classe_id:
                return Response({"error": "Classe obligatoire"}, status=400)
            try:
                classe = Classe.objects.get(id=classe_id)
            except Classe.DoesNotExist:
                return Response({"error": "Classe invalide"}, status=400)
        token = get_random_string(length=32)
        invitation = InvitationLink.objects.create(token=token, role=role)
        if classe:
            invitation.classe_id = classe.id
            invitation.save()
        invite_url = f"{settings.FRONTEND_URL}/register/{token}"
        return Response({"token": token, "invite_link": invite_url, "classe": classe.niveau if classe else None}, status=201)

class SecureRegisterView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def post(self, request, token):
        try:
            invitation = InvitationLink.objects.get(token=token, is_used=False)
        except InvitationLink.DoesNotExist:
            return Response({"error": "Lien invalide ou déjà utilisé"}, status=400)

        data = request.data.copy()
        data['role'] = invitation.role

        # Si c'est un étudiant, on assigne la classe depuis le lien
        if invitation.role == 'etud' and invitation.classe:
            data['classe_id'] = invitation.classe.id

        # Pour les profs/admins, on supprime les champs inutiles si envoyés
        if invitation.role in ['prof', 'admin']:
            data.pop('adresse', None)
            data.pop('date_naissance', None)
            data.pop('lieu_naissance', None)
            data.pop('classe_id', None)

        serializer = self.get_serializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            invitation.is_used = True
            invitation.save()
            return Response(serializer.data, status=201)

        print("❌ Erreurs du serializer :", serializer.errors)
        return Response(serializer.errors, status=400)

class GetInvitationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = InvitationLink.objects.get(token=token, is_used=False)
            data = {"role": invitation.role}
            if invitation.role == "etud" and invitation.classe:
                data["classe"] = invitation.classe.niveau
                data["classe_id"] = invitation.classe.id
            return Response(data, status=200)
        except InvitationLink.DoesNotExist:
            return Response({"error": "Lien invalide ou expiré"}, status=404)
        
# ---------------- Classes, Salles, Matières ----------------
class ClasseViewSet(viewsets.ModelViewSet):
    queryset = Classe.objects.all()
    serializer_class = ClasseSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin pour les opérations admin

class SalleViewSet(viewsets.ModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

class UniteViewSet(viewsets.ModelViewSet):
    queryset = Unite.objects.all()
    serializer_class = UniteSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

class MatiereViewSet(viewsets.ModelViewSet):
    queryset = Matiere.objects.all()
    serializer_class = MatiereSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

class ProfesseurListView(APIView):
    permission_classes = [IsAuthenticated]  # Accessible à tous les utilisateurs authentifiés
    
    def get(self, request):
        profs = User.objects.filter(role='prof')
        serializer = UserSerializer(profs, many=True)
        return Response(serializer.data)

# ---------------- Taches ----------------
class TacheViewSet(viewsets.ModelViewSet):
    serializer_class = TacheSerializer
    queryset = Tache.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Tache.objects.filter(created_by=user).order_by('-date_creation')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EvenementViewSet(viewsets.ModelViewSet):
    queryset = Evenement.objects.all().order_by('date_debut')
    serializer_class = EvenementSerializer
    permission_classes = [IsAuthenticated]  # Par défaut pour tous

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]  # Seuls les admins peuvent modifier
        else:
            permission_classes = [IsAuthenticated]  # Tous peuvent lire
        return [p() for p in permission_classes]
    
# ---------------- Emploi du temps ----------------
class EmploiDuTempsView(APIView):
    permission_classes = [IsAuthenticated]  # Accessible à tous les utilisateurs authentifiés
    
    def get(self, request):
        classe_id = request.query_params.get("classe_id")
        if not classe_id:
            return Response({"detail": "classe_id manquant"}, status=400)
        emplois = EmploiDuTemps.objects.filter(classe_id=classe_id).select_related("classe", "matiere__professeur").order_by("jour", "horaire")
        grouped = defaultdict(list)
        for emploi in emplois:
            grouped[emploi.jour].append(emploi)
        result = [{"jour": jour, "creneaux": EmploiDuTempsSerializer(creneaux, many=True).data} for jour, creneaux in grouped.items()]
        return Response(result, status=200)

    def post(self, request):
        # Cette action devrait être réservée aux admins
        if not request.user.role == 'admin' and not request.user.is_staff:
            return Response({"detail": "Permission refusée"}, status=403)
            
        emploi_data = request.data
        if not emploi_data:
            return Response({"detail": "Aucune donnée reçue"}, status=400)
        classe_id = emploi_data[0].get("classe") if emploi_data else None
        if not classe_id:
            return Response({"detail": "Classe manquante"}, status=400)
        EmploiDuTemps.objects.filter(classe_id=classe_id).delete()
        serializer = EmploiDuTempsSerializer(data=emploi_data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Emploi du temps enregistré avec succès"}, status=201)
        return Response(serializer.errors, status=400)

# ---------------- Webhook Stripe ----------------
@csrf_exempt
def stripe_webhook(request):
    print("🔔 Webhook reçu ! Méthode :", request.method)
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        print("⚠ Échec de la vérification de signature")
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print("⚡ Session checkout reçu :", session)
        metadata = session.get('metadata', {})
        print("📦 Metadata :", metadata)

        etudiant_id = metadata.get("etudiant_id")
        frais_ids = metadata.get("frais_ids", "")

        if not etudiant_id or not frais_ids:
            print("⚠ Metadata manquantes")
            return HttpResponse(status=400)

        etudiant_id = int(etudiant_id)
        frais_ids = [int(m) for m in frais_ids.split(",")]

        frais_objs = FraisMensuel.objects.filter(
            id__in=frais_ids,
            etudiant__id=etudiant_id,
            est_paye=False
        )

        print("Frais trouvés:", list(frais_objs.values("id", "etudiant_id", "est_paye")))

        if frais_objs.exists():
            montant_total = sum(f.montant for f in frais_objs)
            paiement = Paiement.objects.create(
                etudiant_id=etudiant_id,
                montant_total=montant_total,
                stripe_session_id=session.get("id"),
                statut="Payé",
                mode_paiement="Stripe"
            )
            paiement.frais_mensuels.set(frais_objs)
            frais_objs.update(est_paye=True)

            print("💰 Frais mis à jour :", list(frais_objs.values("id", "est_paye")))

    return HttpResponse(status=200)

# ---------------- Frais ----------------
class FraisPaiementViewSet(viewsets.ModelViewSet):
    queryset = FraisPaiement.objects.select_related('classe').all()
    serializer_class = FraisPaiementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

# ---------------- Paiements ----------------
class PaiementCreateView(generics.CreateAPIView):
    queryset = Paiement.objects.all()
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'etud':
            return Paiement.objects.filter(etudiant=user)
        return Paiement.objects.all()

class PaiementListCreateView(generics.ListCreateAPIView):
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'etud':
            return Paiement.objects.filter(etudiant=user)
        elif user.role == 'admin':
            return Paiement.objects.all()
        return Paiement.objects.none()

# Vue pour récupérer les paiements de l'étudiant
class PaiementsEtudiantView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            paiements = Paiement.objects.filter(etudiant=user).prefetch_related('frais_mensuels').order_by('-date_creation')
            
            data = []
            for paiement in paiements:
                data.append({
                    'id': paiement.id,
                    'montant_total': paiement.montant_total,
                    'date_creation': paiement.date_creation,
                    'statut': paiement.statut,
                    'frais_mensuels': [
                        {
                            'id': frais.id,
                            'mois': frais.mois,
                            'montant': frais.montant
                        } for frais in paiement.frais_mensuels.all()
                    ]
                })
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreateStripeSessionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            etudiant = request.user
            frais_ids = request.data.get("frais_ids", [])

            if not frais_ids or not isinstance(frais_ids, list):
                return Response({"error": "Veuillez sélectionner au moins un frais."},
                                status=status.HTTP_400_BAD_REQUEST)

            frais_objs_ordered = []
            for frais_id in frais_ids:
                try:
                    f = FraisMensuel.objects.get(
                        id=frais_id, 
                        etudiant=etudiant, 
                        est_paye=False
                    )
                    frais_objs_ordered.append(f)
                except FraisMensuel.DoesNotExist:
                    continue

            if not frais_objs_ordered:
                return Response({"error": "Aucun frais valide trouvé."},
                                status=status.HTTP_400_BAD_REQUEST)

            montant_total = sum(f.montant for f in frais_objs_ordered)

            line_items = []
            for f in frais_objs_ordered:
                line_items.append({
                    "price_data": {
                        "currency": "mga",
                        "product_data": {
                            "name": f"Frais scolaire - {f.mois}",
                            "description": f"Frais de scolarité pour {f.mois}"
                        },
                        "unit_amount": int(f.montant),
                    },
                    "quantity": 1
                })

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                success_url=f"{frontend_url}/etudiant/ecolage?success=true&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{frontend_url}/etudiant/ecolage?canceled=true",
                customer_email=etudiant.email,
                metadata={
                    "etudiant_id": str(etudiant.id),
                    "frais_ids": ",".join(str(f.id) for f in frais_objs_ordered)
                }
            )

            print(f"🎯 Session Stripe créée: {session.id}")

            return Response({
                "session_id": session.id,
                "url": session.url,
                "montant_total": montant_total
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"Erreur serveur: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class CheckPaymentStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response({"error": "session_id manquant"}, status=400)
        
        try:
            paiement = Paiement.objects.get(
                stripe_session_id=session_id,
                etudiant=request.user
            )
            
            return Response({
                "statut": paiement.statut,
                "montant_total": paiement.montant_total,
                "date_paiement": paiement.date_paiement
            })
            
        except Paiement.DoesNotExist:
            return Response({"error": "Paiement non trouvé"}, status=404)

# Vue pour récupérer les frais disponibles
class FraisDisponiblesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            frais = FraisMensuel.objects.filter(
                etudiant=user,
                est_paye=False
            ).values('id', 'mois', 'montant', 'est_paye')
            
            return Response(list(frais), status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def ajouter_frais(request):
    user = request.user
    mois = request.data.get("mois")

    if not mois:
        return Response({"error": "Le mois est obligatoire"}, status=400)

    if not isinstance(mois, list):
        mois = [mois]

    if not hasattr(user, 'classe') or user.classe is None:
        return Response({"error": "Vous n'êtes rattaché à aucune classe"}, status=400)

    classe = user.classe
    try:
        montant = classe.frais.montant
    except FraisPaiement.DoesNotExist:
        return Response({"error": "Aucun montant défini pour cette classe"}, status=400)

    now = datetime.now()
    annee_scolaire = f"{now.year}-{now.year + 1}"

    frais_crees = []

    for m in mois:
        frais_existant = FraisMensuel.objects.filter(
            etudiant=user, 
            mois=m, 
            annee_scolaire=annee_scolaire
        ).first()
        
        if frais_existant:
            frais_crees.append(frais_existant)
        else:
            frais = FraisMensuel.objects.create(
                etudiant=user,
                mois=m,
                montant=montant,
                est_paye=False,
                annee_scolaire=annee_scolaire
            )
            frais_crees.append(frais)

    return Response({
        "message": "Frais créés/récupérés avec succès",
        "frais": [{"id": f.id, "mois": f.mois, "montant": f.montant, "est_paye": f.est_paye} for f in frais_crees]
    }, status=201)

# ---------------- Bulletins ----------------
class BulletinView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"message": "Accès autorisé aux bulletins"})

# ---------------- Bulletins d'un etudiant ----------------
class DownloadBulletinView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, etudiant_id):
        try:
            etudiant = User.objects.get(id=etudiant_id, role='etud')
        except User.DoesNotExist:
            return Response({"error": "Étudiant non trouvé"}, status=404)

        notes_examens_s2 = Note.objects.filter(
            etudiant=etudiant,
            evaluation__type='examen',
            evaluation__semestre=2
        ).select_related('evaluation__matiere__unite').order_by(
            'evaluation__matiere__unite__nom', 'evaluation__matiere__nom'
        )

        unite_dict = {}
        for note in notes_examens_s2:
            unite_nom = note.evaluation.matiere.unite.nom if note.evaluation.matiere.unite else '-'
            matiere_nom = note.evaluation.matiere.nom
            note_valeur = note.valeur
            unite_dict.setdefault(unite_nom, []).append((matiere_nom, note_valeur))

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=40, leftMargin=40,
            topMargin=190, bottomMargin=60
        )
        elements = []

        styles = getSampleStyleSheet()
        nom_centre_style = ParagraphStyle(
            'NomCentre', parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=12, spaceAfter=20,
            alignment=1, textColor=colors.black
        )
        info_style = ParagraphStyle(
            'Info', parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=11, spaceAfter=6
        )

        elements.append(Paragraph(f"<b>RELEVE DE NOTES</b>", nom_centre_style))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(f"<b>De : {etudiant.nom} {etudiant.prenom}</b>", nom_centre_style))
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(f"<b>Filière :</b> Informatique", info_style))
        elements.append(Paragraph(f"<b>Niveau :</b> {etudiant.classe.niveau if etudiant.classe else 'Non assigné'}", info_style))
        elements.append(Paragraph(f"<b>Spécialité :</b> Web Master / Infographiste", info_style))
        elements.append(Paragraph(f"<b>Année universitaire :</b> {datetime.now().year} - {datetime.now().year + 1}", info_style))
        elements.append(Spacer(1, 30))

        if unite_dict:
            table_data = [['Unité d\'enseignement', 'Modules', 'Note Examen finale /20']]
            span_indices = []

            current_row = 1
            for unite_nom, modules in unite_dict.items():
                for i, (matiere_nom, note_valeur) in enumerate(modules):
                    if i == 0:
                        table_data.append([unite_nom, matiere_nom, f"{note_valeur:.2f}"])
                    else:
                        table_data.append(['', matiere_nom, f"{note_valeur:.2f}"])
                if len(modules) > 1:
                    span_indices.append((current_row, current_row + len(modules) - 1))
                current_row += len(modules)

            table = Table(table_data, colWidths=[2*inch, 3*inch, 2*inch])
            style = TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])
            for start, end in span_indices:
                style.add('SPAN', (0, start), (0, end))
            table.setStyle(style)
            elements.append(table)
        else:
            elements.append(Paragraph("Aucune note d'examen disponible pour le semestre 2", styles['Normal']))

        elements.append(Spacer(1, 40))
        elements.append(Paragraph("Le Directeur", nom_centre_style))
        elements.append(Spacer(1, 50))
        elements.append(Paragraph("RANDRIAMAHARO Mamy", nom_centre_style))

        
        def header_footer(canvas, doc):
            canvas.saveState()
            
            logo_gauche = os.path.join(settings.BASE_DIR, "api/assets/InataLogo.png")
            logos_droite = [
                os.path.join(settings.BASE_DIR, "api/assets/cisco.png"),
                os.path.join(settings.BASE_DIR, "api/assets/pearson.png"),
                os.path.join(settings.BASE_DIR, "api/assets/oracle.png")
            ]
            
            logo_gauche_width, logo_gauche_height = 104, 104
            y_logo_gauche = 680
            if os.path.exists(logo_gauche):
                canvas.drawImage(logo_gauche, 40, y_logo_gauche, width=logo_gauche_width, height=logo_gauche_height, mask=None)
            
            logo_droite_width, logo_droite_height = 60, 40
            spacing = 5
            total_height_droite = len(logos_droite) * logo_droite_height + (len(logos_droite)-1)*spacing
            top_padding = -20
            y_start_droite = y_logo_gauche + logo_gauche_height/2 + total_height_droite/2 + top_padding
            for i, logo in enumerate(logos_droite):
                if os.path.exists(logo):
                    canvas.drawImage(logo, 470, y_start_droite - (i+1)*logo_droite_height - i*spacing, width=logo_droite_width, height=logo_droite_height, mask='auto')
            
            canvas.setFont('Helvetica-Bold', 14)
            canvas.drawCentredString(300, 740, "Institut de Arts et des Technologies Avancées")
            
            canvas.setFont('Helvetica-Bold', 10)
            canvas.drawCentredString(300, 720, "Etablissement d'Enseignement Superieur Privé")

            canvas.setFont('Helvetica', 6)
            canvas.drawCentredString(300, 710, "545/MENRS/SG/DGENRS du 17/09/04 35.052/2014-MESuprES du 24/11/14 - 10769/2015- MESuprES du 06/02/15")

            canvas.setFont('Helvetica-Bold', 8)
            canvas.drawCentredString(300, 700, "Informatique, Arts et Multimédia")

            canvas.setFont('Helvetica-Bold', 8)
            canvas.drawCentredString(300, 690, "Formation Diplomante et Professionnalisante")

            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.line(40, 630, 555, 630)
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.line(40, 628, 555, 628)

            footer_y = 130
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.line(40, footer_y, 555, footer_y)

            canvas.setFont('Helvetica-Bold', 10)
            canvas.drawCentredString(300, footer_y - 18, "Institut de Arts et des Technologies Avancées (InATA)")
            canvas.setFont('Helvetica', 8)
            canvas.drawCentredString(300, footer_y - 30, "Face Fokontany II L Ankadivato - 101 Antananarivo - Madagascar")
            canvas.setFont('Helvetica', 8)
            canvas.drawCentredString(300, footer_y - 42, "Tel : +261 20 24 244 34 / +261 32 07 260 00 / +261 33 07 260 00 / +261 34 07 260 00 - Email : inata@inata.org")

            canvas.restoreState()

        doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bulletin_s2_{etudiant.nom}_{etudiant.prenom}.pdf"'
        return response

# ---------------- Bulletins d'une classe ----------------
class DownloadBulletinsClasseView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, etudiant_id):
        try:
            etudiant = User.objects.get(id=etudiant_id, role='etud')
        except User.DoesNotExist:
            return Response({"error": "Étudiant non trouvé"}, status=404)

        notes_examens_s2 = Note.objects.filter(
            etudiant=etudiant,
            evaluation__type='examen',
            evaluation__semestre=2
        ).select_related('evaluation__matiere__unite').order_by(
            'evaluation__matiere__unite__id',
            'evaluation__matiere__nom'
        )

        unite_dict = OrderedDict()
        for note in notes_examens_s2:
            unite = note.evaluation.matiere.unite
            unite_nom = unite.nom if unite else '-'
            matiere_nom = note.evaluation.matiere.nom
            note_valeur = note.valeur

            if unite_nom not in unite_dict:
                unite_dict[unite_nom] = []
            unite_dict[unite_nom].append((matiere_nom, note_valeur))

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=30, alignment=1)
        nom_centre_style = ParagraphStyle('NomCentre', parent=styles['Normal'], fontSize=12, spaceAfter=20, alignment=1, textColor=colors.black)
        info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=11, spaceAfter=6)

        elements.append(Paragraph("RELEVÉ DE NOTES", title_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>De : {etudiant.nom} {etudiant.prenom} </b>", nom_centre_style))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"<b>Filière :</b> Informatique", info_style))
        elements.append(Paragraph(f"<b>Niveau :</b> {etudiant.classe.niveau if etudiant.classe else 'Non assigné'}", info_style))
        elements.append(Paragraph(f"<b>Spécialité :</b> Web Master / Infographiste", info_style))
        elements.append(Paragraph(f"<b>Année universitaire :</b> {datetime.now().year} - {datetime.now().year + 1}", info_style))
        elements.append(Spacer(1, 30))

        if unite_dict:
            table_data = [['Unité d\'enseignement', 'Modules', 'Note Examen finale /20']]
            span_indices = []

            current_row = 1
            for unite_nom, modules in unite_dict.items():
                for i, module in enumerate(modules):
                    if i == 0:
                        table_data.append([unite_nom, module[0], f"{module[1]:.2f}"])
                    else:
                        table_data.append(['', module[0], f"{module[1]:.2f}"])
                if len(modules) > 1:
                    span_indices.append((current_row, current_row + len(modules) - 1))
                current_row += len(modules)

            table = Table(table_data, colWidths=[2*inch, 3*inch, 2*inch])
            style = TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])
            for start, end in span_indices:
                style.add('SPAN', (0, start), (0, end))

            table.setStyle(style)
            elements.append(table)
        else:
            elements.append(Paragraph("Aucune note d'examen disponible pour le semestre 2", styles['Normal']))

        elements.append(Spacer(1, 40))
        elements.append(Paragraph("Le Directeur", nom_centre_style))
        elements.append(Spacer(1, 50))
        elements.append(Paragraph("RANDRIAMAHARO Mamy", nom_centre_style))
        date_style = ParagraphStyle('Date', parent=styles['Normal'], fontSize=9, alignment=2)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Éditée le {datetime.now().strftime('%d/%m/%Y')}", date_style))

        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bulletin_s2_{etudiant.nom}_{etudiant.prenom}.pdf"'
        return response
    
class FraisAdminListView(generics.ListAPIView):
    serializer_class = FraisMensuelAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def get_queryset(self):
        return Paiement.objects.filter(statut='Payé').order_by('-date_creation')[:10]

# ---------------- Endpoint pour récupérer les frais non payés ----------------
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def frais_disponibles(request):
    frais = FraisMensuel.objects.filter(etudiant=request.user, est_paye=False)
    data = [{"id": f.id, "mois": f.mois, "montant": f.montant} for f in frais]
    return Response(data)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsAdmin])  # Ajout de IsAdmin
def liste_frais_admin(request):
    frais = FraisMensuel.objects.select_related("etudiant__classe").all()
    data = []
    for f in frais:
        data.append({
            "id": f.id,
            "nom": f.etudiant.nom,
            "prenom": f.etudiant.prenom,
            "classe": f.etudiant.classe.niveau if f.etudiant.classe else "Non défini",
            "mois": f.mois,
            "annee_scolaire": f.annee_scolaire,
            "montant": f.montant,
            "est_paye": f.est_paye,
        })
    return Response(data)

# Professeur
class ProfMatieresListView(generics.ListAPIView):
    serializer_class = MatiereSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Matiere.objects.filter(professeur=user, is_active=True)

class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        
        if hasattr(user, "professeur"):
            qs = qs.filter(matiere__professeur=user)
        
        matiere_id = self.request.query_params.get("matiere")
        if matiere_id:
            qs = qs.filter(matiere_id=matiere_id)
        
        return qs

class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all()
    serializer_class = ProfNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(evaluation__matiere__professeur=user)

    @action(detail=True, methods=['get'], url_path='etudiants')
    def etudiants_par_matiere(self, request, pk=None):
        try:
            matiere = Matiere.objects.get(id=pk, professeur=request.user)
        except Matiere.DoesNotExist:
            return Response({"error": "Matière non trouvée"}, status=404)

        etudiants = User.objects.filter(classe=matiere.classe, role="etud")
        notes = Note.objects.filter(evaluation__matiere=matiere)

        data = []
        for etudiant in etudiants:
            notes_etudiant = notes.filter(etudiant=etudiant)
            notes_list = []
            for note in notes_etudiant:
                notes_list.append({
                    "id": note.id,
                    "valeur": note.valeur,
                    "remarque": note.remarque,
                    "evaluation": {
                        "id": note.evaluation.id,
                        "nom": note.evaluation.nom,
                        "semestre": note.evaluation.semestre
                    }
                })

            data.append({
                "id": etudiant.id,
                "nom": etudiant.nom,
                "prenom": etudiant.prenom,
                "notes": notes_list
            })

        return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def matieres_professeur(request):
    professeur = request.user
    matieres = Matiere.objects.filter(professeur=professeur)
    serializer = MatiereSerializer(matieres, many=True)
    return Response(serializer.data)

class EtudiantsParClasse(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        classe_id = self.kwargs['classe_id']
        return User.objects.filter(classe_id=classe_id, role='etud')

class AbsenceViewSet(viewsets.ModelViewSet):
    queryset = Absence.objects.all()
    serializer_class = AbsenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ["etud", "prof"]:
            return Absence.objects.filter(personne=user)
        return Absence.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        personne = self.request.data.get("personne")

        if user.role == "prof":
            from .models import User
            cible = User.objects.get(id=personne)
            if cible.role != "etud":
                raise PermissionDenied("Un professeur ne peut marquer absent qu'un étudiant.")
        
        elif user.role == "etud":
            raise PermissionDenied("Un étudiant ne peut pas créer une absence.")

        serializer.save(cree_par=user)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if user.role in ["etud", "prof"]:
            if instance.personne == user:
                serializer.save(justifiee=True, motif=self.request.data.get("motif", instance.motif))
            else:
                raise PermissionDenied("Vous ne pouvez justifier que vos propres absences.")
        else:
            serializer.save()

class ProfesseurListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        profs = User.objects.filter(role='prof')
        serializer = UserSerializer(profs, many=True)
        return Response(serializer.data)
    
class AbsenceProfesseurViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AbsenceProfesseurSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Absence.objects.filter(personne__role='etud')

class FraisPaiementDetailView(generics.RetrieveAPIView):
    queryset = FraisPaiement.objects.all()
    serializer_class = FraisPaiementSerializer
    lookup_field = 'classe'
    permission_classes = [IsAuthenticated, IsAdmin]

class PaiementAdminCreateView(generics.CreateAPIView):
    serializer_class = PaiementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Paiement créé avec succès",
                "paiement": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsAdmin])  # Ajout de IsAdmin
def ajouter_paiement(request):
    data = request.data
    etudiant_id = data.get("etudiant")
    mois_list = data.get("mois")
    montant_total = data.get("montant_total")

    if not etudiant_id or not mois_list or not montant_total:
        return Response({"error": "etudiant, mois et montant_total sont obligatoires"}, status=400)

    if not isinstance(mois_list, list):
        mois_list = [mois_list]

    try:
        etudiant = User.objects.get(id=etudiant_id, role='etud')
    except User.DoesNotExist:
        return Response({"error": "Étudiant introuvable"}, status=400)

    now = datetime.now()
    annee_scolaire = f"{now.year}-{now.year + 1}"

    frais_crees = []
    mois_existants = []

    for mois in mois_list:
        frais_existant = FraisMensuel.objects.filter(
            etudiant=etudiant,
            mois=mois,
            annee_scolaire=annee_scolaire
        ).first()

        if frais_existant:
            mois_existants.append(mois)
        else:
            montant_par_mois = float(montant_total) / len(mois_list)
            
            frais = FraisMensuel.objects.create(
                etudiant=etudiant,
                mois=mois,
                montant=montant_par_mois,
                est_paye=True,
                annee_scolaire=annee_scolaire
            )
            frais_crees.append(frais)

    if mois_existants:
        return Response({
            "error": f"Des frais existent déjà pour les mois suivants: {', '.join(mois_existants)}"
        }, status=400)

    if frais_crees:
        paiement = Paiement.objects.create(
            etudiant=etudiant,
            montant_total=montant_total,
            statut="Payé",
            mode_paiement="Liquide"
        )
        paiement.frais_mensuels.set(frais_crees)

    return Response({
        "message": f"Paiement manuel ajouté avec succès pour {len(frais_crees)} mois",
        "paiement_id": paiement.id if frais_crees else None,
        "montant_total": montant_total,
        "mois_payes": [frais.mois for frais in frais_crees],
        "frais_crees": [{
            "id": frais.id,
            "mois": frais.mois,
            "montant": frais.montant,
            "est_paye": frais.est_paye
        } for frais in frais_crees]
    }, status=201)

class AdminPaiementCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Changé

    def post(self, request):
        serializer = PaiementManualSerializer(data=request.data)
        if serializer.is_valid():
            paiement = serializer.save()
            return Response({
                "id": paiement.id,
                "montant_total": paiement.montant_total,
                "statut": paiement.statut,
                "mois": [f.mois for f in paiement.frais_mensuels.all()]
            }, status=status.HTTP_201_CREATED)
        
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AdminEvaluationListView(generics.ListAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def get_queryset(self):
        matiere_id = self.request.query_params.get('matiere')
        return Evaluation.objects.filter(matiere_id=matiere_id)

class AdminNoteListView(generics.ListAPIView):
    serializer_class = NoteAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        matiere_id = self.request.query_params.get('matiere')
        classe_id = self.request.query_params.get('classe')
        return Note.objects.filter(evaluation__matiere_id=matiere_id, etudiant__classe_id=classe_id)
    
class DevoirListCreateView(generics.ListCreateAPIView):
    serializer_class = ExerciceSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin pour création

    def get_queryset(self):
        queryset = Exercice.objects.all().order_by('-date_creation')

        classe_id = self.request.query_params.get('classe')
        if classe_id:
            queryset = queryset.filter(classe_id=classe_id)

        type_devoir = self.request.query_params.get('type')
        if type_devoir:
            queryset = queryset.filter(type=type_devoir)

        return queryset

    def perform_create(self, serializer):
        serializer.save()

def download_devoir(request, filename):
    file_path = os.path.join(settings.MEDIA_ROOT, 'exercices', filename)

    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    raise Http404("Fichier non trouvé")

class DevoirEtudiantView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'etud' or not user.classe:
            return Response([], status=200)

        devoirs = Exercice.objects.filter(classe=user.classe).order_by('-date_creation')
        serializer = ExerciceSerializer(devoirs, many=True)
        return Response(serializer.data)

class MatiereEtudiantView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        etudiant = request.user
        if etudiant.role != 'etud':
            return Response({"detail": "Accès interdit"}, status=403)
        
        matieres = Matiere.objects.filter(classe=etudiant.classe, is_active=True)
        serializer = MatiereSerializer(matieres, many=True)
        return Response(serializer.data)

class NotesEtudiantView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, matiere_id):
        etudiant = request.user
        if etudiant.role != 'etud':
            return Response({"detail": "Accès interdit"}, status=403)
        
        notes = Note.objects.filter(etudiant=etudiant, evaluation__matiere_id=matiere_id)
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def emploi_etudiant(request):
    user = request.user
    if not user.classe:
        return Response({"detail": "L'étudiant n'a pas de classe assignée."}, status=400)
    
    emplois = EmploiDuTemps.objects.filter(classe=user.classe).order_by('jour', 'horaire')
    serializer = EmploiDuTempsSerializer(emplois, many=True)
    
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi']
    horaires = ['08:00-09:00', '09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00']
    
    emploi_structure = {jour: {h: None for h in horaires} for jour in jours}

    for e in serializer.data:
        emploi_structure[e['jour']][e['horaire']] = {
            "id": e['id'],
            "matiere": e['matiere'],
            "matiere_nom": e['matiere_nom'],
            "professeur_nom": e['professeur_nom'],
            "salle_nom": e['salle']
        }

    return Response({
        "classe_id": user.classe.id,
        "classe_nom": str(user.classe),
        "emploi_du_temps": emploi_structure
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def etudiant_info(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data)

# Modification du profil de l'utilisateur

class UpdateProfilView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

class UpdatePhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        photo = request.FILES.get('photo')
        if photo:
            user.photo = photo
            user.save()
            serializer = UserSerializer(user, context={'request': request})
            return Response({'photo': serializer.data['photo']})
        return Response({"detail": "Aucune photo fournie"}, status=400)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_notes_etudiants(request):
    classe_id = request.GET.get("classe")
    matiere_id = request.GET.get("matiere")
    annee = request.GET.get("annee")

    notes = Note.objects.select_related(
        "etudiant__classe", 
        "evaluation__matiere"
    ).all()

    if classe_id:
        notes = notes.filter(etudiant__classe_id=classe_id)

    if matiere_id:
        notes = notes.filter(evaluation__matiere_id=matiere_id)

    if annee:
        notes = notes.filter(etudiant__annee=annee)

    serializer = NoteAdminSerializer(notes, many=True)
    return Response(serializer.data)

class ProfesseursParClasseView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, classe_id):
        profs = User.objects.filter(role='prof', matieres__classe=classe_id).distinct()
        serializer = UserSerializer(profs, many=True)
        return Response(serializer.data)
    
class SalaireClasseMatiereViewSet(viewsets.ModelViewSet):
    queryset = SalaireClasseMatiere.objects.all()
    serializer_class = SalaireClasseMatiereSerializer
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def get_queryset(self):
        user = self.request.user
        if user.role == 'prof':
            return SalaireClasseMatiere.objects.filter(professeur=user)
        return SalaireClasseMatiere.objects.all()
    
class PaiementProfListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Ajout de IsAdmin

    def get(self, request):
        paiements = PaiementProf.objects.all()
        serializer = PaiementProfSerializer(paiements, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data
        data['date_creation'] = datetime.now()
        data['statut'] = 'Payé'
        
        serializer = PaiementProfSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            paiement = PaiementProf.objects.get(id=pk)
        except PaiementProf.DoesNotExist:
            return Response({"error": "Paiement non trouvé"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PaiementProfSerializer(paiement, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET'])
@permission_classes([AllowAny])
def debug_permissions(request):
    """Endpoint de debug pour les permissions"""
    from .permissions import IsAdmin, IsProf
    
    user = request.user
    
    data = {
        'user': {
            'authenticated': user.is_authenticated if user else False,
            'email': user.email if user and user.is_authenticated else None,
        },
        'permissions': {
            'IsAdmin': IsAdmin().has_permission(request, None),
            'IsProf': IsProf().has_permission(request, None),
        },
        'user_attributes': {}
    }
    
    if user and user.is_authenticated:
        data['user_attributes'] = {
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'has_role_attr': hasattr(user, 'role'),
            'role': getattr(user, 'role', 'N/A') if hasattr(user, 'role') else 'No role field',
        }
    
    return Response(data)