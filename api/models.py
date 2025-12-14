from django.db import models
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from datetime import date

def current_year():
    return datetime.now().year

def annee_scolaire_courante():
    now = datetime.now()
    return f"{now.year}-{now.year+1}"

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email requis')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class Classe(models.Model):
    niveau = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    ordre = models.PositiveIntegerField(default=1, help_text="Ordre de la classe pour la progression")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.niveau

class InvitationLink(models.Model):
    token = models.CharField(max_length=64, unique=True, editable=False)
    role = models.CharField(max_length=50)
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True, blank=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Unite(models.Model):
    nom = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.nom}"

class Matiere(models.Model):
    unite = models.ForeignKey(  
        'Unite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matieres"
    )
    nom = models.CharField(max_length=50)
    professeur = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'prof'}
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        related_name="matieres"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nom} - {self.classe.niveau}"
    
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('prof', 'Prof'),
        ('etud', 'Etud'),
        ('diplome', 'Diplômé'),
    ]
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='etud')
    classe = models.ForeignKey(
        Classe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etudiants"
    )
    annee = models.PositiveIntegerField(default=current_year)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    photo = models.ImageField(upload_to='profile/', null=True, blank=True)
    objects = UserManager()
    adresse = models.CharField(null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=255, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.role})"

class Tache(models.Model):
    PRIORITE_CHOICES = [
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
    ]
    
    STATUT_CHOICES = [
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
    ]
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='taches_creees'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    priorite = models.CharField(max_length=10, choices=PRIORITE_CHOICES, default='moyenne')
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='a_faire')

    def __str__(self):
        return f"{self.titre} ({self.assignee})"

class Evenement(models.Model):
    motif = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    def __str__(self):
        return self.motif
        
class EmploiDuTemps(models.Model):
    JOURS_SEMAINE = [
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
    ]
    
    HORAIRES = [
        ('08:00-09:00', '08:00 - 09:00'),
        ('09:00-10:00', '09:00 - 10:00'),
        ('10:00-11:00', '10:00 - 11:00'),
        ('11:00-12:00', '11:00 - 12:00'),
        ('14:00-15:00', '14:00 - 15:00'),
        ('15:00-16:00', '15:00 - 16:00'),
    ]
    
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='emplois_du_temps')
    horaire = models.CharField(max_length=11, choices=HORAIRES)
    jour = models.CharField(max_length=10, choices=JOURS_SEMAINE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    salle = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ['classe', 'jour', 'horaire']
        ordering = ['classe', 'jour', 'horaire']
    
    def __str__(self):
        return f"{self.classe} - {self.jour} {self.horaire} - {self.matiere.nom}"

class Salle(models.Model):
    salle = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.salle

class FraisPaiement(models.Model):
    classe = models.OneToOneField(
        Classe,
        on_delete=models.CASCADE,
        related_name="frais"
    )
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Montant à payer pour cette classe"
    )

    def __str__(self):
        return f"{self.classe.niveau} - {self.montant} Ar"
        
class FraisMensuel(models.Model):
    etudiant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'etud'},
        null=True,  # temporairement pour migration
        blank=True
    )
    mois = models.CharField(max_length=20)
    annee_scolaire = models.CharField(max_length=9)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    est_paye = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.etudiant.username if self.etudiant else 'Inconnu'} - {self.mois} - {self.montant} Ar"

class Paiement(models.Model):
    etudiant = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'etud'})
    frais_mensuels = models.ManyToManyField(FraisMensuel)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    statut = models.CharField(max_length=20, choices=[
        ('En attente', 'En attente'),
        ('Payé', 'Payé'),
        ('Échoué', 'Échoué')
    ], default='En attente')
    date_creation = models.DateTimeField(auto_now_add=True)
    mode_paiement = models.CharField(max_length=50, blank=True, null=True)

# Salaire des professeurs
class SalaireClasseMatiere(models.Model):
    professeur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'prof'},
        related_name='tarifs_professeur'
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        related_name='tarifs_classe'
    )
    matiere = models.ForeignKey(
        Matiere,
        on_delete=models.CASCADE,
        related_name='tarifs_matiere'
    )
    montant = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('professeur', 'classe', 'matiere')

    def __str__(self):
        return f"{self.professeur} - {self.classe} - {self.matiere} : {self.montant} Ar"

class SalaireMensuel(models.Model):
    professeur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'prof'},
        related_name='salaires_professeur'
    )
    matiere = models.ForeignKey(
        Matiere,
        on_delete=models.CASCADE,
        related_name='salaires_matiere'
    )
    mois = models.CharField(max_length=20)
    annee_scolaire = models.CharField(max_length=9)

    montant = models.DecimalField(max_digits=10, decimal_places=2)
    est_paye = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.professeur.username} - {self.matiere.nom} - {self.mois} - {self.montant} Ar"

from django.db import models
from django.conf import settings

# Optionnel : tu peux avoir un modèle pour chaque mois payé pour un professeur
class FraisMensuelProf(models.Model):
    MOIS_CHOICES = [
        ('Janvier', 'Janvier'),
        ('Février', 'Février'),
        ('Mars', 'Mars'),
        ('Avril', 'Avril'),
        ('Mai', 'Mai'),
        ('Juin', 'Juin'),
        ('Juillet', 'Juillet'),
        ('Août', 'Août'),
        ('Septembre', 'Septembre'),
        ('Octobre', 'Octobre'),
        ('Novembre', 'Novembre'),
        ('Décembre', 'Décembre'),
    ]

    paiement = models.ForeignKey('PaiementProf', on_delete=models.CASCADE, related_name='frais_mensuels')
    mois = models.CharField(max_length=20, choices=MOIS_CHOICES)
    salaire = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.mois} - {self.salaire} Ar"

class PaiementProf(models.Model):
    professeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paiements')
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, default='Payé')  # toujours payé pour ton cas
    # frais_mensuels → lié via le modèle FraisMensuelProf

    def __str__(self):
        return f"{self.professeur} - {self.montant_total} Ar - {self.date_creation.date()}"

SEMESTRES = [
    (1, "Semestre 1"),
    (2, "Semestre 2"),
]

class Evaluation(models.Model):
    SEMESTRES = [
        (1, "Semestre 1"),
        (2, "Semestre 2"),
    ]

    TYPE_CHOICES = [
        ("devoir", "Devoir"),
        ("examen", "Examen Final"),
    ]

    nom = models.CharField(max_length=100)  # ex: "Devoir 1"
    matiere = models.ForeignKey('Matiere', on_delete=models.CASCADE)
    semestre = models.PositiveSmallIntegerField(choices=SEMESTRES, default=1)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="devoir")
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} - {self.matiere.nom} - Semestre {self.semestre} ({self.type})"

class Note(models.Model):
    etudiant = models.ForeignKey('User', on_delete=models.CASCADE)
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="notes")
    valeur = models.FloatField()
    remarque = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.etudiant.nom} - {self.evaluation.nom} : {self.valeur}"
    
class Absence(models.Model):
    personne = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="absences"
    )
    matiere = models.ForeignKey(
        Matiere,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Matière concernée (pour les étudiants uniquement)"
    )
    date = models.DateField(auto_now_add=True)
    justifiee = models.BooleanField(default=False)
    motif = models.TextField(blank=True, null=True)
    cree_par = models.ForeignKey(
        User,
        related_name="absences_crees",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('personne', 'matiere', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.personne.nom} {self.personne.prenom} - {self.date} ({'Justifiée' if self.justifiee else 'Non justifiée'})"
    
class Exercice(models.Model):
    TYPE_CHOICES = [
        ("exercice", "Exercice"),
        ("examen", "Examen"),
    ]
    STATUT_CHOICES = [
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
    ]

    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    fichier = models.FileField(upload_to='exercices/', blank=True, null=True)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    matiere = models.ForeignKey('Matiere', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="exercice")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="en_cours")
    
    def save(self, *args, **kwargs):
        # Mettre automatiquement le statut à "terminé" si la date de fin est passée
        if self.date_fin and timezone.now() >= self.date_fin:
            self.statut = "termine"
        else:
            self.statut = "en_cours"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titre} ({self.type})"
    
