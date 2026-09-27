"""Almaval - socle du portage de l'onboarding en Python sous gestion@, 27.09.2026.

Demande d'Alberto : tous les robots d'Almaval 2.0 tournent sous
gestion@almaval.ch. Les moteurs de nuit du projet Apps Script « Almaval -
RH - Onboarding des collaborateurs » (1nHfUB4qWHahyFh_tmgWaahVFPyTd2q7DOuhQqxeM9ecGSzHPL-GJ-ml5)
tournaient sous am.forte@. Ce module porte ce que ces moteurs ont en
commun, transcrit des fichiers 00 Configuration, 01 Lecture, 13 Mutations
(lecture des registres, valeurs), 16 Courriels, 33/34/35 (charte des
courriels) et 68 (signature du service RH) :

  - CFG, COL, COL_PIECE, COL_COURRIEL, COL_SUIVI... les memes libelles ;
  - lire_onglet(nom) sur Collaborateurs - Gestion, ligne d'en-tetes
    detectee comme ligneDenTete_ (premiere ligne non fusionnee et non
    vide parmi les six premieres) ;
  - lire_onglet_de(ident, nom) sur n'importe quel classeur, en-tetes en
    ligne 1 et colonnes calculees (formule en ligne 1 ou 2) ;
  - ecrire, ecrire_objet, ajouter_ligne, ligne_libre ;
  - mettre_en_file(message) : depot dans « Courriels - File d'attente »
    apres la charte (35) et la signature du service RH (68), a l'identique ;
  - memoire : le remplacant de PropertiesService, un fichier JSON dans le
    dossier de travail des scripts (DOSSIER_TRAVAIL), sous gestion@ ;
  - Drive : enfants_de, creer_dossier, copier_fichier, corbeille, sous
    gestion@ avec supportsAllDrives.

Les valeurs lues sont celles du distributeur : nombres, textes, booleens
et Date (numero de serie avec format), voir outils_zzzzz_distributeur.
Les fonctions date_de / serial_de / en_jour font le pont avec datetime.

Aucun outil MCP ici : les moteurs portes s'appuient dessus et exposent
leurs propres outils et ponts.
"""

import datetime
import html as _html
import json
import re
import threading
import time
import unicodedata
import uuid

from outils_delegation import service
from outils_zzzzz_distributeur import (
    _CACHE_CLASSEURS, _CACHE_GRILLES, Date, FORMAT_DATE, FORMAT_DATE_HEURE, EPOQUE,
    _assurer_dimensions, _batch, _batch_avec_reponse, _classeur, _est_vide, _executer, _feuilles,
    _lire_grille, _oublier, _onglet, _onglet_exige, _requete_cellules, extraire_id,
)

COMPTE_ROBOTS = "gestion@almaval.ch"
SCOPES_DRIVE = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
FUSEAU = datetime.timezone(datetime.timedelta(hours=2))  # Europe/Zurich, voir maintenant()

# ------------------------------------------------ 00 Configuration

CFG = {
    "CLASSEUR_RH": "19RFsMg0XxgqZz101L2zAAFeGC-oyTWBNN5YnmkZvRvE",
    "ONGLET_SAISIE": "Saisie - Collaborateurs",
    "ONGLET_CHAMPS": "Formulaire - Champs",
    "ONGLET_LISTES": "Formulaire - Listes",
    "ONGLET_MODELES": "Modèles - Contrats",
    "ONGLET_TEXTES": "Modèles - Textes contrat",
    "ONGLET_PIECES": "Registre - Pièces",
    "ONGLET_PERSONNES": "Registre - Personnes",
    "ONGLET_ENGAGEMENTS": "Registre - Engagements",
    "ONGLET_SAISIE_ARCHIVE": "Saisie - Archive",
    "ONGLET_SORTIE_ACTIONS": "Sortie - Actions",
    "ONGLET_SORTIE_SUIVI": "Sortie - Suivi",
    "ONGLET_SORTIE_PATIENTS": "Sortie - Continuité clinique",
    "ONGLET_SORTIE_ENTRETIEN": "Sortie - Entretien",
    "ONGLET_SORTIE_MODELES": "Modèles - Documents de sortie",
    "ONGLET_CERTIFICAT_FORMULATIONS": "Certificat - Formulations",
    "ETAPE_SORTIE": 5,
    "LIBELLE_INSTRUCTIONS": "Instructions de départ",
    "MODELE_CERTIFICAT": "1Payal7Ib83oyrJRlMMd6yW7jBAEmoSfvPvapYrZQbMc",
    "CLASSEUR_PATIENTS": "1mxImnYcssgFtMBeSydVlQpbJZiu5S4g2w8aQtwsQMs4",
    "ONGLET_INDEX_PATIENTS": "Index patients",
    "DOSSIER_MODELE": "1Gpdrt5FncaDaXmURIJD-loNMFtZCEP0k",
    "DOSSIER_INTERNES": "1RUDt7moN0rPeSvssUueriYutxiMILcan",
    "DOSSIER_EXTERNES": "1kqnXgvOhS_ukS1Tm2EavASXVgA9zXgP1",
    "DOSSIER_RH_INTERNES": "1Sy_unbBC0kwtT7NntFjCEBR-S-R-hWpW",
    "DOSSIER_RH_EXTERNES": "1kqnXgvOhS_ukS1Tm2EavASXVgA9zXgP1",
    "DOSSIER_CONTRATS": "1lY-d40v336_bM62iofh4uTkcPPZvrb4I",
    "DOSSIER_TRAVAIL": "1N7o8nCzXhtCwxtEvcl3wCceOcN8EPdbX",
    "SOUS_DOSSIERS_RH": ["1. Dossier candidature", "2. Documents contractuels", "3. Documents administratifs",
                         "4. Communications prestataires", "5. Compétences et formations", "6. Absences",
                         "7. Fin des relations"],
    "CLASSEMENT_DES_PIECES": {
        "Contrat de travail signé": "2. Documents contractuels",
        "Avenant signé": "2. Documents contractuels",
        "Convention de formation": "2. Documents contractuels",
        "Diplôme": "5. Compétences et formations",
        "Autorisation de pratique": "5. Compétences et formations",
        "Attestation d'affiliation professionnelle": "5. Compétences et formations",
        "Attestation RC professionnelle": "5. Compétences et formations",
        "Certificat médical": "6. Absences",
        "Instructions de départ signées": "7. Fin des relations",
        "Certificat de travail": "7. Fin des relations",
        "Attestation de l'employeur pour le chômage": "7. Fin des relations",
    },
    "SOUS_DOSSIER_PAR_DEFAUT": "3. Documents administratifs",
    "DOSSIER_SIGNATURES": "1_LeOY2eUUGjopj9d6JtrHoDGHNvieiso",
    "SUFFIXE_SIGNATURE": " - Signature manuscrite",
    "SIGNATAIRE_RH": "Girard Delphine",
    "HAUTEUR_SIGNATURE": 34,
    "EMAIL_PAIE": "salaires@gespower.ch",
    "NOM_PAIE": "Lilia",
    "SUFFIXE_DOSSIER": " - dossier admin personnel",
    "ENTITE_PAR_DEFAUT": "Alma Valens Sàrl",
    "TARIF_PAR_PROFESSION": {
        "Médecin psychiatre": 215.44, "Médecin pédopsychiatre": 215.44, "Médecin": 215.44,
        "Psychologue psychothérapeute": 154.03, "Psychologue": 154.03, "Psychologue assistant": 154.03,
        "Neuropsychologue": 180.63, "Infirmier": 66.113,
    },
    "TARIF_PAR_DEFAUT": 154.03,
    "NOM_MODELE_A_REMPLACER": "Nom Prénom",
    "DEMI_JOURNEES": ["Lundi matin", "Lundi après-midi", "Mardi matin", "Mardi après-midi", "Mercredi matin",
                      "Mercredi après-midi", "Jeudi matin", "Jeudi après-midi", "Vendredi matin",
                      "Vendredi après-midi", "Samedi matin", "Samedi après-midi"],
    "MOIS_PERIODE_ESSAI": 3,
    "RETENUE_BASE": 30, "OPTION_SECRETARIAT": 5, "OPTION_FACTURATION": 5, "OPTION_FACTORING": 2.5,
    "DUREE_INDEPENDANT": 18, "PREAVIS_INDEPENDANT": 6, "HEURES_PAR_TRANCHE_DIX": 3.5,
    "PREAVIS_MANDAT": 6, "LISTE_TYPES_MANDAT": "Type de mandat",
    "URL_APPLICATION": "https://script.google.com/macros/s/AKfycbz_j2QOzQ8L5Iy5CaME3txOcLK9sR9JsNSw6mvV8RCYP7W6BPgiJzmpR8ivvG4qXIhk/exec",
    "DOMAINE_INTERNE": "almaval.ch",
    "JOURS_VALIDITE_JETON": 30, "MINUTES_VALIDITE_CODE": 15, "HEURES_VALIDITE_SESSION": 6,
    "ESSAIS_CODE_MAX": 5, "ENVOIS_CODE_MAX": 5,
    "ONGLET_JOURNAL": "Journal - Accès",
    "EXPEDITEUR": "rh@almaval.ch", "NOM_EXPEDITEUR": "Almaval",
    "EMAIL_RH": "rh@almaval.ch", "SIGNATURE_RH": "Almaval, ressources humaines",
    "ENVOI_AUTOMATIQUE": False,
    "ONGLET_COURRIELS": "Courriels - File d'attente",
    "COURRIELS_VIA_ROBOT": True,
    "MODE_COURRIEL": "Brouillon",
    "CLASSEUR_PLACES": "1WieEc-9hnuvvLmDLjPJ6z-4Ojcx67Cuci_FjgGvDmbE",
    "ONGLET_PLACES": "Places disponibles", "ONGLET_PLACES_ARCHIVE": "Places disponibles - Archive",
    "LIGNE_TECHNIQUE_PLACES": 2,
    "PROFESSIONS_PLACES": ["Médecin psychiatre", "Médecin pédopsychiatre", "Médecin", "Psychologue",
                           "Psychologue psychothérapeute", "Psychologue assistant", "Neuropsychologue"],
    "STATUTS_INTERNES": ["Salarié", "Partner interne"],
    "STATUTS_MANDAT": ["Partner interne", "Partner externe"],
    "PROFESSIONS_GRILLE": ["Psychologue", "Psychologue psychothérapeute", "Psychologue assistant", "Neuropsychologue"],
    "NOM_GRILLE": "Grille de compétences - psychologue",
    "ACTIONS": {
        "CONTRAT": "Générer le contrat", "LIEN": "Renvoyer le lien au collaborateur",
        "VALIDE": "Contrat signé validé", "SORTIE_OUVRIR": "Ouvrir la sortie",
        "SORTIE_PATIENTS": "Ouvrir la continuité clinique", "SORTIE_CLORE": "Clore la sortie",
        "CERTIFICAT": "Générer le certificat de travail",
        "SORTIE_LIEN": "Envoyer le lien de sortie au collaborateur",
        "REPRISE": "Reprendre le dossier d'un ancien collaborateur",
        "VALIDER": "Enregistrer la validation électronique de l'avenant",
        "CHARGER": "Charger un collaborateur en place depuis le registre",
        "INSCRIRE": "Inscrire au registre des engagements",
        "MUTATION": "Enregistrer la mutation",
        "REGENERER": "Régénérer le document de la mutation",
    },
}

COL = {
    "INITIALES": "Initiales", "NOM": "Nom", "PRENOM": "Prénom", "EMAIL_PRIVE": "E-mail privé",
    "EMAIL_ALMAVAL": "E-mail Almaval", "NOM_USAGE_SOUHAITE": "Nom d'usage souhaité",
    "ADRESSE_ALMAVAL_SOUHAITEE": "Adresse Almaval souhaitée", "LANGUE": "Langue de correspondance",
    "ENTITE": "Entité juridique", "DOMAINE": "Domaine", "PROFESSION": "Profession", "STATUT": "Statut",
    "STATUT_COLLAB": "Statut de collaboration", "TYPE_CONTRAT": "Type de contrat", "REMUNERATION": "Rémunération",
    "DATE_DEBUT": "Date début", "FIN_ESSAI": "Date de fin de période d'essai", "EPT_CLINIQUE": "EPT clinique",
    "EPT_ADMIN": "EPT admin", "H_HEBDO": "H hebdo 100% total (h/semaine)", "H_LAMAL": "h hebdo LAMal 100% (h/semaine)",
    "SEMAINES_CONGE": "Semaines de congé (nb/an)", "MOIS": "Mois de salaire (nb/an)",
    "SALAIRE_HORAIRE": "Salaire horaire (% du facturé)", "SALAIRE_POST": "Salaire fixe mensuel post-essai (CHF/mois)",
    "SALAIRE_ESSAI": "Salaire pendant la période d'essai (CHF/mois)", "CONTRIBUTION": "Contribution fixe (CHF/mois)",
    "LIEU_TRAVAIL": "Lieux de travail", "ACTIVITE_ACC": "Activité accessoire",
    "CONDITIONS": "Conditions particulières du contrat", "CAS_PARTICULIER": "Cas particulier du contrat",
    "RETENUE_BASE": "Retenue de base (% du facturé)", "OPT_SECRETARIAT": "Renonciation au secrétariat",
    "OPT_FACTURATION": "Service de facturation", "OPT_FACTORING": "Factoring (% du facturé)",
    "PRESTATIONS": "Prestations réalisées", "DUREE_MOIS": "Durée du contrat (mois)", "TYPE_MANDAT": "Type de mandat",
    "DATE_SORTIE": "Date sortie", "MOTIF_SORTIE": "Motif de sortie", "DELAI_CONGE": "Délai de congé",
    "TYPE_FIN": "Type de fin de contrat", "RESILIATION_RECUE": "Résiliation reçue le",
    "DERNIER_JOUR": "Dernier jour travaillé", "LIBERE": "Libéré de l'obligation de travailler",
    "DELAI_LEGAL": "Délai de congé légal (mois)", "SOLDE_VACANCES": "Solde de vacances à la sortie (jours)",
    "HEURES_SOLDE": "Heures à solder", "CERTIFICAT_REMIS": "Certificat de travail remis le",
    "DOSSIER_RH": "Dossier RH du collaborateur", "ENTRETIEN_SORTIE": "Entretien de sortie fait le",
    "STATUT_SORTIE": "Statut de la sortie", "SORTIE_OUVERTE": "Sortie ouverte le",
    "LIEN_CERTIFICAT": "Lien du certificat de travail",
    "SORTIE_EMAIL": "E-mail privé confirmé à la sortie", "SORTIE_TELEPHONE": "Téléphone privé confirmé à la sortie",
    "SORTIE_RUE": "Adresse de correspondance après la sortie", "SORTIE_NPA": "NPA après la sortie",
    "SORTIE_LOCALITE": "Localité après la sortie", "SORTIE_PAYS": "Pays après la sortie",
    "SORTIE_IBAN": "IBAN confirmé à la sortie", "VACANCES_DECLARE": "Solde de vacances déclaré (jours)",
    "HEURES_DECLARE": "Heures supplémentaires déclarées", "MATERIEL": "Matériel détenu",
    "MATERIEL_DETAIL": "Matériel - détail et numéros d'inventaire",
    "DOSSIERS_PAPIER": "Dossiers papier et matériel de test détenus", "RESTITUTION": "Restitution du matériel prévue le",
    "CERTIF_SOUHAITE": "Certificat de travail souhaité", "CERTIF_EXERGUE": "Éléments à mettre en exergue dans le certificat",
    "DISPO_ENTRETIEN": "Disponibilités pour l'entretien de sortie", "INSTRUCTIONS_LUES": "Instructions de départ acceptées",
    "SORTIE_SOUMISE": "Sortie soumise le", "STATUT_SORTIE_FORM": "Statut du formulaire de sortie",
    "SEXE": "Sexe", "NATIONALITE": "Nationalité", "PERMIS": "Permis de séjour", "TITRE_OBTENU": "Titre obtenu",
    "APPROCHES": "Approches thérapeutiques", "TRANCHES_AGE": "Tranches d'âge des patients",
    "LANGUES_CONSULT": "Langues de consultation",
    "AVS": "N. AVS", "NUMERO_ENGAGEMENT": "N° d'engagement", "CLE_ENGAGEMENT": "Clé engagement",
    "REPRIS_LE": "Dossier repris le", "REPRIS_DEPUIS": "Dossier repris depuis",
    "DONNEES_VERIFIEES": "Données personnelles vérifiées",
    "JETON": "Jeton", "JETON_JUSQUAU": "Jeton valable jusqu'au", "LIEN_FORM": "Lien du formulaire",
    "FORM_ENVOYE": "Formulaire envoyé le", "CONTRAT_GENERE": "Contrat généré le",
    "CONTRAT_SIGNE": "Lien vers le contrat signé", "DATE_SIGNATURE": "Date de signature du contrat",
    "SOUMIS_LE": "Soumis le", "STATUT_SAISIE": "Statut de la saisie", "ACTION_RH": "Action RH",
    "DOSSIER": "Dossier du collaborateur", "MESSAGE": "Message du service",
}

COL_PIECE = {"INITIALES": "Initiales", "NOM": "Nom prénom", "TYPE": "Type de pièce", "FICHIER": "Nom du fichier",
             "LIEN": "Lien Drive", "DEPOSE_LE": "Déposé le", "DEPOSE_PAR": "Déposé par",
             "ECHEANCE": "Échéance de la pièce", "STATUT": "Statut", "REMARQUE": "Remarque"}

COL_COURRIEL = {"CLE": "Clé", "CREE_LE": "Créé le", "TYPE": "Type de message", "INITIALES": "Initiales",
                "NOM": "Nom prénom", "DESTINATAIRE": "Destinataire", "OBJET": "Objet", "CORPS": "Corps HTML",
                "PIECE_LIEN": "Pièce jointe", "PIECE_NOM": "Nom de la pièce jointe", "MODE": "Mode",
                "STATUT": "Statut", "TRAITE_LE": "Traité le", "ID_GMAIL": "Identifiant Gmail",
                "MESSAGE": "Message du robot"}

COL_JOURNAL = {"HORODATAGE": "Horodatage", "INITIALES": "Initiales", "NOM": "Nom prénom", "EVENEMENT": "Événement",
               "ADRESSE": "Adresse utilisée", "DETAIL": "Détail"}

COL_ENTRETIEN = {"INITIALES": "Initiales", "NOM": "Nom prénom", "REMPLI_LE": "Rempli le",
                 "TRANSMISSION": "Transmission à la direction"}

COL_SORTIE = {"ORDRE": "Ordre", "ETAPE": "Étape", "ACTION": "Action", "RESPONSABLE": "Responsable",
              "STATUTS": "Statuts concernés", "PROFESSIONS": "Professions concernées",
              "JOURS": "Jours par rapport à la sortie", "OBLIGATOIRE": "Obligatoire", "ACTIF": "Actif"}

COL_MODELE_SORTIE = {"ORDRE": "Ordre", "NOM": "Nom du modèle", "ID": "ID du document", "STATUTS": "Statuts concernés",
                     "TYPES_FIN": "Types de fin de contrat concernés", "PROFESSIONS": "Professions concernées",
                     "LIBELLE": "Libellé du document", "MOMENT": "Moment de production", "ACTIF": "Actif"}

COL_SUIVI = {"INITIALES": "Initiales", "NOM": "Nom prénom", "ORDRE": "Ordre", "ETAPE": "Étape", "ACTION": "Action",
             "RESPONSABLE": "Responsable", "ECHEANCE": "Échéance", "ETAT": "État", "FAIT_LE": "Fait le",
             "FAIT_PAR": "Fait par", "REMARQUE": "Remarque"}

COL_CONTINUITE = {"INITIALES": "Initiales du sortant", "NOM": "Nom prénom du sortant", "ID_PATIENT": "Identifiant patient",
                  "PATIENT": "Patient", "PRESTATION": "Prestation en cours", "DECISION": "Décision",
                  "REPRIS_PAR": "Repris par", "DATE_REPRISE": "Date de reprise", "INFORME_LE": "Patient informé le",
                  "REMARQUE": "Remarque"}

# 13 Mutations
CFG_MUT = {
    "CLASSEUR_EFFECTIF": "1gqCyEB8D5tJDlHQN3DPc66yQ6WfUIt1E9O1ROGiN15c",
    "ONGLET_ENGAGEMENTS": "Registre - Engagements", "ONGLET_PERSONNES": "Registre - Personnes",
    "ONGLET_MUTATIONS": "Mutations", "ONGLET_LISTES_EFFECTIF": "Listes", "ONGLET_REGLES": "Mutations - Règles",
    "MODELE_SOURCE_AVENANT": "1mJDqwdL6fg6zBzAwEyF5VmEKm0h59Jese4w70OknFew",
    "FAMILLE_MODELE_AVENANT": "AVENANT", "NOM_MODELE_AVENANT": "XYZ - Almaval - Modèle Avenant au contrat - Mutation",
    "LIEU_LETTRE": "Crissier", "HEURE_PASSAGE": 3, "SEMAINES_TRAVAILLEES_HORS_CONGE": 50,
    "ORIGINE_SAISIE": "Saisie - Collaborateurs", "RENSEIGNE_PAR": "Saisie RH",
}
ID_GESTION = CFG["CLASSEUR_RH"]
ID_EFFECTIF = CFG_MUT["CLASSEUR_EFFECTIF"]
ID_BDU = "1W35AtQw9U2Wn2MofCxKAyNbZykb4Zr375RPS8CzE-BE"

COL_MUT = {"DATE_EFFET": "Date d'effet de la mutation", "MOTIF": "Motif de la mutation",
           "ENREGISTREE_LE": "Mutation enregistrée le", "SUITE": "Suite de la mutation",
           "LIEN_AVENANT": "Lien de l'avenant", "ECART": "Écart avec le registre", "INSCRIT_LE": "Inscrit au registre le"}

COL_MUTATIONS = {"CLE_MUTATION": "Clé mutation", "CLE": "Clé engagement", "DATE": "Date d'effet",
                 "TYPE": "Type de mutation", "SUITE": "Suite de la mutation", "ETAT": "État de la mutation",
                 "APPLIQUEE": "Appliquée le", "LIEN_AVENANT": "Lien de l'avenant", "MOTIF": "Motif",
                 "SIGNE": "Contrat ou avenant signé", "PIECE": "Lien de la pièce", "SAISI_PAR": "Saisi par",
                 "DATE_SAISIE": "Date de saisie", "RENSEIGNE_PAR": "Renseigné par", "COMMENTAIRE": "Commentaire",
                 "DETAIL": "Détail de la mutation", "VALEURS": "Valeurs à reporter au registre",
                 "ANCIEN_SALAIRE": "Ancien salaire mensuel", "NOUVEAU_SALAIRE": "Nouveau salaire mensuel",
                 "ANCIEN_TAUX": "Ancien taux d'activité", "NOUVEAU_TAUX": "Nouveau taux d'activité",
                 "IMPACT": "Impact salaire"}

ETATS_MUT = {"A_APPLIQUER": "À appliquer", "APPLIQUEE": "Appliquée", "NOUVEAU_CONTRAT": "Nouveau contrat requis",
             "ANNULEE": "Annulée"}
SUITES_MUT = ["Nouveau contrat", "Avenant", "Cahier des charges", "Validation par clic", "Registre seul", "Inscription seule"]
PRIORITE_TYPES_MUT = ["Changement de contrat", "Changement de fonction", "Changement de statut",
                      "Hausse du taux d'activité", "Baisse du taux d'activité", "Hausse du salaire", "Baisse du salaire",
                      "Changement du cahier des charges", "Obtention ou changement d'habilitation",
                      "Changement de mandat", "Changement de lieu ou d'horaire", "Changement de nom", "Sortie",
                      "Autre mutation"]
SECTIONS_AVENANT = ["Contrat", "Fonction", "Taux d'activité", "Temps de travail", "Rémunération", "Cahier des charges"]
SERVICES_EPT = ["Clinique", "Comptabilité", "Direction générale", "Finances", "Formation", "IT", "Logistique",
                "Opérations", "Proximité", "Qualité", "Relations", "RH", "Secrétariat", "Service social"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"]

_verrou = threading.RLock()


# ------------------------------------------------ temps

def maintenant():
    """L'heure de Zurich. Le serveur tourne en UTC ; l'heure d'ete ou d'hiver
    est calculee sans dependance externe (regle europeenne)."""
    utc = datetime.datetime.utcnow()
    an = utc.year
    def dernier_dimanche(mois):
        d = datetime.datetime(an, mois, 31)
        return d - datetime.timedelta(days=(d.weekday() + 1) % 7)
    debut = dernier_dimanche(3).replace(hour=1)
    fin = dernier_dimanche(10).replace(hour=1)
    decalage = 2 if debut <= utc < fin else 1
    return utc + datetime.timedelta(hours=decalage)


def aujourdhui():
    return maintenant().strftime("%d.%m.%Y")


def horodatage():
    return maintenant().strftime("%d.%m.%Y %H:%M")


def serial_de(d):
    """datetime ou date -> Date (numero de serie Sheets), format date ou date heure."""
    if isinstance(d, datetime.datetime):
        s = Date((d - EPOQUE).total_seconds() / 86400.0)
        s.format = FORMAT_DATE_HEURE if (d.hour or d.minute or d.second) else FORMAT_DATE
        return s
    if isinstance(d, datetime.date):
        s = Date((datetime.datetime(d.year, d.month, d.day) - EPOQUE).total_seconds() / 86400.0)
        s.format = FORMAT_DATE
        return s
    return d


def date_de(v):
    """Une valeur de cellule -> datetime.datetime, ou None. Comme dateOuNullePermis_
    et dateOuNulle_ : Date de Sheets, numero de serie, jj.mm.aaaa, jj/mm/aaaa, iso."""
    if isinstance(v, Date):
        return EPOQUE + datetime.timedelta(days=float(v))
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if 20000 < float(v) < 80000:
            return EPOQUE + datetime.timedelta(days=float(v))
        return None
    texte = str("" if v is None else v).strip()
    if not texte:
        return None
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:\s+(\d{1,2}):(\d{2}))?$", texte)
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                                     int(m.group(4) or 0), int(m.group(5) or 0))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?", texte)
    if m:
        try:
            return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                     int(m.group(4) or 0), int(m.group(5) or 0))
        except ValueError:
            return None
    return None


def debut_de_jour(d):
    return datetime.datetime(d.year, d.month, d.day)


def en_jour(v):
    """jj.mm.aaaa si la valeur est une date, sinon le texte tel quel."""
    d = date_de(v) if isinstance(v, (Date, int, float)) and not isinstance(v, bool) else None
    if d is None:
        return str("" if v is None else v)
    return d.strftime("%d.%m.%Y")


def jour_iso(d):
    return d.strftime("%Y-%m-%d") if d else ""


def date_longue(d):
    return str(d.day) + " " + MOIS_FR[d.month - 1] + " " + str(d.year)


# ------------------------------------------------ textes

_ACCENTS = re.compile("[̀-ͯ]")


def normaliser(v):
    """normaliser_ telle qu'elle GAGNE dans le projet (« 07 Charte », declaree
    apres « 01 Lecture ») : minuscules, espaces reduites, ACCENTS CONSERVES.
    Un None ou un undefined d'Apps Script donnait « null »/« undefined » par
    String() ; ici la chaine vide, ce qui ne change aucune comparaison utile."""
    if v is None:
        return ""
    return re.sub(r"\s+", " ", texte(v).strip().lower())


def normaliser_sans_accent(v):
    """La version de « 01 Lecture », sans accents, pour les moteurs qui la
    citaient explicitement avant « 07 »."""
    t = str("" if v is None else v).strip().lower()
    return _ACCENTS.sub("", unicodedata.normalize("NFD", t))


def meme_texte(a, b):
    return normaliser(a) == normaliser(b)


VOC = {"POLE": "Pôle", "ANCIEN": "Sous-service", "ONGLET_POLES": "Services - Pôles",
       "ONGLET_POLES_ANCIEN": "Services - Sous-services"}


def voc_alias_deux_sens(o):
    """« 55 » : le pole sous les deux orthographes, dans les deux sens."""
    if not isinstance(o, dict):
        return o
    a_p, a_a = VOC["POLE"] in o, VOC["ANCIEN"] in o
    if a_p and not a_a:
        o[VOC["ANCIEN"]] = o[VOC["POLE"]]
    elif a_a and not a_p:
        o[VOC["POLE"]] = o[VOC["ANCIEN"]]
    return o


def voc_pole(ligne):
    if not ligne:
        return ""
    v = ligne.get(VOC["POLE"])
    if v is None or str(v).strip() == "":
        v = ligne.get(VOC["ANCIEN"])
    return "" if v is None else str(v).strip()


def texte(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Date):
        return en_jour(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def est_actif(v):
    if v is True:
        return True
    return str("" if v is None else v).strip().lower() == "x"


def liste_de_texte(v):
    return [x.strip() for x in str("" if v is None else v).split(",") if x.strip() != ""]


def nom_de_fichier(t):
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]', " ", str(t or ""))).strip()


def echapper(t):
    return str("" if t is None else t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cellule_vide_mut(v):
    return v is None or v == "" or str(v).strip() == "" or str(v).strip() == "-"


def saisie_vide(v):
    return v is None or v == "" or str(v).strip() == ""


def nombre_ou_nul(v):
    if cellule_vide_mut(v):
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[’'\s]", "", str(v)).replace("%", "").replace(",", ".")
    try:
        n = float(t)
    except ValueError:
        return None
    if "%" in str(v):
        n = n / 100
    return n


def nombre_ou_zero(v):
    n = nombre_ou_nul(v)
    return 0 if n is None else n


def nombre_js(n):
    """Un nombre ecrit comme String(n) en JavaScript : 4 et non 4.0."""
    if n is None:
        return ""
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return repr(float(n)) if isinstance(n, float) else str(n)


# ------------------------------------------------ lecture des onglets

class Onglet:
    """L'objet de travail de lireOnglet_ : entetes, lignes (dict par en-tete,
    plus _ligne), calculees, colonne(nom), existe(nom)."""

    def __init__(self, ident, prop, entetes, lignes, ligne_entete, calculees=None, grille=None):
        self.id = ident
        self.prop = prop
        self.titre = prop["title"]
        self.sheet_id = prop["sheetId"]
        self.entetes = entetes
        self.lignes = lignes
        self.ligne_entete = ligne_entete
        self.premiere_ligne = ligne_entete + 1
        self.calculees = calculees or {}
        self.grille = grille or []
        self.index = {}
        for i, e in enumerate(entetes):
            if e and e not in self.index:
                self.index[e] = i

    def colonne(self, nom):
        if nom not in self.index:
            raise ValueError("Colonne introuvable dans « " + self.titre + " » : " + str(nom))
        return self.index[nom] + 1

    def existe(self, nom):
        return nom in self.index

    def derniere_ligne(self):
        return len(self.grille)

    def lien(self):
        return "https://docs.google.com/spreadsheets/d/" + self.id + "/edit#gid=" + str(self.sheet_id)


_CACHE_FUSIONS = {}


def _fusions(ident):
    if ident not in _CACHE_FUSIONS:
        rep = _executer(_feuilles().get(spreadsheetId=ident, fields="sheets(properties(sheetId,title),merges)"))
        _CACHE_FUSIONS[ident] = {s["properties"]["sheetId"]: s.get("merges", []) for s in rep.get("sheets", [])}
    return _CACHE_FUSIONS[ident]


def ligne_d_en_tete(ident, prop, grille):
    """ligneDenTete_ : premiere ligne, parmi les six premieres, dont la
    cellule A n'est pas fusionnee et n'est pas vide ; 1 a defaut."""
    fusions = _fusions(ident).get(prop["sheetId"], [])
    maxi = min(6, max(len(grille), 1))
    for r in range(1, maxi + 1):
        fusionnee = any(f.get("startRowIndex", 0) <= r - 1 < f.get("endRowIndex", 0)
                        and f.get("startColumnIndex", 0) <= 0 < f.get("endColumnIndex", 0) for f in fusions)
        if fusionnee:
            continue
        v = grille[r - 1][0] if r - 1 < len(grille) and grille[r - 1] else ""
        if str(v).strip() == "":
            continue
        return r
    return 1


def _formules_en_tete(ident, titre, largeur):
    """Les colonnes portant une formule en ligne 1 ou 2, comme lireOngletDe_."""
    plage = "'" + titre.replace("'", "''") + "'!1:2"
    rep = _executer(_feuilles().values().get(spreadsheetId=ident, range=plage, valueRenderOption="FORMULA"))
    calculees = set()
    for l in rep.get("values", []):
        for i, v in enumerate(l):
            if isinstance(v, str) and v.startswith("="):
                calculees.add(i)
    return calculees


def lire_onglet_de(ident, nom, rafraichir=False, avec_calculees=True):
    """lireOngletDe_ : en-tetes en ligne 1, colonnes calculees relevees."""
    ident = extraire_id(ident)
    classeur = _classeur(ident)
    prop = _onglet_exige(classeur, nom)
    if rafraichir:
        _oublier(ident, prop["title"])
    grille = _lire_grille(ident, prop["title"])
    entetes = [str(e).strip() if not isinstance(e, float) else texte(e) for e in (grille[0] if grille else [])]
    calculees = {}
    if avec_calculees:
        for i in _formules_en_tete(ident, prop["title"], len(entetes)):
            if i < len(entetes) and entetes[i]:
                calculees[entetes[i]] = True
    lignes = []
    for i, l in enumerate(grille[1:]):
        obj = {"_ligne": i + 2}
        for j, e in enumerate(entetes):
            if e and e not in obj:
                obj[e] = l[j] if j < len(l) else ""
        voc_alias_deux_sens(obj)
        lignes.append(obj)
    o = Onglet(ident, prop, entetes, lignes, 1, calculees, grille)
    voc_alias_deux_sens(o.index)
    return o


def lire_onglet(nom, rafraichir=False):
    """lireOnglet_ : un onglet de Collaborateurs - Gestion, ligne d'en-tetes
    detectee par les fusions."""
    classeur = _classeur(ID_GESTION)
    prop = _onglet_exige(classeur, nom)
    if rafraichir:
        _oublier(ID_GESTION, prop["title"])
    grille = _lire_grille(ID_GESTION, prop["title"])
    le = ligne_d_en_tete(ID_GESTION, prop, grille)
    entetes = [texte(e).strip() for e in (grille[le - 1] if len(grille) >= le else [])]
    lignes = []
    for i, l in enumerate(grille[le:]):
        obj = {"_ligne": i + le + 1}
        for j, e in enumerate(entetes):
            if e:
                obj[e] = l[j] if j < len(l) else ""
        lignes.append(obj)
    return Onglet(ID_GESTION, prop, entetes, lignes, le, {}, grille)


def lire_onglet_effectif(nom, rafraichir=False):
    return lire_onglet_de(ID_EFFECTIF, nom, rafraichir)


def oublier_tout():
    _CACHE_GRILLES.clear()
    _CACHE_CLASSEURS.clear()
    _CACHE_FUSIONS.clear()


# ------------------------------------------------ ecriture

def ecrire(onglet, numero_ligne, nom_colonne, valeur):
    """ecrire_ : une cellule, colonne designee par son libelle."""
    c = onglet.colonne(nom_colonne)
    _assurer_dimensions(onglet.id, onglet.prop, lignes=numero_ligne)
    _batch(onglet.id, _requete_cellules(onglet.sheet_id, numero_ligne - 1, c - 1, [[valeur]]))
    _oublier(onglet.id, onglet.titre)


def ecrire_objet(onglet, numero_ligne, objet):
    """ecrireObjet_ : un dict { en-tete: valeur }, colonnes calculees et
    en-tetes absents sautes, par blocs contigus, en un seul batch."""
    cellules = []
    for i, e in enumerate(onglet.entetes):
        if not e or onglet.calculees.get(e):
            continue
        if e not in objet:
            continue
        cellules.append((i, objet[e]))
    cellules.sort()
    if not cellules:
        return 0
    _assurer_dimensions(onglet.id, onglet.prop, lignes=numero_ligne)
    requetes, bloc, debut = [], [], None
    for c, v in cellules:
        if bloc and c != debut + len(bloc):
            requetes.append(_requete_cellules(onglet.sheet_id, numero_ligne - 1, debut, [bloc]))
            bloc, debut = [], None
        if not bloc:
            debut = c
        bloc.append("" if v is None else v)
    if bloc:
        requetes.append(_requete_cellules(onglet.sheet_id, numero_ligne - 1, debut, [bloc]))
    _batch(onglet.id, requetes)
    _oublier(onglet.id, onglet.titre)
    return len(cellules)


def ecrire_lignes(onglet, numero_ligne, colonne, lignes):
    """Un bloc rectangulaire, comme getRange(...).setValues(lignes)."""
    if not lignes:
        return
    _assurer_dimensions(onglet.id, onglet.prop, lignes=numero_ligne + len(lignes) - 1,
                        colonnes=colonne + max(len(l) for l in lignes) - 1)
    _batch(onglet.id, _requete_cellules(onglet.sheet_id, numero_ligne - 1, colonne - 1, lignes))
    _oublier(onglet.id, onglet.titre)


def ajouter_ligne(onglet, valeurs):
    """appendRow : apres la derniere ligne portant une valeur. Rend le numero de la ligne ecrite."""
    numero = onglet.derniere_ligne() + 1
    ecrire_lignes(onglet, numero, 1, [list(valeurs)])
    onglet.grille.append(list(valeurs))
    return numero


def ligne_libre(onglet, colonne_cle):
    """ligneLibre_ : apres la derniere ligne portant une valeur dans la colonne cle."""
    derniere = onglet.ligne_entete
    for l in onglet.lignes:
        if str("" if l.get(colonne_cle) is None else l.get(colonne_cle)).strip() != "":
            derniere = l["_ligne"]
    return derniere + 1


def supprimer_lignes(onglet, numeros):
    """Supprime des lignes (numeros 1 base), de bas en haut, en un batch."""
    if not numeros:
        return
    requetes = [{"deleteDimension": {"range": {"sheetId": onglet.sheet_id, "dimension": "ROWS",
                                               "startIndex": n - 1, "endIndex": n}}} for n in sorted(set(numeros), reverse=True)]
    _batch(onglet.id, requetes)
    onglet.prop.get("gridProperties", {})["rowCount"] = onglet.prop.get("gridProperties", {}).get("rowCount", 0) - len(set(numeros))
    _oublier(onglet.id, onglet.titre)


# ------------------------------------------------ Drive

TYPE_DOSSIER = "application/vnd.google-apps.folder"
TYPE_RACCOURCI = "application/vnd.google-apps.shortcut"


def drive():
    return service("drive", "v3", SCOPES_DRIVE, COMPTE_ROBOTS)


def enfants_de(id_dossier):
    """Enfants directs, dossiers puis fichiers, comme enfantsDe_."""
    liste, jeton = [], None
    while True:
        rep = _executer(drive().files().list(
            q="'" + id_dossier + "' in parents and trashed = false", pageSize=1000, pageToken=jeton,
            supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives",
            fields="nextPageToken,files(id,name,mimeType,shortcutDetails,modifiedTime,createdTime,size,md5Checksum,webViewLink)"))
        liste.extend(rep.get("files", []))
        jeton = rep.get("nextPageToken")
        if not jeton:
            break
    dossiers = [f for f in liste if f["mimeType"] == TYPE_DOSSIER]
    fichiers = [f for f in liste if f["mimeType"] != TYPE_DOSSIER]
    return dossiers + fichiers


def fichier(ident, champs="id,name,mimeType,parents,trashed,webViewLink,modifiedTime,createdTime,size"):
    return _executer(drive().files().get(fileId=ident, supportsAllDrives=True, fields=champs))


def creer_dossier(nom, id_parent):
    return _executer(drive().files().create(body={"name": nom, "mimeType": TYPE_DOSSIER, "parents": [id_parent]},
                                            supportsAllDrives=True, fields="id,name"))


def copier_fichier(id_fichier, nom, id_parent):
    return _executer(drive().files().copy(fileId=id_fichier, body={"name": nom, "parents": [id_parent]},
                                          supportsAllDrives=True, fields="id,name,webViewLink"))


def deplacer_fichier(id_fichier, id_parent):
    meta = fichier(id_fichier, "id,parents")
    return _executer(drive().files().update(fileId=id_fichier, addParents=id_parent,
                                            removeParents=",".join(meta.get("parents", [])),
                                            supportsAllDrives=True, fields="id,name,parents"))


def renommer_fichier(id_fichier, nom):
    return _executer(drive().files().update(fileId=id_fichier, body={"name": nom}, supportsAllDrives=True, fields="id,name"))


def corbeille(id_fichier):
    return _executer(drive().files().update(fileId=id_fichier, body={"trashed": True}, supportsAllDrives=True, fields="id"))


def partager_lecture(id_fichier, adresse):
    try:
        _executer(drive().permissions().create(fileId=id_fichier, supportsAllDrives=True, sendNotificationEmail=False,
                                               body={"type": "user", "role": "reader", "emailAddress": adresse}))
        return True
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------ memoire (PropertiesService)

NOM_MEMOIRE = "Mémoire du robot onboarding (Python, gestion@).json"
_MEMOIRE = {"id": None, "donnees": None}


def _fichier_memoire():
    if _MEMOIRE["id"]:
        return _MEMOIRE["id"]
    rep = _executer(drive().files().list(
        q="'" + CFG["DOSSIER_TRAVAIL"] + "' in parents and name = '" + NOM_MEMOIRE.replace("'", "\\'") + "' and trashed = false",
        supportsAllDrives=True, includeItemsFromAllDrives=True, corpora="allDrives", fields="files(id)"))
    fichiers = rep.get("files", [])
    if fichiers:
        _MEMOIRE["id"] = fichiers[0]["id"]
        return _MEMOIRE["id"]
    from googleapiclient.http import MediaInMemoryUpload
    rep = _executer(drive().files().create(
        body={"name": NOM_MEMOIRE, "parents": [CFG["DOSSIER_TRAVAIL"]], "mimeType": "application/json"},
        media_body=MediaInMemoryUpload(b"{}", mimetype="application/json"), supportsAllDrives=True, fields="id"))
    _MEMOIRE["id"] = rep["id"]
    return _MEMOIRE["id"]


def memoire_lire_tout():
    if _MEMOIRE["donnees"] is None:
        ident = _fichier_memoire()
        brut = _executer(drive().files().get_media(fileId=ident, supportsAllDrives=True))
        try:
            _MEMOIRE["donnees"] = json.loads(brut.decode("utf-8") if isinstance(brut, bytes) else brut) or {}
        except Exception:  # noqa: BLE001
            _MEMOIRE["donnees"] = {}
    return _MEMOIRE["donnees"]


def memoire_lire(cle, defaut=None):
    return memoire_lire_tout().get(cle, defaut)


def _memoire_sauver():
    from googleapiclient.http import MediaInMemoryUpload
    ident = _fichier_memoire()
    contenu = json.dumps(_MEMOIRE["donnees"], ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
    _executer(drive().files().update(fileId=ident, media_body=MediaInMemoryUpload(contenu, mimetype="application/json"),
                                     supportsAllDrives=True, fields="id"))


def memoire_ecrire(cle, valeur):
    with _verrou:
        donnees = memoire_lire_tout()
        donnees[cle] = valeur
        _memoire_sauver()


def memoire_ecrire_plusieurs(paires):
    with _verrou:
        donnees = memoire_lire_tout()
        donnees.update(paires)
        _memoire_sauver()


def memoire_effacer(prefixe):
    with _verrou:
        donnees = memoire_lire_tout()
        cles = [k for k in donnees if k.startswith(prefixe)]
        for k in cles:
            donnees.pop(k, None)
        if cles:
            _memoire_sauver()
        return len(cles)


# ------------------------------------------------ 35 charte des courriels

STYLE_MESSAGE = {
    "corps": "font-family:verdana,sans-serif;font-size:10px;line-height:1.5;color:#666666;",
    "para": "margin:0 0 10px 0;font-family:verdana,sans-serif;font-size:10px;color:#666666;",
    "titre": "margin:16px 0 6px 0;font-family:verdana,sans-serif;font-size:10px;color:#128da0;font-weight:bold;",
    "liste": "margin:0 0 10px 0;padding-left:20px;font-family:verdana,sans-serif;font-size:10px;color:#666666;",
    "puce": "margin:0 0 4px 0;font-family:verdana,sans-serif;font-size:10px;color:#666666;",
    "lien": "font-family:verdana,sans-serif;font-size:10px;color:#128da0;",
    "bouton": "background:#128da0;color:#ffffff;padding:10px 18px;text-decoration:none;border-radius:4px;"
              "display:inline-block;font-family:verdana,sans-serif;font-size:10px;",
    "mention": "margin:0;font-family:verdana,sans-serif;font-size:10px;color:#666666;",
    "table": "border-collapse:collapse;margin:14px 0;max-width:520px;",
    "th": "font-family:verdana,sans-serif;font-size:10px;color:#128da0;font-weight:bold;text-align:left;"
          "padding:6px 12px;border:1px solid #e2e2e2;border-bottom:1px solid #128da0;",
    "tdGauche": "padding:6px 12px;border:1px solid #e2e2e2;font-family:verdana,sans-serif;font-size:10px;color:#666666;font-weight:bold;",
    "tdDroite": "padding:6px 12px;border:1px solid #e2e2e2;font-family:verdana,sans-serif;font-size:10px;color:#666666;",
}

# Point d'extension : la phrase lisible des puces de presence et de lieu
# (« 31 »/« 34 », phraseDuChangementAv_), posee par le module des mutations.
PHRASE_LISIBLE = {"fn": None}


def cle_al(v):
    t = re.sub(r"\s+", " ", str("" if v is None else v).strip().lower())
    return _ACCENTS.sub("", unicodedata.normalize("NFD", t))


def desechapper_al(v):
    return str("" if v is None else v).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def prenom_de(nom_prenom):
    bouts = str(nom_prenom or "").strip().split()
    return " ".join(bouts[1:]) if len(bouts) > 1 else (bouts[0] if bouts else "")


def retourner_paire_av(compose, nom_legal, premier_prenom_legal):
    c = str(compose or "").strip()
    if not c or " " not in c:
        return None
    if nom_legal and len(c) > len(nom_legal) + 1 and c[:len(nom_legal)].lower() == nom_legal.lower() and c[len(nom_legal)] == " ":
        return {"nom": nom_legal, "prenom": c[len(nom_legal):].strip()}
    if premier_prenom_legal and len(c) > len(premier_prenom_legal) + 1 \
            and c[-len(premier_prenom_legal):].lower() == premier_prenom_legal.lower() \
            and c[len(c) - len(premier_prenom_legal) - 1] == " ":
        nom = c[:len(c) - len(premier_prenom_legal) - 1].strip()
        if nom:
            return {"nom": nom, "prenom": premier_prenom_legal}
    return None


def appellation_separee_av(params):
    ligne = (params or {}).get("ligne") or {}
    engagement = (params or {}).get("engagement") or {}
    personne = (params or {}).get("personne") or {}
    nom_legal = str((params or {}).get("nom") or "").strip()
    prenom_legal = str((params or {}).get("prenom") or "").strip()
    premier = prenom_legal.split()[0] if prenom_legal.split() else ""
    prenom_u = str(ligne.get("Prénom d'usage") or personne.get("Prénom d'usage") or "").strip()
    if prenom_u:
        nom_seul = str(ligne.get("Nom d'usage") or personne.get("Nom d'usage") or "").strip()
        if nom_seul and " " in nom_seul:
            paire = retourner_paire_av(nom_seul, nom_legal, premier)
            nom_seul = paire["nom"] if paire else ""
        return {"prenom": prenom_u, "nom": nom_seul or nom_legal}
    candidats = [str(ligne.get("Nom d'usage") or "").strip(), str(personne.get("Nom d'usage") or "").strip(),
                 str(engagement.get("Collaborateur") or "").strip(), str(ligne.get("Collaborateur") or "").strip(),
                 nom_legal]
    for i, c in enumerate(candidats):
        if not c:
            continue
        if " " not in c:
            if i < len(candidats) - 1:
                return {"prenom": premier or prenom_legal, "nom": c}
            continue
        p = retourner_paire_av(c, nom_legal, premier)
        if p:
            return p
    return {"prenom": prenom_legal, "nom": nom_legal}


def appellation_av(params):
    p = appellation_separee_av(params)
    return ((p.get("prenom") or "") + " " + (p.get("nom") or "")).strip()


def appellation_nom_prenom_av(params):
    p = appellation_separee_av(params)
    return ((p.get("nom") or "") + " " + (p.get("prenom") or "")).strip()


def identite_d_usage_du_courriel_av(info):
    initiales = str((info or {}).get("initiales") or "").strip()
    if not initiales:
        return None
    try:
        registre = lire_onglet_effectif(CFG_MUT["ONGLET_PERSONNES"])
        personne = next((l for l in registre.lignes if meme_texte(l.get("Initiales"), initiales)), None)
    except Exception:  # noqa: BLE001
        return None
    if not personne:
        return None
    try:
        saisie = lire_onglet(CFG["ONGLET_SAISIE"])
        fiche = next((l for l in saisie.lignes if meme_texte(l.get(COL["INITIALES"]), initiales)), None)
    except Exception:  # noqa: BLE001
        fiche = None
    return {"nom": str(personne.get("Nom") or "").strip(), "prenom": str(personne.get("Prénom") or "").strip(),
            "personne": personne, "ligne": fiche or {}, "engagement": {}}


def prenom_d_usage_du_courriel_av(info):
    try:
        params = identite_d_usage_du_courriel_av(info)
        if params and params.get("nom"):
            paire = appellation_separee_av(params)
            if paire and paire.get("prenom"):
                return paire["prenom"]
    except Exception:  # noqa: BLE001
        pass
    return prenom_de((info or {}).get("nomPrenom") or "")


def phrase_lisible_du_courriel_av(ligne_texte):
    """« 34 » : rend la phrase de l'avenant pour une puce de presence ou de
    lieu, None sinon. Sans moteur des mutations charge, None."""
    fn = PHRASE_LISIBLE["fn"]
    if fn is None:
        return None
    try:
        return fn(ligne_texte)
    except Exception:  # noqa: BLE001
        return None


def phrases_lisibles_al(html):
    t = str(html or "")
    if not t or PHRASE_LISIBLE["fn"] is None:
        return t

    def remplacer(m):
        try:
            brut = desechapper_al(m.group(2)).strip() + " : " + desechapper_al(m.group(3)).strip()
            phrase = phrase_lisible_du_courriel_av(brut)
            if not phrase:
                return m.group(0)
            return "<li" + (m.group(1) or "") + ">" + echapper(phrase) + "</li>"
        except Exception:  # noqa: BLE001
            return m.group(0)
    return re.sub(r"<li([^>]*)><b>([\s\S]*?)</b>\s*:\s*([\s\S]*?)</li>", remplacer, t, flags=re.I)


def salutation_al_usage(html, initiales, nom_prenom):
    t = str(html or "")
    init = str(initiales or "").strip()
    if not t or not init:
        return t
    try:
        params = identite_d_usage_du_courriel_av({"initiales": init, "nomPrenom": nom_prenom or ""})
    except Exception:  # noqa: BLE001
        return t
    if not params or not params.get("nom"):
        return t
    paire = appellation_separee_av(params)
    usage = str((paire or {}).get("prenom") or "").strip()
    if not usage:
        return t
    attendus = {cle_al(params["prenom"]), cle_al((params["prenom"].split() or [""])[0]),
                cle_al(params["prenom"] + " " + params["nom"]), cle_al(params["nom"] + " " + params["prenom"]),
                cle_al(prenom_de(str(nom_prenom or "")))}
    attendus.discard("")

    def remplacer(m):
        cle = cle_al(m.group(2))
        if cle not in attendus:
            return m.group(0)
        if cle == cle_al(usage):
            return m.group(0)
        return m.group(1) + " " + echapper(usage) + ","
    return re.sub(r"(Bonjour|Buongiorno|Bonsoir|Buonasera)\s+([^<,;]{1,120}),", remplacer, t)


def poser_le_style_al(html, balise, style):
    motif = re.compile("<" + balise + r"(\s[^>]*)?>", re.I)

    def remplacer(m):
        attrs = m.group(1) or ""
        if re.search(r"font-family", attrs, re.I):
            return m.group(0)
        existant = re.search(r'style\s*=\s*"([^"]*)"', attrs, re.I)
        if existant:
            return "<" + balise + attrs.replace(existant.group(0), 'style="' + style + existant.group(1) + '"') + ">"
        return "<" + balise + attrs + ' style="' + style + '">'
    return motif.sub(remplacer, str(html or ""))


def habiller_le_courriel_al(html):
    t = str(html or "")
    if not t.strip():
        return t
    if re.search(r"font-family", t, re.I):
        return t
    t = poser_le_style_al(t, "p", STYLE_MESSAGE["para"])
    t = poser_le_style_al(t, "ul", STYLE_MESSAGE["liste"])
    t = poser_le_style_al(t, "ol", STYLE_MESSAGE["liste"])
    t = poser_le_style_al(t, "li", STYLE_MESSAGE["puce"])
    t = poser_le_style_al(t, "a", STYLE_MESSAGE["lien"])
    t = poser_le_style_al(t, "table", STYLE_MESSAGE["table"])
    t = poser_le_style_al(t, "th", STYLE_MESSAGE["th"])
    t = poser_le_style_al(t, "td", STYLE_MESSAGE["tdDroite"])
    return '<div style="' + STYLE_MESSAGE["corps"] + '">' + t + "</div>"


def charte_du_courriel_al(corps, initiales, nom_prenom):
    t = str(corps or "")
    if not t.strip():
        return t
    t = phrases_lisibles_al(t)
    t = salutation_al_usage(t, initiales, nom_prenom)
    t = habiller_le_courriel_al(t)
    return t


# ------------------------------------------------ 68 signature du service RH

_SH = "https://cdn.signaturehound.com"
_LOGO = _SH + "/users/43mcvhklnss78hz/88389069-042b-4926-9676-1db41af5cfdb.png"
_AVERTISSEMENT = ("Le contenu de ce courriel est confidentiel et destiné uniquement au destinataire spécifié dans le "
                  "message. Il est strictement interdit de partager une partie de ce message avec un tiers, sans un "
                  "consentement écrit de l'expéditeur. Si vous avez reçu ce message par erreur, veuillez répondre à ce "
                  "message et procéder à sa suppression, afin que nous puissions nous assurer qu'une telle erreur ne "
                  "se reproduise pas à l'avenir.")


def _ligne_sig(icone, contenu, href, gras=False):
    gris, teal = "rgb(136,136,136)", "rgb(18,141,162)"
    style = "font-size:11px;line-height:14px;white-space:nowrap;color:" + (teal if gras else gris) + ";" + ("font-weight:700;" if gras else "")
    t = ('<a href="' + href + '" style="' + style + 'text-decoration:none" target="_blank">' + contenu + "</a>") if href \
        else ('<span style="' + style + '">' + contenu + "</span>")
    return ('<tr><td style="padding:1px 5px 1px 0;vertical-align:middle;border:0">'
            '<p style="margin:1px"><img src="' + _SH + "/icons/" + icone + '_default_128da2.png" alt="" '
            'width="18" height="18" style="display:block;border:0;margin:0;width:18px;height:18px"></p></td>'
            '<td style="line-height:14px;padding:1px 0;vertical-align:middle;border:0">'
            '<p style="margin:1px">' + t + "</p></td></tr>")


def _social_sig(icone, href):
    return ('<td width="30" style="font-size:0;line-height:0;padding:11px 1px 0 0;border:0">'
            '<p style="margin:1px"><a href="' + href + '" target="_blank">'
            '<img src="' + _SH + "/icons/" + icone + '_default_128da2.png" alt="" width="30" height="30" '
            'style="display:block;border:0;margin:0;width:30px;height:30px"></a></p></td>'
            '<td width="3" style="padding:0 0 1px;border:0"></td>')


SIGNATURE_RH_BLOC = (
    '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:0;margin:0"><tbody><tr>'
    '<td style="padding:0 1px 0 0;border:0">'
    '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:0;margin:0"><tbody><tr>'
    '<td align="center" style="padding:0 16px 0 0;vertical-align:top;border:0">'
    '<p style="margin:1px"><a href="http://www.almaval.ch/" target="_blank">'
    '<img src="' + _LOGO + '" alt="Almaval" width="150" height="157" style="display:block;border:0;max-width:150px"></a></p>'
    "</td>"
    '<td width="5" style="padding:1px 0 0;border:0"></td>'
    '<td style="padding:0 1px 0 0;vertical-align:top;border:0">'
    '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:0;margin:0"><tbody>'
    '<tr><td style="padding:0 1px 9px 0;border:0;border-bottom:2px solid #f7cb4d;font-size:11px;line-height:14px;white-space:nowrap">'
    '<p style="font-size:11px;line-height:14px;color:#7b7a7a;margin:1px;white-space:nowrap">Ressources humaines</p></td></tr>'
    '<tr><td style="padding:9px 1px 9px 0;border:0;border-bottom:2px solid #f7cb4d">'
    '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:0;margin:0"><tbody>'
    + _ligne_sig("email", "rh@almaval.ch", "mailto:rh@almaval.ch")
    + _ligne_sig("phone", "Secrétariat : +41 21 525 35 14", "tel:+41215253514")
    + _ligne_sig("mobile", "Secrétariat : +41 76 702 78 69 (uniquement WhatsApp)", "tel:+41767027869")
    + _ligne_sig("map", "Castel de Bois Genoud, 1023 Crissier", "")
    + _ligne_sig("website", "almaval.ch", "http://www.almaval.ch/", True)
    + "</tbody></table></td></tr>"
    '<tr><td style="padding:0 1px 0 0;border:0">'
    '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:0;margin:0"><tbody><tr>'
    + _social_sig("facebook", "https://www.facebook.com/almavalpsy/")
    + _social_sig("linkedin", "https://www.linkedin.com/company/almaval-psy")
    + "</tr></tbody></table></td></tr>"
    "</tbody></table></td></tr></tbody></table></td></tr></tbody></table>"
    '<p style="margin:12px 0 0 0;font-size:9px;line-height:1.4;color:#999999;">' + _AVERTISSEMENT + "</p>")


def signer_corps_rh(corps):
    t = str(corps or "")
    if not t.strip():
        return t
    if _LOGO in t or "cdn.signaturehound.com" in t:
        return t
    cloture = CFG["SIGNATURE_RH"]
    t = re.sub(r"<p[^>]*>\s*" + re.escape(cloture) + r"\s*</p>\s*", "", t, flags=re.I)
    italien = re.search(r"(Buongiorno|Buonasera|Gentile|Egregi)", re.sub(r"<[^>]+>", " ", t)[:400]) is not None
    politesse = ('<p style="margin:16px 0 12px 0;font-family:verdana,sans-serif;font-size:10px;color:#666666;">'
                 + ("Cordiali saluti," if italien else "Cordialement,") + "</p>")
    signature = politesse + SIGNATURE_RH_BLOC
    fin = t.rstrip()
    if re.search(r"</div>$", fin, re.I):
        i = fin.lower().rfind("</div>")
        return fin[:i] + signature + fin[i:]
    return t + signature


def preparer_corps(corps, initiales, nom_prenom):
    """Ce que subit un corps a l'entree de la file : charte (35), signature
    (68), et un retour a la ligne apres chaque bloc."""
    if not corps:
        return corps
    try:
        t = charte_du_courriel_al(str(corps), initiales, nom_prenom)
        t = signer_corps_rh(t)
        return re.sub(r"(</(p|li|tr|ul|ol|table|div|h[1-6])>)(?!\n)", r"\1\n", t, flags=re.I)
    except Exception:  # noqa: BLE001
        return corps


# ------------------------------------------------ 16 la file des courriels

def onglet_courriels():
    classeur = _classeur(ID_GESTION)
    if _onglet(classeur, CFG["ONGLET_COURRIELS"]) is None:
        entetes = list(COL_COURRIEL.values())
        rep = _batch_avec_reponse(ID_GESTION, [{"addSheet": {"properties": {
            "title": CFG["ONGLET_COURRIELS"], "gridProperties": {"rowCount": 100, "columnCount": len(entetes), "frozenRowCount": 1}}}}])
        prop = rep["replies"][0]["addSheet"]["properties"]
        classeur["onglets"].append(prop)
        _batch(ID_GESTION, _requete_cellules(prop["sheetId"], 0, 0, [entetes]))
        _oublier(ID_GESTION, prop["title"])
    return lire_onglet(CFG["ONGLET_COURRIELS"], rafraichir=True)


def mettre_en_file(message, a_sec=False):
    """mettreEnFile_ apres ses deux enveloppes (35 puis 68). Rend le numero de
    la ligne ecrite ; avec a_sec, rend la ligne qui serait ecrite sans ecrire."""
    m = dict(message or {})
    if m.get("corps"):
        m["corps"] = preparer_corps(m["corps"], m.get("initiales"), m.get("nomPrenom"))
    now = maintenant()
    valeurs = {
        COL_COURRIEL["CLE"]: "C" + now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
        COL_COURRIEL["CREE_LE"]: serial_de(now),
        COL_COURRIEL["TYPE"]: m.get("type") or "",
        COL_COURRIEL["INITIALES"]: m.get("initiales") or "",
        COL_COURRIEL["NOM"]: m.get("nomPrenom") or "",
        COL_COURRIEL["DESTINATAIRE"]: m.get("destinataire") or "",
        COL_COURRIEL["OBJET"]: m.get("objet") or "",
        COL_COURRIEL["CORPS"]: m.get("corps") or "",
        COL_COURRIEL["PIECE_LIEN"]: m.get("pieceLien") or "",
        COL_COURRIEL["PIECE_NOM"]: m.get("pieceNom") or "",
        COL_COURRIEL["MODE"]: m.get("mode") or CFG["MODE_COURRIEL"],
        COL_COURRIEL["STATUT"]: m.get("statut") or "En attente",
        COL_COURRIEL["MESSAGE"]: m.get("detail") or "",
    }
    if a_sec:
        return valeurs
    with _verrou:
        file_ = onglet_courriels()
        ligne = [valeurs.get(e, "") for e in file_.entetes]
        return ajouter_ligne(file_, ligne)


def marquer_file(numero_ligne, statut, detail=None):
    file_ = onglet_courriels()
    objet = {COL_COURRIEL["STATUT"]: statut, COL_COURRIEL["TRAITE_LE"]: serial_de(maintenant())}
    if detail is not None:
        objet[COL_COURRIEL["MESSAGE"]] = detail
    ecrire_objet(file_, numero_ligne, objet)


def lien_onglet(ident, nom):
    classeur = _classeur(ident)
    prop = _onglet(classeur, nom)
    return "https://docs.google.com/spreadsheets/d/" + ident + "/edit" + ("#gid=" + str(prop["sheetId"]) if prop else "")
