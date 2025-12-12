from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import datetime
from rest_framework import serializers, generics
from .models import User
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Classe, Matiere, EmploiDuTemps, Salle, Paiement, FraisMensuel, FraisPaiement, Note, Evaluation, Tache, Evenement, Absence, Exercice, Unite, SalaireClasseMatiere, FraisMensuelProf, PaiementProf

class UserSerializer(serializers.ModelSerializer):
    # Enlever read_only=True pour permettre les mises à jour
    photo = serializers.ImageField(required=False, allow_null=True)
    
    # Ajouter un champ pour l'URL complète de la photo
    photo_url = serializers.SerializerMethodField()
    
    classe = serializers.StringRelatedField(read_only=True)
    classe_id = serializers.PrimaryKeyRelatedField(
        source='classe',
        queryset=Classe.objects.all(),
        required=False,
        allow_null=True
    )
    date_naissance = serializers.DateField(format="%d/%m/%Y", required=False)
    lieu_naissance = serializers.CharField(required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'nom', 'prenom', 'email', 'phone', 'role',
            'is_active', 'password', 'classe', 'classe_id', 
            'annee', 'photo', 'photo_url', 'date_naissance', 'lieu_naissance'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'photo': {'required': False}  # Photo facultative
        }

    def get_photo_url(self, obj):
        """Retourne l'URL complète de la photo"""
        if obj.photo and hasattr(obj.photo, 'url'):
            request = self.context.get('request')
            if request:
                # Construire l'URL absolue
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Ajoute le rôle de l'utilisateur à la réponse
        data['token'] = data.get('access')
        data['role'] = self.user.role if hasattr(self.user, 'role') else None
        data['nom'] = self.user.nom
        data['prenom'] = self.user.prenom
        return data
    
class ClasseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classe
        fields = '__all__'

class SalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salle
        fields = '__all__'

class UniteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unite
        fields = '__all__'

class MatiereSerializer(serializers.ModelSerializer):
    unite_nom = serializers.CharField(source='unite.nom', read_only=True)
    professeur_nom = serializers.CharField(source='professeur.nom', read_only=True)
    professeur_prenom = serializers.CharField(source='professeur.prenom', read_only=True)
    classe_niveau = serializers.CharField(source='classe.niveau', read_only=True)

    class Meta:
        model = Matiere
        fields = ['id', 'nom', 'is_active', 'professeur', 'professeur_nom', 'professeur_prenom', 'classe', 'classe_niveau', 'unite', 'unite_nom']
        
class UtilisateurAbsenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nom', 'prenom', 'email', 'role']

class TacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tache
        fields = '__all__'

class EvenementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evenement
        fields = ['id', 'motif', 'description', 'date_debut', 'date_fin', 'created_by']

class EmploiDuTempsSerializer(serializers.ModelSerializer):
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    professeur_nom = serializers.SerializerMethodField()
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)
    salle_nom = serializers.CharField(source='salle.salle', read_only=True)

    class Meta:
        model = EmploiDuTemps
        fields = ['id', 'classe', 'classe_nom', 'jour', 'horaire', 'matiere', 'matiere_nom', 'professeur_nom', 'salle', 'salle_nom']

    def get_professeur_nom(self, obj):
        if obj.matiere.professeur:
            return f"{obj.matiere.professeur.nom} {obj.matiere.professeur.prenom}"
        return "Non assigné"

class EmploiSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploiDuTemps
        fields = ['classe', 'jour', 'horaire', 'matiere', 'salle']

class FraisMensuelSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisMensuel
        fields = ['id', 'mois', 'annee_scolaire', 'montant', 'est_paye', 'etudiant']

class PaiementSerializer(serializers.ModelSerializer):
    etudiant = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='etud'))
    frais_mensuels = FraisMensuelSerializer(read_only=True, many=True)
    classe = serializers.PrimaryKeyRelatedField(queryset=Classe.objects.all(), required=False)

    class Meta:
        model = Paiement
        fields = [
            'id',
            'etudiant',
            'classe',
            'frais_mensuels',
            'montant_total',
            'mode_paiement',
            'date_creation',
            'statut',
            'stripe_session_id',
        ]
        read_only_fields = ['date_creation', 'statut', 'stripe_session_id']

class FraisPaiementSerializer(serializers.ModelSerializer):
    classe_niveau = serializers.CharField(source="classe.niveau", read_only=True)
    classe_nom = serializers.CharField(source="classe.nom", read_only=True)

    class Meta:
        model = FraisPaiement
        fields = ["id", "classe", "classe_niveau", "classe_nom", "montant"]

class FraisMensuelAdminSerializer(serializers.ModelSerializer):
    nom = serializers.CharField(source='etudiant.nom', read_only=True)
    prenom = serializers.CharField(source='etudiant.prenom', read_only=True)
    mois_payes = serializers.SerializerMethodField()
    classe = serializers.CharField(source='etudiant.classe.niveau', read_only=True)

    class Meta:
        model = Paiement
        fields = ['id', 'nom', 'prenom', 'mois_payes', 'montant_total', 'statut', 'date_creation', 'classe']

    def get_mois_payes(self, obj):
        # Retourne un tableau de chaînes "Mois (Année)"
        return [f"{f.mois} ({f.annee_scolaire})" for f in obj.frais_mensuels.all()]

class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = '__all__'

class ProfNoteSerializer(serializers.ModelSerializer):
    etudiant_nom = serializers.CharField(source='etudiant.nom', read_only=True)
    etudiant_prenom = serializers.CharField(source='etudiant.prenom', read_only=True)
    matiere_nom = serializers.CharField(source='evaluation.matiere.nom', read_only=True)
    evaluation_nom = serializers.CharField(source='evaluation.nom', read_only=True)
    semestre = serializers.IntegerField(source='evaluation.semestre', read_only=True)

    class Meta:
        model = Note
        fields = ['id', 'etudiant', 'etudiant_nom', 'etudiant_prenom', 
                  'evaluation', 'evaluation_nom', 'matiere_nom', 
                  'semestre', 'valeur', 'remarque']
        
class AbsenceSerializer(serializers.ModelSerializer):
    personne_nom = serializers.CharField(source="personne.nom", read_only=True)
    personne_prenom = serializers.CharField(source="personne.prenom", read_only=True)
    personne_role = serializers.CharField(source="personne.role", read_only=True)
    matiere_nom = serializers.CharField(source="matiere.nom", read_only=True)
    personne_classe = serializers.SerializerMethodField(read_only=True)
    personne_classe_id = serializers.SerializerMethodField()

    class Meta:
        model = Absence
        fields = "__all__"
        read_only_fields = ("date", "cree_par")

    def get_personne_classe(self, obj):
        return getattr(getattr(obj.personne, 'classe', None), 'niveau', None)

    def get_personne_classe_id(self, obj):
        return getattr(getattr(obj.personne, 'classe', None), 'id', None)

class AbsenceProfesseurSerializer(serializers.ModelSerializer):
    etudiant_nom = serializers.CharField(source="personne.nom", read_only=True)
    etudiant_prenom = serializers.CharField(source="personne.prenom", read_only=True)
    classe_nom = serializers.CharField(source="personne.classe.niveau", read_only=True)  # 🔥
    classe_id = serializers.IntegerField(source="personne.classe.id", read_only=True)   # 🔥

    class Meta:
        model = Absence
        fields = ["id", "etudiant_nom", "etudiant_prenom", "classe_nom", "classe_id", "date", "justifiee"]

class PaiementManualSerializer(serializers.Serializer):
    etudiant = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='etud'))
    montant_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = serializers.ChoiceField(choices=[('liquide', 'Liquide'), ('cheque', 'Chèque')])
    mois = serializers.ListField(child=serializers.CharField())

    def validate(self, data):
        etudiant = data['etudiant']
        mois_list = data['mois']
        annee_scolaire = f"{datetime.now().year}-{datetime.now().year+1}"

        # Vérifier les mois déjà payés
        mois_deja_payes = FraisMensuel.objects.filter(etudiant=etudiant, mois__in=mois_list, est_paye=True, annee_scolaire=annee_scolaire).values_list('mois', flat=True)
        if mois_deja_payes:
            raise serializers.ValidationError({
                "mois": f"Ces mois sont déjà payés : {', '.join(mois_deja_payes)}"
            })

        return data

    def create(self, validated_data):
        etudiant = validated_data['etudiant']
        montant_total = validated_data['montant_total']
        mode_paiement = validated_data['mode_paiement']
        mois_list = validated_data['mois']

        montant_par_mois = montant_total / len(mois_list) if mois_list else montant_total

        # Créer le paiement
        paiement = Paiement.objects.create(
            etudiant=etudiant,
            montant_total=montant_total,
            mode_paiement=mode_paiement,
            statut='Payé',
        )

        # Créer les FraisMensuel
        frais_objs = []
        for mois in mois_list:
            frais, created = FraisMensuel.objects.get_or_create(
                etudiant=etudiant,
                mois=mois,
                annee_scolaire=f"{datetime.now().year}-{datetime.now().year+1}",
                defaults={'montant': montant_par_mois, 'est_paye': True}
            )
            if not created:
                frais.montant = montant_par_mois
                frais.est_paye = True
                frais.save()
            frais_objs.append(frais)

        paiement.frais_mensuels.set(frais_objs)
        return paiement
    
# Afficher les notes pour l'admin
class NoteAdminSerializer(serializers.ModelSerializer):
    etudiant_nom = serializers.CharField(source='etudiant.nom', read_only=True)
    etudiant_prenom = serializers.CharField(source='etudiant.prenom', read_only=True)
    etudiant_annee = serializers.IntegerField(source='etudiant.annee', read_only=True)
    matiere_nom = serializers.CharField(source='evaluation.matiere.nom', read_only=True)
    evaluation_nom = serializers.CharField(source='evaluation.nom', read_only=True)
    semestre = serializers.IntegerField(source='evaluation.semestre', read_only=True)
    classe = serializers.CharField(source='etudiant.classe.niveau', read_only=True)

    class Meta:
        model = Note
        fields = [
            'id', 'etudiant', 'etudiant_nom', 'etudiant_prenom', 'etudiant_annee',
            'classe', 'evaluation', 'evaluation_nom', 'matiere_nom',
            'semestre', 'valeur', 'remarque'
        ]

class ExerciceSerializer(serializers.ModelSerializer):
    # On affiche les infos complètes en lecture
    classe = ClasseSerializer(read_only=True)
    matiere = MatiereSerializer(read_only=True)
    
    # Mais on autorise l'envoi d'IDs lors de la création
    classe_id = serializers.PrimaryKeyRelatedField(
        queryset=Classe.objects.all(), source='classe', write_only=True
    )
    matiere_id = serializers.PrimaryKeyRelatedField(
        queryset=Matiere.objects.all(), source='matiere', write_only=True
    )

    class Meta:
        model = Exercice
        fields = [
            'id',
            'titre',
            'description',
            'fichier',
            'classe',
            'classe_id',
            'matiere',
            'matiere_id',
            'type',
            'date_creation',
            'date_fin',
            'statut',
        ]

    def get_fichier(self, obj):
        if obj.fichier:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.fichier.url)
        return None

class DevoirEtudiantSerializer(serializers.ModelSerializer):
    classe = serializers.StringRelatedField()
    matiere = serializers.StringRelatedField()

    class Meta:
        model = Exercice
        fields = ['id', 'titre', 'description', 'classe', 'matiere', 'type', 'date_fin', 'fichier', 'statut']

class NoteSerializer(serializers.ModelSerializer):
    evaluation_nom = serializers.CharField(source='evaluation.nom', read_only=True)
    type = serializers.CharField(source='evaluation.type', read_only=True)
    semestre = serializers.IntegerField(source='evaluation.semestre', read_only=True)

    class Meta:
        model = Note
        fields = ['id', 'evaluation_nom', 'valeur', 'type', 'semestre', 'remarque']

class SalaireClasseMatiereSerializer(serializers.ModelSerializer):
    professeur = UserSerializer(read_only=True)
    classe = ClasseSerializer(read_only=True)
    matiere = MatiereSerializer(read_only=True)
    professeur_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='prof'),
        source='professeur',
        write_only=True
    )
    classe_id = serializers.PrimaryKeyRelatedField(
        queryset=Classe.objects.all(),
        source='classe',
        write_only=True
    )
    matiere_id = serializers.PrimaryKeyRelatedField(
        queryset=Matiere.objects.all(),
        source='matiere',
        write_only=True
    )

    class Meta:
        model = SalaireClasseMatiere
        fields = ['id', 'professeur', 'classe', 'matiere', 'montant',
                  'professeur_id', 'classe_id', 'matiere_id']
        
class FraisMensuelProfSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisMensuelProf
        fields = ['id', 'mois', 'salaire']

class PaiementProfSerializer(serializers.ModelSerializer):
    frais_mensuels = FraisMensuelProfSerializer(many=True)

    class Meta:
        model = PaiementProf
        fields = ['id', 'montant_total', 'date_creation', 'statut', 'frais_mensuels']

    def create(self, validated_data):
        frais_data = validated_data.pop('frais_mensuels')
        paiement = PaiementProf.objects.create(**validated_data)
        for frais in frais_data:
            FraisMensuelProf.objects.create(paiement=paiement, **frais)
        return paiement

    def update(self, instance, validated_data):
        frais_data = validated_data.pop('frais_mensuels', None)

        # Mettre à jour les champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Mettre à jour les frais mensuels si fournis
        if frais_data is not None:
            # Supprimer les anciens frais
            instance.frais_mensuels.all().delete()
            # Créer les nouveaux frais
            for frais in frais_data:
                FraisMensuelProf.objects.create(paiement=instance, **frais)

        return instance

