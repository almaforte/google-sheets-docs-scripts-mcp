"""Almaval - moteur de l'occupation des bureaux : la vue des postes admin
par personne.

Demande d'Alberto des 14 et 15.09.2026. Les grilles d'occupation
(Propositions, Planification, Vue actuelle) disent quel bureau est
occupe par qui, quelle que soit la nature de l'occupation. Les postes
administratifs repondent a une autre question : quel administratif est
present quel jour, et sa repartition d'EPT par cahier des charges
est-elle juste. D'ou une vue a part, de meme facture que la Vue
actuelle, ou la personne prend la place du bureau en tete de colonne.

Deux registres du fichier definitif des collaborateurs se lisent.
Registre - Engagements donne qui est a part administrative (colonne
« EPT admin »), l'EPT porte par chaque service (colonnes « EPT
<service> ») et la presence de chaque demi-journee (les douze colonnes
qui portent le lieu). Registre - Postes admin, onglet de saisie
d'Alberto depuis le 15.09.2026, donne la nomenclature du cahier des
charges : par personne, une ligne par poste, Service, Poste, Taux.
C'est cette nomenclature que la vue ecrit ; les colonnes de services du
registre ne servent plus qu'a defaut, pour une personne qui n'a pas
encore de postes declares, et une ligne « Direction » ne se montre
jamais : la part de direction est inherente aux roles des huit poles
de la direction generale, elle n'est pas un poste a part. Le total des
taux se confronte a l'EPT administratif de l'engagement : en rose s'il
le depasse, et une ligne « À répartir » en rose pour la part qu'aucun
poste ne porte.

Departement, calcule et non saisi (troisieme demande d'Alberto le
15.09.2026 au soir, apres le schema de gouvernance « Almaval en trois
departements », onzieme version, encore une proposition). Le vocabulaire
distingue desormais autorite (Direction generale, Operations, Proximite,
hors departement, reunies sous le mot « Fonction transversale » qu'Alberto
a retenu le 15.09.2026 au soir), departement (regroupe des services, a un
responsable)
et service (l'unite chiffree en EPT qu'Alberto declare dans Registre -
Postes admin). Un service n'appartient qu'a un seul departement, la
regle est fixe et vit dans SERVICES_VERS_DEPARTEMENT plutot que dans une
colonne a tenir a jour a la main : Departement des soins (son nom exact
encore ouvert entre soins, sante et therapies ; retenu pour l'instant,
Soins, choix d'Alberto le 15.09.2026 au soir) porte Clinique et Service
social ; Departement administratif porte Secretariat, RH, Comptabilite
et Logistique ; Departement des ressources et du developpement porte
Finances, Formation, Qualite, Informatique, Relations exterieures et
Juridique. En relisant Registre - Postes admin a la lumiere de ce
schema, deux erreurs sont apparues et ont ete corrigees a la source :
Foery Stephanie et Schick Gabrielle etaient rattachees au service
Finances pour leurs postes de comptabilite, alors que Comptabilite est
un service a part, distinct de Finances, dans un autre departement ;
et Forte Alberto M. (Directeur medical) et Devaud Oceane (Referente
clinique ADC) portaient « Soins » comme service, qui est en realite le
nom du departement, leur service etant Clinique.

Chaque personne occupe quatre colonnes. Plus de bande au-dessus des
noms : Alberto l'a fait retirer le 15.09.2026 au soir, parce que la vue
est une vue par personne et non par departement, et que beaucoup de
personnes tiennent des postes a cheval sur plusieurs departements et
plusieurs services, qu'une seule etiquette au-dessus de leur nom ne
peut pas dire sans mentir. Le departement et le service se lisent donc
ligne par ligne, dans le cahier des charges. Une vue par departement et
par service se fera a part. L'ordre des colonnes, lui, n'est plus celui
des services : c'est celui des lignes de Registre - Postes admin, qu'Alberto
range a sa main, responsables d'abord puis chargees et assistantes. Le moteur
n'a donc plus de nom a forcer a une place.
Sous son nom, la ligne « Cahier des charges » sur sa propre couleur,
puis les postes, separes par un filet horizontal tirete, sans filet
vertical entre Departement, Service, Poste et Taux ; puis le total.
Dans la grille, chaque demi-journee travaillee porte un mot qui dit
aussi ou la personne est (Alberto, 19.09.2026) : « Présent à Morges »
pour un site de la maison, aux couleurs de la personne, « Présent en
télétravail » en italique gris sur ces memes couleurs eclaircies quand
elle travaille de chez elle, jamais sur fond blanc, « Présent en
itinérance » quand elle travaille sans bureau attitre, en bougeant
entre les locaux tout en restant joignable. Le mot est fondu sur la
journee entiere quand les deux demi-journees se ressemblent, et se
separe sinon : une matinee a Crissier et une apres-midi a Morges ne se
confondent plus. Tout est ecrit par le
moteur, rien ne se saisit ici : l'onglet est protege, et la nomenclature
se corrige dans Registre - Postes admin (Service, Poste, Taux ; jamais
Departement, qui se calcule).

La meme vue est portee dans Almaval - Patients, que consultent les
collaborateurs (demande d'Alberto le 15.09.2026 au soir), dans un onglet
a elle, « Postes admin », cree a cote de l'occupation des bureaux et non
dedans : deux tableaux ne partagent pas un onglet, et les deux vues n'ont
ni le meme nombre de colonnes ni les memes largeurs. _poser ecrit un
onglet de zero, et sert les deux classeurs.

Facon de poser la charte. Les grilles d'occupation n'ont qu'une ligne
entre les noms et le premier matin, la ligne des numeros, et _blocs ne
sait lire que cette geometrie. Cette vue en a plusieurs, le cahier des
charges. Plutot que de toucher au socle, la charte est generee sur une
facade de la grille sans ces lignes, puis chaque indice de ligne des
requetes obtenues est decale d'autant sous la ligne des intitules : le
fond dore pale et le filet moyen de la ligne des numeros s'etendent ainsi
d'eux-memes a tout le cahier des charges. Ce module est le seul a
connaitre cette vue ; lieux_poser_la_charte ne la touche pas.
"""

from main import mcp, tolerant
from outils_lieux_socle import (
    BATIMENT_ADMINISTRATION,
    BLANC,
    DEMIS,
    EDITEURS,
    ETATS_ENGAGEMENT_VIVANTS,
    GRIS,
    HAUTEUR_ENTETE,
    ID_EFFECTIF,
    ID_LIEUX,
    ID_PATIENTS,
    JOURS,
    ONGLET_EFFECTIF,
    ONGLET_PATIENTS,
    _aujourdhui,
    _cellule,
    _colonne,
    _date,
    _date_serie,
    _ecrire,
    _etat_complet,
    _feuilles,
    _jolie_date,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
    _onglets,
    _rvb,
    _vider,
)
from outils_lieux_charte import (
    _couleurs_personnes,
    _requetes_charte_bureaux,
    _requetes_hauteurs,
)


ONGLET_VUE_ADMIN = "Vue admin"
# La meme vue, portee dans le classeur que consultent les collaborateurs
# (demande d'Alberto le 15.09.2026 au soir). Un onglet a elle, a cote de
# l'occupation des bureaux et non dedans : deux tableaux ne partagent pas
# un onglet, et les deux vues n'ont ni le meme nombre de colonnes ni les
# memes largeurs.
ONGLET_ADMIN_PATIENTS = "Postes admin"
# La cellule a droite de « Jour », en ligne d'en-tete, porte le nom du
# site dans les grilles d'occupation. Ici elle reste vide : Alberto a
# retire le mot ADMINISTRATION le 15.09.2026 (« je vais l'enlever, faut
# pas le remettre »), la vue etant une vue par personne et non par lieu.
SITE_ADMIN = ""
# _blocs reconnait un bloc a une cellule « Jour » suivie d'un site non
# vide : la facade, qui ne sert qu'a calculer la charte et n'est jamais
# ecrite, garde donc un marqueur technique a cette place.
SITE_ADMIN_TECHNIQUE = "ADMIN"
MOT_PRESENT = "Présent"
MOT_TELETRAVAIL = "Télétravail"
NON_TRAVAILLE = "Non travaillé"
MOT_ITINERANT = "Itinérant"
# Decision d'Alberto du 19.09.2026 : la ligne de presence dit aussi ou.
# Une demi-journee travaillee sans bureau attitre est de l'itinerance,
# la personne bouge entre les locaux et reste joignable ; le teletravail
# reste distinct, c'est de l'attitre a distance. Les valeurs de gauche
# sont celles de la liste « Lieu de travail » du registre RH ; tout ce
# qui n'y figure pas est un site et prend la forme « Présent à <site> ».
LIBELLES_PRESENCE = {
    MOT_TELETRAVAIL: "Présent en télétravail",
    MOT_ITINERANT: "Présent en itinérance",
    "Formation": "Présent en formation",
    "Déplacement": "Présent en déplacement",
    "Jura": "Présent au Jura",
}
# La regle de mise en forme cherche ce fragment, pas le libelle entier.
MARQUE_TELETRAVAIL = "télétravail"
A_REPARTIR = "À répartir"
ROSE = "#f4cccc"
LIBELLE_CAHIER = "Cahier des charges"
LIBELLE_TOTAL = "Total EPT admin"
COLONNES_PERSONNE = ("Département", "Service", "Poste", "Taux")
LARGEURS_PERSONNE = (80, 84, 92, 34)
LARGEUR_JOUR = 80
LARGEUR_DEMI = 60
# La ligne « Cahier des charges » se distingue des postes qu'elle
# coiffe : cyan pale de la gamme claire, la famille froide de la maison.
# La ligne « Cahier des charges » est doree comme la ligne des noms
# (Alberto, 20.09.2026, mise en forme faite a la main dans Postes admin
# et reprise ici).
COULEUR_CAHIER = "#f7cb4d"
# Les deux instances de la charte de gouvernance, et la couleur de chacune
# dans la vue (Alberto, 20.09.2026) : A1 porte « Legende couleurs : », les
# deux cellules de gauche de la ligne des noms portent les etiquettes sur
# leur couleur (vert pale pour la direction, rose pale pour la strategie,
# teintes posees a la main par Alberto le 20.09.2026), et chaque ligne de
# poste qui siege reprend la couleur de son instance ; une personne a deux
# postes qui siegent en a deux colores. Le siege est une propriete du POSTE, lue dans la colonne
# « Instance » du referentiel des postes, jamais de la personne. Un poste
# au Conseil de direction siege aussi au Conseil de strategie, la couleur
# de direction l'emporte.
INSTANCE_DIRECTION = "Conseil de direction"
INSTANCE_STRATEGIE = "Conseil de stratégie"
COULEURS_INSTANCES = {INSTANCE_DIRECTION: "#d9ead3", INSTANCE_STRATEGIE: "#ead1dc"}
# Une ligne de poste qui ne siege a aucun conseil porte la teinte sable de
# la charte (Alberto, 22.09.2026, apres le controle du chantier de la
# presence : « la teinte #fbe9b8 des lignes de poste qui ne siegent pas,
# que le moteur n'applique pas »). Les trois teintes se lisent alors
# ensemble : vert pale pour la direction, rose pale pour la strategie,
# sable pour un poste qui ne siege pas. Le rose d'ecart #f4cccc reste
# au-dessus, et une cellule de poste vide n'est pas peinte.
COULEUR_POSTE = "#fbe9b8"
LIBELLE_LEGENDE = "Légende couleurs :"
RANG_INSTANCES = {INSTANCE_DIRECTION: 0, INSTANCE_STRATEGIE: 1}
# Colonne du referentiel qui deplace le siege d'un poste vers un autre
# (cle « Service > Sous-service > Poste » du delegataire).
SIEGE_DELEGUE = "Siège délégué au poste"
RANG_SANS_INSTANCE = 2
# Les taux se lisent a une decimale au moins, trois quand il le faut
# (0,028 de formation, 0,293 de proximite).
FORMAT_TAUX = "0.0##"
# Entre deux postes d'une meme personne, un filet horizontal tirete.
FILET_POSTES = "DASHED"

# La nomenclature du cahier des charges, saisie par Alberto : une ligne
# par poste, rattachee a l'engagement par sa cle, ou a defaut par le nom.
# Departement n'y est plus une colonne depuis le 15.09.2026 au soir : il
# se calcule depuis Service (voir SERVICES_VERS_DEPARTEMENT), pour ne pas
# dupliquer a la main une regle fixe du schema de gouvernance.
ONGLET_POSTES = "Registre - Postes admin"
# Depuis le 20.09.2026 le registre des postes tenus s'appelle « Registre -
# Affectations » (une ligne par affectation, postes cliniques compris,
# colonne « Nature de l'EPT ») ; l'ancien nom reste lu a defaut. Seules
# les affectations dont la nature est administrative entrent dans la
# vue, et seules celles qui n'ont pas de date de fin passee.
ONGLETS_POSTES = ("Registre - Affectations", ONGLET_POSTES)
NATURE_ADMINISTRATIVE = "Administratif"
COLONNES_POSTES = ("Clé engagement", "Nom prénom", "Service", "Poste", "Taux")
# Le referentiel des postes recopie dans l'Effectif : quand une ligne du
# cahier des charges porte un sous-service (ADC, Communication...), la
# vue montre l'intitule abrege du referentiel a la place du poste nu,
# « ADC - Ch. projet » plutot que « Chargé de projet » (Alberto,
# 19.09.2026) ; sans sous-service, le poste nu suffit, le service etant
# deja dans sa colonne.
ONGLET_POSTES_REFERENTIEL = "Aide - Postes référentiel"
# Les services du registre qui ne font pas un poste a part : la part de
# direction est inherente aux roles des poles de la direction generale.
SERVICES_INTEGRES = ("Direction",)

# Les trois departements du schema de gouvernance « Almaval en trois
# departements » (onzieme version, 15.09.2026, statut proposition), et
# l'autorite, qui n'appartient a aucun departement. Le nom du premier
# reste ouvert entre soins, sante et therapies ; Soins est le choix
# provisoire d'Alberto le 15.09.2026 au soir, a corriger ici seul si le
# mot change.
DEPARTEMENT_SOINS = "Soins"
DEPARTEMENT_ADMINISTRATIF = "Administratif"
DEPARTEMENT_RESSOURCES = "Ressources et développement"
AUTORITE = "Fonction transversale"

# Le departement de chaque service, fixe par le schema de gouvernance :
# jamais une colonne a tenir a jour a la main, un service n'appartient
# qu'a un seul departement (ou a aucun, une autorite transversale).
SERVICES_VERS_DEPARTEMENT = {
    "DIRECTION GENERALE": AUTORITE,
    "OPERATIONS": AUTORITE,
    "PROXIMITE": AUTORITE,
    "CLINIQUE": DEPARTEMENT_SOINS,
    "SERVICE SOCIAL": DEPARTEMENT_SOINS,
    "ADC": DEPARTEMENT_SOINS,
    "SECRETARIAT": DEPARTEMENT_ADMINISTRATIF,
    "RH": DEPARTEMENT_ADMINISTRATIF,
    "RESSOURCES HUMAINES": DEPARTEMENT_ADMINISTRATIF,
    "COMPTABILITE": DEPARTEMENT_ADMINISTRATIF,
    "LOGISTIQUE": DEPARTEMENT_ADMINISTRATIF,
    "INTENDANCE": DEPARTEMENT_ADMINISTRATIF,
    "FINANCES": DEPARTEMENT_RESSOURCES,
    "FORMATION": DEPARTEMENT_RESSOURCES,
    "ENCADREMENT": DEPARTEMENT_RESSOURCES,
    "QUALITE": DEPARTEMENT_RESSOURCES,
    "IT": DEPARTEMENT_RESSOURCES,
    "INFORMATIQUE": DEPARTEMENT_RESSOURCES,
    "PARTENARIAT ET RELATIONS EXTERIEURES": DEPARTEMENT_RESSOURCES,
    "RELATIONS EXTERIEURES": DEPARTEMENT_RESSOURCES,
    "PARTENARIAT": DEPARTEMENT_RESSOURCES,
    "MARKETING": DEPARTEMENT_RESSOURCES,
    "JURIDIQUE": DEPARTEMENT_RESSOURCES,
}

# Le classeur maitre des vocabulaires, et son onglet des services : un
# service, son departement, son responsable.
ID_LISTES = "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY"
ONGLET_SERVICES = "Services - Responsables"
# Le registre dit « EPT Direction », la liste des services dit
# « Direction générale » : meme service.
ALIAS_SERVICES = {"DIRECTION": "Direction générale"}
# Ordre de tri : celui de Services - Responsables, qui porte encore au
# 15.09.2026 l'ancienne repartition a trois valeurs (Direction,
# Administration, Thérapies) ; sans lien avec les trois departements du
# nouveau schema de gouvernance, qui ne sert ici qu'au calcul de la
# colonne Departement du cahier des charges, pas au tri des personnes.
ORDRE_DEPARTEMENTS = ("Direction", "Administration", "Thérapies")
# Les colonnes « EPT ... » du registre qui ne sont pas des services.
EPT_TECHNIQUES = {
    "ADMIN", "CLINIQUE", "TOTAL",
    "CLINIQUE BUREAU NON CLINIQUE", "CLINIQUE BUREAU CLINIQUE", "CLINIQUE TELETRAVAIL",
    "ADMIN BUREAU NON CLINIQUE", "ADMIN BUREAU CLINIQUE", "ADMIN TELETRAVAIL", "TOTAL TELETRAVAIL",
}


# ------------------------------------------------------------------ lecture

def _lire_brut(onglet: str, classeur: str, sujet: str = ""):
    """Comme _lire, mais en valeurs non formatees : un taux de 0,028
    affiche a deux decimales se lisait 0,03 et faussait le total du
    cahier des charges (Alberto, 19.09.2026). Les dates reviennent en
    numero de serie, que _date_serie sait lire."""
    reponse = _feuilles(sujet).values().get(
        spreadsheetId=classeur, range="'" + onglet + "'", valueRenderOption="UNFORMATTED_VALUE"
    ).execute()
    return reponse.get("values", [])


def _abreges_postes(sujet: str = ""):
    """{(service, sous-service, poste) normalises: intitule abrege}, lu
    dans le referentiel des postes ; vide si l'onglet manque."""
    try:
        lignes = _lire(ONGLET_POSTES_REFERENTIEL, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}
    if not lignes:
        return {}
    tetes = lignes[0]
    try:
        i_service = _colonne(tetes, "Service")
        i_sous = _colonne(tetes, "Sous-service")
        i_poste = _colonne(tetes, "Poste")
        i_abrege = _colonne(tetes, "Intitulé EPT abrégé")
    except RuntimeError:
        return {}
    abreges = {}
    for ligne in lignes[1:]:
        abrege = str(_cellule(ligne, i_abrege)).strip()
        if abrege:
            abreges[(_normaliser(_cellule(ligne, i_service)), _normaliser(_cellule(ligne, i_sous)),
                     _normaliser(_cellule(ligne, i_poste)))] = abrege
    return abreges


# Ordre des personnes dans la vue, regles validees par Alberto le
# 19.09.2026 : la Direction toujours en tete ; puis le departement et le
# service dans l'ordre du referentiel des postes, qui reflete
# l'organigramme (une personne est classee par son poste le plus lourd,
# a egalite par le service qui vient en premier, et un clinicien a
# mandat administratif va sous le service de son poste admin) ; puis le
# niveau de responsabilite lu sur l'intitule du poste ; puis l'EPT
# administratif decroissant ; puis le nom. Aucune colonne de rang a
# tenir a la main.
POSTES_DE_DIRECTION = ("DG", "DIRECTEUR")
RANG_POSTE_AUTRE = 5


def _rang_poste(poste: str) -> int:
    """Le niveau de responsabilite d'un poste, lu sur son intitule :
    0 direction, 1 responsable ou CFO, 2 responsable qualifie
    (operationnel, strategique, pole), 3 charge ou referent,
    4 assistant ou secretaire, 5 le reste."""
    p = _normaliser(poste)
    if " - " in p:
        # intitule abrege du referentiel, « ADC - Ch. projet » : le poste
        # est apres le dernier separateur
        p = p.split(" - ")[-1].strip()
    if not p:
        return RANG_POSTE_AUTRE
    if p == "DG" or p.startswith("DIRECTEUR") or p.startswith("DIRECTRICE") or p.startswith("DIR."):
        return 0
    if p in ("RESPONSABLE", "RESP.", "CFO"):
        return 1
    if p.startswith("RESPONSABLE") or p.startswith("RESP."):
        return 2
    if p.startswith("CHARGE") or p.startswith("CH.") or p.startswith("REFERENT") or p.startswith("REF."):
        return 3
    if p.startswith("ASSISTANT") or p.startswith("ASS.") or p.startswith("SECRETAIRE"):
        return 4
    return RANG_POSTE_AUTRE


def _ordre_referentiel(sujet: str = ""):
    """({departement normalise: rang}, {service normalise: rang}) dans
    l'ordre des lignes du referentiel des postes copie dans l'Effectif,
    premiere apparition ; vides si l'onglet manque."""
    try:
        lignes = _lire(ONGLET_POSTES_REFERENTIEL, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}, {}
    if not lignes:
        return {}, {}
    tetes = lignes[0]
    try:
        i_departement = _colonne(tetes, "Département")
        i_service = _colonne(tetes, "Service")
    except RuntimeError:
        return {}, {}
    departements, services = {}, {}
    for ligne in lignes[1:]:
        departement = _normaliser(_cellule(ligne, i_departement))
        service = _normaliser(_cellule(ligne, i_service))
        if departement and departement not in departements:
            departements[departement] = len(departements)
        if service and service not in services:
            services[service] = len(services)
    return departements, services


def _instances_postes(sujet: str = ""):
    """{(service, sous-service, poste) normalises: instance}, lu dans le
    referentiel des postes copie dans l'Effectif. Depuis le 20.09.2026
    apres-midi le referentiel porte deux colonnes a croix, « Conseil de
    direction » et « Conseil de strategie » (un poste au Conseil de
    direction siege aussi au Conseil de strategie, la direction
    l'emporte) ; l'ancienne colonne unique « Instance » est lue a defaut.
    La colonne « Siege delegue au poste » deplace le siege vers le poste
    delegataire, qui seul est colore et range parmi les sieges (le
    20.09.2026 au soir : Qualite > Responsable delegue son siege a
    Qualite > Responsable pole patients). Vide si l'onglet manque."""
    try:
        lignes = _lire(ONGLET_POSTES_REFERENTIEL, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}
    if not lignes:
        return {}
    tetes = lignes[0]
    try:
        i_service = _colonne(tetes, "Service")
        i_sous = _colonne(tetes, "Sous-service")
        i_poste = _colonne(tetes, "Poste")
    except RuntimeError:
        return {}
    i_direction = i_strategie = i_instance = None
    try:
        i_direction = _colonne(tetes, INSTANCE_DIRECTION)
        i_strategie = _colonne(tetes, INSTANCE_STRATEGIE)
    except RuntimeError:
        try:
            i_instance = _colonne(tetes, "Instance")
        except RuntimeError:
            return {}
    i_cle = i_delegue = None
    try:
        i_cle = _colonne(tetes, "Clé poste")
    except RuntimeError:
        i_cle = None
    try:
        i_delegue = _colonne(tetes, SIEGE_DELEGUE)
    except RuntimeError:
        i_delegue = None
    instances, par_cle, delegations = {}, {}, []
    for ligne in lignes[1:]:
        triplet = (_normaliser(_cellule(ligne, i_service)), _normaliser(_cellule(ligne, i_sous)),
                   _normaliser(_cellule(ligne, i_poste)))
        if not triplet[0] or not triplet[2]:
            continue  # sous-service seul, sans poste : rien ne siege
        # la cle du referentiel, ou sa reconstruction « Service > Sous-service > Poste »
        cle = _normaliser(_cellule(ligne, i_cle)) if i_cle is not None else ""
        if not cle:
            cle = _normaliser(" > ".join(x for x in (
                str(_cellule(ligne, i_service)).strip(), str(_cellule(ligne, i_sous)).strip(),
                str(_cellule(ligne, i_poste)).strip()) if x))
        par_cle[cle] = triplet
        instance = ""
        if i_instance is not None:
            instance = str(_cellule(ligne, i_instance)).strip()
        else:
            if _normaliser(_cellule(ligne, i_direction)) == "X":
                instance = INSTANCE_DIRECTION
            elif _normaliser(_cellule(ligne, i_strategie)) == "X":
                instance = INSTANCE_STRATEGIE
        if instance not in RANG_INSTANCES:
            continue
        delegue = _normaliser(_cellule(ligne, i_delegue)) if i_delegue is not None else ""
        if delegue:
            delegations.append((triplet, delegue, instance))
        else:
            instances[triplet] = instance
    # Le siege delegue est porte par le poste delegataire, jamais par les
    # deux : Alberto, 20.09.2026, « la delegation reste chez Steph quand
    # meme pour le CoDir ». Un delegataire qui siege deja garde le rang
    # le plus eleve ; une cle de delegue inconnue laisse le siege au
    # titulaire, pour ne rien perdre.
    for triplet, delegue, instance in delegations:
        cible = par_cle.get(delegue)
        if cible is None:
            instances[triplet] = instance
            continue
        actuelle = instances.get(cible)
        if actuelle is None or RANG_INSTANCES[instance] < RANG_INSTANCES[actuelle]:
            instances[cible] = instance
    return instances


def _nombre(valeur):
    """Un nombre lu dans une cellule affichee en francais, ou None."""
    texte = str(valeur if valeur is not None else "").strip().replace("\xa0", "").replace(" ", "")
    if not texte:
        return None
    texte = texte.replace(",", ".")
    if texte.endswith("%"):
        try:
            return float(texte[:-1]) / 100.0
        except ValueError:
            return None
    try:
        return float(texte)
    except ValueError:
        return None


def _services(sujet: str = ""):
    """Les services de la maison, dans l'ordre de Services - Responsables :
    rend ({service normalise: rang}, {service normalise: departement}).
    Sans le classeur maitre, la vue se fait sans departements. Ce
    departement-la est celui, ancien, du tri (Direction/Administration/
    Thérapies) ; pas celui, nouveau, du cahier des charges."""
    try:
        lignes = _lire(ONGLET_SERVICES, ID_LISTES, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}, {}
    if not lignes:
        return {}, {}
    tetes = lignes[0]
    try:
        i_service = _colonne(tetes, "Service")
        i_departement = _colonne(tetes, "Département")
    except RuntimeError:
        return {}, {}
    ordre, departements = {}, {}
    for k, ligne in enumerate(lignes[1:]):
        service = _normaliser(_cellule(ligne, i_service))
        if service and service not in ordre:
            ordre[service] = k
            departements[service] = str(_cellule(ligne, i_departement)).strip()
    return ordre, departements


def _cle_service(nom: str) -> str:
    """Le service tel que la liste des services le nomme, normalise."""
    cle = _normaliser(nom)
    return _normaliser(ALIAS_SERVICES.get(cle, nom))


def _departement_du_service(service: str) -> str:
    """Le departement d'un service, calcule depuis le schema de
    gouvernance, jamais saisi. Chaine vide si le service n'est pas
    encore reconnu, pour que la vue le signale plutot que de deviner."""
    return SERVICES_VERS_DEPARTEMENT.get(_normaliser(service), "")


def _postes_declares(sujet: str = ""):
    """La nomenclature saisie dans Registre - Postes admin : rend
    ({cle d'engagement normalisee: [(departement, service, poste, taux)]},
    {nom normalise: [(departement, service, poste, taux)]},
    {("cle"|"nom", identifiant): rang de premiere apparition},
    {(service, poste affiche) normalises: instance ou le poste siege}), dans
    l'ordre des lignes ; une ligne va sous sa cle quand elle en porte
    une, sous son nom sinon. Le troisieme dictionnaire donne l'ordre des
    colonnes de la vue : celui des lignes du registre, qu'Alberto range
    a sa main (15.09.2026 au soir). Le departement de chaque ligne est calcule depuis son
    service (SERVICES_VERS_DEPARTEMENT), jamais lu dans le registre. Sans
    l'onglet, la vue se fait avec les services du registre."""
    lignes = []
    for onglet in ONGLETS_POSTES:
        try:
            lignes = _lire_brut(onglet, ID_EFFECTIF, sujet=sujet)
        except Exception:  # noqa: BLE001
            lignes = []
        if lignes:
            break
    if not lignes:
        return {}, {}, {}, {}
    tetes = lignes[0]
    try:
        i_service = _colonne(tetes, "Service")
        i_poste = _colonne(tetes, "Poste")
        i_taux = _colonne(tetes, "Taux")
    except RuntimeError:
        return {}, {}, {}, {}
    try:
        i_nature = _colonne(tetes, "Nature de l'EPT")
    except RuntimeError:
        i_nature = None
    try:
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_fin = None
    aujourdhui = _aujourdhui() if i_fin is not None else None
    try:
        i_cle = _colonne(tetes, "Clé engagement")
    except RuntimeError:
        i_cle = None
    try:
        i_nom = _colonne(tetes, "Nom prénom")
    except RuntimeError:
        i_nom = None
    try:
        i_sous = _colonne(tetes, "Sous-service")
    except RuntimeError:
        i_sous = None
    abreges = _abreges_postes(sujet=sujet) if i_sous is not None else {}
    instances = _instances_postes(sujet=sujet)
    par_cle, par_nom, apparition, sieges = {}, {}, {}, {}
    for ligne in lignes[1:]:
        service = str(_cellule(ligne, i_service)).strip()
        poste = str(_cellule(ligne, i_poste)).strip()
        taux = _nombre(_cellule(ligne, i_taux))
        if not poste and not service:
            continue
        if i_nature is not None:
            nature = str(_cellule(ligne, i_nature)).strip()
            if nature and _normaliser(nature) != _normaliser(NATURE_ADMINISTRATIVE):
                continue  # affectation clinique : hors de la vue des postes admin
        if i_fin is not None and aujourdhui is not None:
            fin = _date_serie(_cellule(ligne, i_fin))
            if fin and fin < aujourdhui:
                continue  # affectation terminee
        sous = str(_cellule(ligne, i_sous)).strip() if i_sous is not None else ""
        instance = instances.get((_normaliser(service), _normaliser(sous), _normaliser(poste)))
        if sous:
            poste = abreges.get((_normaliser(service), _normaliser(sous), _normaliser(poste)),
                                poste + " " + sous)
        if instance:
            sieges[(_normaliser(service), _normaliser(poste))] = instance
        departement = _departement_du_service(service)
        entree = (departement, service, poste, taux if taux is not None else 0.0)
        cle = _normaliser(_cellule(ligne, i_cle)) if i_cle is not None else ""
        nom = _normaliser(_cellule(ligne, i_nom)) if i_nom is not None else ""
        if cle:
            par_cle.setdefault(cle, []).append(entree)
            apparition.setdefault(("cle", cle), len(apparition))
        elif nom:
            par_nom.setdefault(nom, []).append(entree)
            apparition.setdefault(("nom", nom), len(apparition))
    return par_cle, par_nom, apparition, sieges


def _engagements_admin(date_iso: str, sujet: str = ""):
    """Ce que Registre - Engagements dit de chaque personne a part
    administrative, a une date : la cle d'engagement, l'EPT
    administratif, l'EPT par service, la profession et la presence de
    chaque demi-journee (le lieu). Engagements vivants a la date ; En cours
    prime sur À venir ; deux engagements du meme etat s'additionnent.
    Rend {nom: fiche}."""
    effectif = _lire_brut(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not effectif:
        return {}
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    i_admin = _colonne(tetes, "EPT admin")
    try:
        i_cle = _colonne(tetes, "Clé engagement")
    except RuntimeError:
        i_cle = None
    # La vue affiche le nom d'usage (18.09.2026) ; le nom complet reste
    # dans la fiche pour retrouver les postes declares sous ce nom.
    try:
        i_ini = _colonne(tetes, "Initiales")
    except RuntimeError:
        i_ini = None
    affichage = {}
    try:
        from outils_lieux_noms import _referentiel_personnes
        affichage = {ini: p["nom_usage"] for ini, p in _referentiel_personnes(sujet=sujet)["personnes"].items()}
    except Exception as erreur:  # noqa: BLE001
        print("[lieux admin] noms d'usage illisibles : " + str(erreur)[:200], flush=True)
    try:
        i_profession = _colonne(tetes, "Profession")
    except RuntimeError:
        i_profession = None
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    try:
        i_debut = _colonne(tetes, "Date de début")
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_debut = i_fin = None
    try:
        i_total = _colonne(tetes, "EPT total")
    except RuntimeError:
        i_total = None
    colonnes_services = []
    for k, tete in enumerate(tetes):
        texte = str(tete or "").strip()
        if texte.startswith("EPT ") and _normaliser(texte[4:]) not in EPT_TECHNIQUES:
            colonnes_services.append((texte[4:].strip(), k))
    creneaux = []
    for jour in JOURS:
        for demi in DEMIS:
            try:
                creneaux.append((jour, demi, _colonne(tetes, jour + " " + demi.lower())))
            except RuntimeError:
                continue

    par_etat = {}
    for ligne in effectif[1:]:
        nom_complet = str(_cellule(ligne, i_nom)).strip()
        if not nom_complet:
            continue
        nom = nom_complet
        if i_ini is not None:
            nom = affichage.get(str(_cellule(ligne, i_ini)).strip(), nom_complet)
        etat = _cellule(ligne, i_etat) if i_etat is not None else ETATS_ENGAGEMENT_VIVANTS[0]
        if etat not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        if i_debut is not None:
            debut = _date_serie(_cellule(ligne, i_debut))
            fin = _date_serie(_cellule(ligne, i_fin))
            if debut and debut > date_iso:
                continue
            if fin and fin < date_iso:
                continue
        ept_admin = _nombre(_cellule(ligne, i_admin)) or 0.0
        postes = {}
        for service, k in colonnes_services:
            valeur = _nombre(_cellule(ligne, k))
            if valeur:
                postes[service] = postes.get(service, 0.0) + valeur
        if ept_admin <= 0 and not postes:
            continue
        fiche = par_etat.setdefault(_normaliser(nom), {}).setdefault(etat, {
            "nom": nom, "nom_complet": nom_complet, "cle": "", "ept_admin": 0.0, "postes": {},
            "profession": "", "presences": {}, "ept_total": 0.0,
        })
        fiche["ept_admin"] += ept_admin
        if i_total is not None:
            fiche["ept_total"] += _nombre(_cellule(ligne, i_total)) or 0.0
        if not fiche["cle"] and i_cle is not None:
            fiche["cle"] = str(_cellule(ligne, i_cle)).strip()
        for service, valeur in postes.items():
            fiche["postes"][service] = fiche["postes"].get(service, 0.0) + valeur
        if not fiche["profession"] and i_profession is not None:
            fiche["profession"] = str(_cellule(ligne, i_profession)).strip()
        for jour, demi, k in creneaux:
            lieu = str(_cellule(ligne, k)).strip()
            if lieu and _normaliser(lieu) != _normaliser(NON_TRAVAILLE):
                fiche["presences"].setdefault((jour, demi), lieu)

    personnes = {}
    for cle, etats in par_etat.items():
        for etat in ETATS_ENGAGEMENT_VIVANTS:
            if etat in etats:
                fiche = etats[etat]
                fiche["ept_admin"] = round(fiche["ept_admin"], 3)
                fiche["postes"] = {s: round(v, 3) for s, v in fiche["postes"].items()}
                personnes[fiche["nom"]] = fiche
                break
    return personnes


# ------------------------------------------------------------------- grille

def _eclairci(hexa: str, part: float = 0.5) -> str:
    """La meme couleur, melangee a du blanc pour la part donnee."""
    hexa = hexa.lstrip("#")
    canaux = [int(hexa[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join("%02x" % round(v + (255 - v) * part) for v in canaux)


def _mot(lieu: str) -> str:
    """Le mot de la case de presence, qui dit aussi ou la personne est.

    Un lieu inconnu de LIBELLES_PRESENCE est tenu pour un site et prend
    la forme « Présent à <site> » : mieux vaut un libelle inhabituel
    qu'une case vide, la vue etant d'abord un temoin de presence.
    """
    cle = _normaliser(lieu)
    for valeur, libelle in LIBELLES_PRESENCE.items():
        if cle == _normaliser(valeur):
            return libelle
    return MOT_PRESENT + " à " + str(lieu).strip()


def _grille_admin(date_iso: str, sujet: str = ""):
    """La grille de la vue, en memoire, et ce qu'il faut pour l'habiller.

    Une ligne de titre, la ligne des noms (le nom repete sur ses quatre colonnes,
    que la fusion reduira a une seule cellule), la ligne des intitules du
    cahier des charges, une ligne par poste, la ligne « À répartir »
    quand elle a lieu d'etre, le total, puis les douze demi-journees.

    Le cahier des charges d'une personne est celui de Registre - Postes
    admin, dans l'ordre de ses lignes, retrouve par la cle d'engagement
    ou, a defaut, par le nom ; son departement est calcule depuis son
    service (SERVICES_VERS_DEPARTEMENT). Sans postes declares, les
    services du registre en tiennent lieu, par EPT decroissant, sans la
    Direction.

    L'ordre des colonnes suit les regles validees par Alberto le
    19.09.2026 : la Direction en tete ; puis le departement et le service
    du referentiel des postes, dans l'ordre de ses lignes, la personne
    classee par son poste le plus lourd (a egalite, le service qui vient
    en premier ; un clinicien a mandat administratif va sous le service
    de son poste admin) ; puis le niveau de responsabilite de ce poste,
    lu sur son intitule ; puis l'EPT administratif decroissant ; puis le
    nom. Les lignes du cahier d'une personne vont par taux decroissant,
    puis niveau du poste, puis service. Sans postes declares, le service
    le plus lourd du registre classe la personne.
    """
    ordre, departements = _services(sujet=sujet)
    fiches = _engagements_admin(date_iso, sujet=sujet)
    declares_cle, declares_nom, apparition, sieges = _postes_declares(sujet=sujet)
    integres = {_cle_service(s) for s in SERVICES_INTEGRES}

    def service_de(fiche):
        profession = _cle_service(fiche["profession"])
        if profession in ordre:
            return fiche["profession"]
        if fiche["postes"]:
            return max(fiche["postes"].items(), key=lambda x: (x[1], -ordre.get(_cle_service(x[0]), 999)))[0]
        return fiche["profession"]

    def rang_departement(departement):
        return ORDRE_DEPARTEMENTS.index(departement) if departement in ORDRE_DEPARTEMENTS else len(ORDRE_DEPARTEMENTS)

    ordre_departements, ordre_services = _ordre_referentiel(sujet=sujet)

    def postes_de(fiche):
        """Les postes declares d'une personne, (departement, service,
        poste, taux), par la cle d'engagement ou a defaut par le nom."""
        declare = list(declares_cle.get(_normaliser(fiche["cle"]), [])) if fiche["cle"] else []
        declare += declares_nom.get(_normaliser(fiche["nom"]), [])
        if fiche.get("nom_complet") and _normaliser(fiche["nom_complet"]) != _normaliser(fiche["nom"]):
            declare += declares_nom.get(_normaliser(fiche["nom_complet"]), [])
        return declare

    def rang_service_referentiel(service):
        return ordre_services.get(_normaliser(service), len(ordre_services))

    def rang_departement_referentiel(service):
        return ordre_departements.get(_normaliser(_departement_du_service(service)), len(ordre_departements))

    def instance_de(service, poste):
        return sieges.get((_normaliser(service), _normaliser(poste)))

    def rang_instance(declare):
        """0 si un poste siege au Conseil de direction, 1 si un poste siege
        au Conseil de strategie, 2 sinon (Alberto, 20.09.2026)."""
        rangs = [RANG_INSTANCES[i] for i in (instance_de(s, p) for _, s, p, _ in declare) if i]
        return min(rangs) if rangs else RANG_SANS_INSTANCE

    def rang(nom):
        """Ceux qui siegent au Conseil de direction d'abord, puis ceux qui
        siegent au Conseil de strategie, puis le reste ; dans chaque groupe,
        Direction en tete ; puis departement et service du referentiel,
        la personne classee par son poste le plus lourd (a egalite, le
        service qui vient en premier) ; puis le niveau du poste ; puis
        l'EPT administratif decroissant ; puis le nom. Sans postes
        declares, le service le plus lourd du registre en tient lieu."""
        fiche = fiches[nom]
        declare = postes_de(fiche)
        if declare:
            principal = min(declare, key=lambda e: (-float(e[3] or 0.0), rang_service_referentiel(e[1])))
            _, service, poste, _ = principal
            direction = 0 if any(_normaliser(p) == "DG" or _normaliser(s) == _normaliser("Direction générale")
                                 for _, s, p, _ in declare) else 1
            rang_poste = _rang_poste(poste)
        else:
            candidats = [(s, v) for s, v in fiche["postes"].items() if _cle_service(s) not in integres]
            service = max(candidats, key=lambda x: (x[1], -rang_service_referentiel(x[0])))[0] if candidats else fiche["profession"]
            direction = 1
            rang_poste = RANG_POSTE_AUTRE
        return (rang_instance(declare), direction,
                rang_departement_referentiel(service), rang_service_referentiel(service),
                rang_poste, -round(float(fiche["ept_admin"] or 0.0), 3), _normaliser(nom))

    personnes = sorted(fiches, key=rang)
    cahiers, a_repartir, sans_cahier = [], {}, []
    for nom in personnes:
        fiche = fiches[nom]
        declare = list(declares_cle.get(_normaliser(fiche["cle"]), [])) if fiche["cle"] else []
        declare += declares_nom.get(_normaliser(nom), [])
        if fiche.get("nom_complet") and _normaliser(fiche["nom_complet"]) != _normaliser(nom):
            declare += declares_nom.get(_normaliser(fiche["nom_complet"]), [])
        if declare:
            cahier = sorted(((d, s, p, round(float(t or 0.0), 3)) for d, s, p, t in declare),
                            key=lambda e: (-e[3], _rang_poste(e[2]), rang_service_referentiel(e[1])))
        else:
            sans_cahier.append(nom)
            lignes_postes = sorted(
                ((-v, ordre.get(_cle_service(s), 999), s, v) for s, v in fiche["postes"].items()
                 if _cle_service(s) not in integres),
            )
            cahier = [(_departement_du_service(s), s, s, v) for _, _, s, v in lignes_postes]
        reste = round(fiche["ept_admin"] - sum(v for _, _, _, v in cahier), 3)
        if reste > 0.0005:
            cahier.append(("", "", A_REPARTIR, reste))
            a_repartir[nom] = reste
        cahiers.append(cahier)
    n_postes = max([len(c) for c in cahiers] + [1])
    largeur = 2 + 4 * len(personnes)

    def vide():
        return [""] * largeur

    # La ligne 1 ne porte plus de titre date : « Legende couleurs : » a
    # gauche, la date etant celle du passage du matin (Alberto,
    # 20.09.2026). Les deux etiquettes d'instance occupent les deux
    # cellules de gauche de la ligne des noms, a la place de « Jour » ; la
    # facade rendue a la charte des bureaux garde « Jour » (voir _facade).
    grille = [[LIBELLE_LEGENDE] + [""] * (largeur - 1)]
    entete = vide()
    entete[0] = INSTANCE_DIRECTION
    entete[1] = INSTANCE_STRATEGIE
    legende = [(1, 0, INSTANCE_DIRECTION), (1, 1, INSTANCE_STRATEGIE)]
    intitules = vide()
    intitules[0] = LIBELLE_CAHIER
    for k, nom in enumerate(personnes):
        c = 2 + 4 * k
        entete[c] = entete[c + 1] = entete[c + 2] = entete[c + 3] = nom
        intitules[c], intitules[c + 1], intitules[c + 2], intitules[c + 3] = COLONNES_PERSONNE
    grille += [entete, intitules]

    r_attributs = len(grille)
    roses = []  # (ligne, colonne) a peindre en rose
    cases_sieges = []  # (ligne, colonne de depart, instance) : lignes de poste qui siegent
    cases_postes = []  # (ligne, colonne de depart) : lignes de poste qui ne siegent pas
    sans_departement = set()
    for p in range(n_postes):
        ligne = vide()
        ligne[0] = "Poste " + str(p + 1)
        for k in range(len(personnes)):
            c = 2 + 4 * k
            if p < len(cahiers[k]):
                departement, service, poste, taux = cahiers[k][p]
                ligne[c], ligne[c + 1], ligne[c + 2], ligne[c + 3] = departement, service, poste, taux
                if poste == A_REPARTIR:
                    roses += [(len(grille), c), (len(grille), c + 1), (len(grille), c + 2), (len(grille), c + 3)]
                elif service and not departement:
                    sans_departement.add(service)
                instance = sieges.get((_normaliser(service), _normaliser(poste)))
                if instance:
                    cases_sieges.append((len(grille), c, instance))
                elif poste and poste != A_REPARTIR:
                    cases_postes.append((len(grille), c))
        grille.append(ligne)
    total = vide()
    total[0] = LIBELLE_TOTAL
    ecarts = []
    for k, nom in enumerate(personnes):
        c = 2 + 4 * k
        somme = round(sum(v for _, _, _, v in cahiers[k]), 3)
        total[c + 3] = somme
        ept_admin = fiches[nom]["ept_admin"]
        if abs(somme - ept_admin) > 0.0005:
            roses.append((len(grille), c + 3))
            ecarts.append({"collaborateur": nom, "postes": somme, "ept_admin": ept_admin,
                           "lecture": "la somme des postes dépasse l'EPT administratif"})
        elif nom in a_repartir:
            ecarts.append({"collaborateur": nom, "postes": round(somme - a_repartir[nom], 3),
                           "ept_admin": ept_admin, "a_repartir": a_repartir[nom],
                           "lecture": "une part de l'EPT administratif n'est portée par aucun service"})
        # Troisieme controle, demande par Alberto le 19.09.2026 : la
        # presence declaree doit tenir dans l'EPT total, dix demi-journees
        # pour un plein temps. Une semaine qui deborde peut etre un samedi
        # travaille, l'ecart se lit, il ne se corrige pas tout seul.
        ept_total = round(fiches[nom].get("ept_total") or 0.0, 3)
        attendues = int(round(ept_total * 10))
        declarees = len(fiches[nom]["presences"])
        if attendues and declarees != attendues:
            ecarts.append({"collaborateur": nom, "demi_journees_declarees": declarees,
                           "demi_journees_attendues": attendues, "ept_total": ept_total,
                           "lecture": "la présence déclarée ne correspond pas à l'EPT total"})
    grille.append(total)
    r_jours = len(grille)

    presences_jour = {}
    for jour in JOURS:
        for demi in DEMIS:
            ligne = vide()
            ligne[0] = jour if demi == DEMIS[0] else ""
            ligne[1] = demi
            for k, nom in enumerate(personnes):
                c = 2 + 4 * k
                lieu = fiches[nom]["presences"].get((jour, demi))
                if lieu:
                    mot = _mot(lieu)
                    ligne[c] = ligne[c + 1] = ligne[c + 2] = ligne[c + 3] = mot
                    presences_jour.setdefault(k, {})[(jour, demi)] = mot
            grille.append(ligne)

    meta = {
        "personnes": personnes,
        "largeur": largeur,
        "r_entete": 1,
        "r_intitules": 2,
        "r_attributs": list(range(r_attributs, r_jours)),
        "r_jours": r_jours,
        "r_fin": len(grille),
        "presences": presences_jour,
        "roses": roses,
        "sieges": cases_sieges,
        "postes": cases_postes,
        "legende": legende,
        "ecarts": ecarts,
        "n_postes": n_postes,
        "sans_cahier": sans_cahier,
        "sans_departement": sorted(sans_departement),
    }
    return grille, meta


def _facade(grille, meta):
    """La meme grille sans les lignes du cahier des charges : une ligne
    entre les noms et le premier matin, la geometrie que _blocs sait lire.

    La cellule du site est vide dans la vue livree, mais _blocs a besoin
    d'y lire quelque chose pour reconnaitre le bloc : la facade, qui ne
    sert qu'au calcul de la charte, porte un marqueur technique."""
    exclues = set(meta["r_attributs"])
    facade = [list(l) for r, l in enumerate(grille) if r not in exclues]
    r_entete = meta["r_entete"]
    if 0 <= r_entete < len(facade) and len(facade[r_entete]) > 1:
        # la vue livree porte les etiquettes d'instance a la place de
        # « Jour » et du site : la facade remet ce que _blocs attend
        facade[r_entete][0] = "Jour"
        facade[r_entete][1] = SITE_ADMIN_TECHNIQUE
    return facade


def _decaler(objet, seuil: int, decalage: int):
    """Decale, dans des requetes ecrites pour la facade, tout indice de
    ligne a partir du seuil : startRowIndex et endRowIndex partout, et
    startIndex et endIndex des dimensions quand il s'agit de lignes."""
    if isinstance(objet, list):
        return [_decaler(x, seuil, decalage) for x in objet]
    if not isinstance(objet, dict):
        return objet
    resultat = {}
    lignes = objet.get("dimension") == "ROWS"
    for cle, valeur in objet.items():
        if cle in ("startRowIndex", "endRowIndex") and isinstance(valeur, int) and valeur >= seuil:
            resultat[cle] = valeur + decalage
        elif lignes and cle in ("startIndex", "endIndex") and isinstance(valeur, int) and valeur >= seuil:
            resultat[cle] = valeur + decalage
        else:
            resultat[cle] = _decaler(valeur, seuil, decalage)
    return resultat


# ----------------------------------------------------------------- habillage

def _fusions_admin(sid: int, grille, meta):
    """Les fusions de la vue : etiquettes sur deux colonnes, nom sur ses
    quatre colonnes, jour sur ses deux lignes, presence sur quatre
    colonnes et, pour une journee entiere, sur ses deux lignes."""
    def fusion(r0, r1, c0, c1):
        return {"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}}}

    requetes = []
    for r in [meta["r_intitules"]] + meta["r_attributs"]:
        requetes.append(fusion(r, r + 1, 0, 2))
    for k in range(len(meta["personnes"])):
        c = 2 + 4 * k
        requetes.append(fusion(meta["r_entete"], meta["r_entete"] + 1, c, c + 4))
    for j in range(len(JOURS)):
        r_matin = meta["r_jours"] + 2 * j
        requetes.append(fusion(r_matin, r_matin + 2, 0, 1))
        for k in range(len(meta["personnes"])):
            c = 2 + 4 * k
            creneaux = meta["presences"].get(k, {})
            matin, apres = creneaux.get((JOURS[j], DEMIS[0])), creneaux.get((JOURS[j], DEMIS[1]))
            if matin and matin == apres:
                requetes.append(fusion(r_matin, r_matin + 2, c, c + 4))
            else:
                requetes.append(fusion(r_matin, r_matin + 1, c, c + 4))
                requetes.append(fusion(r_matin + 1, r_matin + 2, c, c + 4))
    return requetes


def _charte_admin(sid: int, grille, meta, couleurs):
    """La charte des grilles d'occupation, posee sur la facade et
    decalee, puis ce qui est propre a cette vue."""
    facade = _facade(grille, meta)
    seuil = meta["r_attributs"][0] if meta["r_attributs"] else meta["r_jours"]
    decalage = len(meta["r_attributs"])
    requetes = _requetes_charte_bureaux(sid, facade, {}, base=True)
    requetes += _requetes_hauteurs(sid, facade)
    requetes = _decaler(requetes, seuil, decalage)

    filet = {"style": "SOLID_MEDIUM", "color": _rvb(GRIS)}
    fin = {"style": "SOLID", "color": _rvb(GRIS)}
    tirete = {"style": FILET_POSTES, "color": _rvb(GRIS)}
    aucun = {"style": "NONE"}
    r_fin = meta["r_fin"]
    n = len(meta["personnes"])

    def bords(r0, r1, c0, c1, **cotes):
        requete = {"range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                             "startColumnIndex": c0, "endColumnIndex": c1}}
        requete.update(cotes)
        return {"updateBorders": requete}

    # les colonnes des jours restent sous les yeux quand la vue defile
    requetes.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenColumnCount": 2}},
        "fields": "gridProperties.frozenColumnCount"}})

    # le cahier des charges se lit sur deux lignes de texte
    for r in meta["r_attributs"]:
        requetes.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r + 1},
            "properties": {"pixelSize": HAUTEUR_ENTETE}, "fields": "pixelSize"}})

    # largeurs : les deux colonnes de gauche, puis quatre par personne
    largeurs = [(0, 1, LARGEUR_JOUR), (1, 2, LARGEUR_DEMI)]
    for k in range(n):
        for d, pixels in enumerate(LARGEURS_PERSONNE):
            c = 2 + 4 * k + d
            largeurs.append((c, c + 1, pixels))
    for c0, c1, pixels in largeurs:
        requetes.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize"}})

    # la ligne « Cahier des charges » sur sa propre couleur, en gras
    r_intitules = meta["r_intitules"]
    requetes.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r_intitules, "endRowIndex": r_intitules + 1,
                  "startColumnIndex": 0, "endColumnIndex": meta["largeur"]},
        "cell": {"userEnteredFormat": {"backgroundColor": _rvb(COULEUR_CAHIER),
                                       "textFormat": {"bold": True}}},
        "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold"}})

    if meta["r_attributs"]:
        r0, r1 = meta["r_attributs"][0], meta["r_attributs"][-1] + 1
        # les taux en nombre, une a trois decimales
        for k in range(n):
            c = 2 + 4 * k + 3
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": FORMAT_TAUX}}},
                "fields": "userEnteredFormat.numberFormat"}})
        # une ligne de poste qui ne siege a aucun conseil porte la teinte
        # sable, sur ses quatre colonnes. Posee AVANT le rose et avant les
        # couleurs d'instance, qui la recouvrent quand les plages se
        # rencontrent.
        for r, c in meta.get("postes", []):
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                          "startColumnIndex": c, "endColumnIndex": c + 4},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(COULEUR_POSTE)}},
                "fields": "userEnteredFormat.backgroundColor"}})
        # ce qui ne fait pas le compte se lit en rose : un total qui ne
        # fait pas l'EPT administratif, une part qu'aucun service ne porte
        for r, c in meta["roses"]:
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(ROSE)}},
                "fields": "userEnteredFormat.backgroundColor"}})
        # les lignes de poste qui siegent reprennent la couleur de leur
        # instance, sur leurs quatre colonnes
        for r, c, instance in meta.get("sieges", []):
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                          "startColumnIndex": c, "endColumnIndex": c + 4},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(COULEURS_INSTANCES[instance])}},
                "fields": "userEnteredFormat.backgroundColor"}})

    # aucun filet vertical entre Departement, Service, Poste et Taux
    # d'une meme personne : la charte des bureaux en pose un entre chaque
    # colonne
    for k in range(n):
        c = 2 + 4 * k
        requetes.append(bords(meta["r_entete"], r_fin, c, c + 4, innerVertical=aucun))

    # un filet tirete entre deux postes, un filet fin avant le total
    if meta["r_attributs"]:
        r_total = meta["r_attributs"][-1]
        for r in meta["r_attributs"][1:-1]:
            requetes.append(bords(r, r + 1, 0, meta["largeur"], top=tirete))
        requetes.append(bords(r_total, r_total + 1, 0, meta["largeur"], top=fin))

    # un filet moyen entre deux personnes, de la ligne des noms au samedi
    for k in range(1, n):
        c = 2 + 4 * k
        requetes.append(bords(meta["r_entete"], r_fin, c, c + 1, left=filet))

    # « Présent » aux couleurs de la personne. Le teletravail garde ces
    # couleurs, eclaircies de moitie, avec le texte en italique gris :
    # jamais un fond blanc, qui est reserve au provisoire (Alberto,
    # 19.09.2026). Sheets n'applique que la premiere regle vraie, donc
    # la regle du teletravail est inseree devant celle de la presence.
    for k, nom in enumerate(meta["personnes"]):
        couleur = couleurs.get(nom)
        if not couleur:
            continue
        c = 2 + 4 * k
        plage = [{"sheetId": sid, "startRowIndex": meta["r_jours"], "endRowIndex": r_fin,
                  "startColumnIndex": c, "endColumnIndex": c + 4}]
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": plage,
            "booleanRule": {
                "condition": {"type": "TEXT_STARTS_WITH", "values": [{"userEnteredValue": MOT_PRESENT}]},
                "format": {"backgroundColor": _rvb(couleur)}},
        }, "index": 0}})
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": plage,
            "booleanRule": {
                "condition": {"type": "TEXT_CONTAINS", "values": [{"userEnteredValue": MARQUE_TELETRAVAIL}]},
                "format": {"backgroundColor": _rvb(_eclairci(couleur)),
                           "textFormat": {"italic": True, "foregroundColor": _rvb(GRIS)}}},
        }, "index": 0}})

    # La ligne de titre n'est pas une ligne d'etage. Depuis que la bande
    # a disparu, la charte des bureaux la prenait pour telle et y posait
    # son bandeau et ses filets verticaux (Alberto, 15.09.2026 : « ligne 1
    # pas de diviseurs verticaux des cellules, c'est moche »). Elle est
    # donc remise a plat en dernier, apres tout le reste : fond blanc,
    # aucune bordure, titre a gauche qui deborde sur les colonnes vides.
    requetes.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": meta["largeur"]},
        "cell": {"userEnteredFormat": {"backgroundColor": _rvb(BLANC)}},
        "fields": "userEnteredFormat.backgroundColor"}})
    requetes.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": 1},
        "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT",
                                       "wrapStrategy": "OVERFLOW_CELL"}},
        "fields": "userEnteredFormat.horizontalAlignment,userEnteredFormat.wrapStrategy"}})
    requetes.append(bords(0, 1, 0, meta["largeur"], innerVertical=aucun,
                          top=aucun, bottom=aucun, left=aucun, right=aucun))
    # les etiquettes des instances, sur leur couleur, en gras, centrees,
    # dans les deux cellules de gauche de la ligne des noms
    for r, c, instance in meta.get("legende", []):
        requetes.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "cell": {"userEnteredFormat": {"backgroundColor": _rvb(COULEURS_INSTANCES[instance]),
                                           "horizontalAlignment": "CENTER",
                                           "wrapStrategy": "WRAP",
                                           "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat.bold"}})
    # la ligne des noms est encadree en haut et en bas d'un filet moyen
    # (Alberto, 20.09.2026)
    requetes.append(bords(meta["r_entete"], meta["r_entete"] + 1, 0, meta["largeur"],
                          top=filet, bottom=filet))

    # onglet de consultation : protege, ecrit par le moteur
    requetes.append({"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": sid},
        "description": "Vue générée par le moteur, ne se saisit pas",
        "warningOnly": False,
        "requestingUserCanEdit": True,
        "editors": {"users": EDITEURS},
    }}})
    return requetes


def _page_blanche(sid: int, classeur: str = ID_LIEUX, onglet: str = ONGLET_VUE_ADMIN, sujet: str = ""):
    """Defusionne, efface formats, validations, regles, protections et
    bandes de l'onglet, puis ses valeurs : la vue se reecrit de zero."""
    requetes = [
        {"unmergeCells": {"range": {"sheetId": sid}}},
        {"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredFormat,dataValidation"}},
    ]
    for feuille in _etat_complet(classeur, sujet=sujet):
        if feuille["properties"]["sheetId"] != sid:
            continue
        for bande in feuille.get("bandedRanges", []):
            requetes.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for protection in feuille.get("protectedRanges", []):
            requetes.append({"deleteProtectedRange": {"protectedRangeId": protection["protectedRangeId"]}})
        for k in range(len(feuille.get("conditionalFormats", [])) - 1, -1, -1):
            requetes.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": k}})
    _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": requetes}).execute()
    _vider(onglet, classeur, sujet=sujet)


def _poser(classeur: str, onglet: str, grille, meta, couleurs, sujet: str = ""):
    """Ecrit la vue dans un onglet, de zero : page blanche, geometrie,
    valeurs, fusions, charte. Le meme rendu sert dans le classeur des
    lieux et dans celui que consultent les collaborateurs. Rend le
    sheetId de l'onglet ecrit."""
    proprietes = _onglets(classeur, sujet=sujet)
    if onglet not in proprietes:
        # a cote de l'occupation des bureaux quand elle est la, en fin de
        # classeur sinon
        voisin = proprietes.get(ONGLET_PATIENTS)
        creation = {"title": onglet, "gridProperties": {
            "rowCount": len(grille), "columnCount": max(meta["largeur"], 2)}}
        if voisin and "index" in voisin:
            creation["index"] = voisin["index"] + 1
        _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": [
            {"addSheet": {"properties": creation}}]}).execute()
        proprietes = _onglets(classeur, sujet=sujet)
    sid = proprietes[onglet]["sheetId"]
    _page_blanche(sid, classeur, onglet, sujet=sujet)
    # Degeler d'abord, redimensionner ensuite : en une seule requete,
    # Sheets confronte le nouveau nombre de colonnes aux colonnes encore
    # figees et refuse (« impossible de supprimer toutes les colonnes non
    # figées », 15.09.2026).
    _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 0, "frozenColumnCount": 0}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {
                "rowCount": len(grille), "columnCount": max(meta["largeur"], 2)}},
            "fields": "gridProperties.rowCount,gridProperties.columnCount"}},
    ]}).execute()
    _ecrire(onglet, "A1:" + _lettre(meta["largeur"] - 1) + str(len(grille)), grille, classeur, sujet=sujet)
    if meta["personnes"]:
        fusions = _fusions_admin(sid, grille, meta)
        if fusions:
            _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": fusions}).execute()
        habillage = _charte_admin(sid, grille, meta, couleurs)
        _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": habillage}).execute()
    return sid


# -------------------------------------------------------------------- outil

@mcp.tool()
@tolerant
def lieux_vue_admin(date: str = "", publier: bool = True, sujet: str = ""):
    """Reconstruit la vue des postes admin par personne, onglet Vue admin.

    Meme facture que la Vue actuelle, la personne en tete de colonne.
    Sous le nom, le cahier des charges tel que Registre - Postes admin le
    declare (service, poste, taux, une ligne par poste), avec son
    departement calcule depuis le service, et son total, confronte a
    l'EPT administratif de Registre - Engagements ; puis « Présent » ou
    « Télétravail » sur chaque demi-journee travaillee, fondu sur la
    journee. Toute personne a part administrative y figure ; sans postes
    declares, ses services du registre en tiennent lieu et elle est
    signalee. date permet de regarder un autre jour ; par defaut
    aujourd'hui. La meme vue est portee dans l'onglet « Postes admin »
    d'Almaval - Patients, que consultent les collaborateurs ; publier a
    faux s'en tient au classeur des lieux.
    """
    date_iso = _date(date) or _aujourdhui()
    grille, meta = _grille_admin(date_iso, sujet=sujet)
    couleurs = _couleurs_personnes(sujet=sujet)

    sid = _poser(ID_LIEUX, ONGLET_VUE_ADMIN, grille, meta, couleurs, sujet=sujet)
    lien_patients = ""
    if publier:
        sid_patients = _poser(ID_PATIENTS, ONGLET_ADMIN_PATIENTS, grille, meta, couleurs, sujet=sujet)
        lien_patients = ("https://docs.google.com/spreadsheets/d/" + ID_PATIENTS
                         + "/edit#gid=" + str(sid_patients))

    sans_couleur = [n for n in meta["personnes"] if not couleurs.get(n)]
    presences = sum(len(v) for v in meta["presences"].values())
    _journaliser([[_maintenant(), ONGLET_VUE_ADMIN, "Génération", date_iso, "", str(presences), "Terminé",
                   str(len(meta["personnes"])) + " personnes, " + str(len(meta["ecarts"]))
                   + " cahiers des charges à revoir, au " + _jolie_date(date_iso)]], sujet=sujet)
    return {
        "onglet": "https://docs.google.com/spreadsheets/d/" + ID_LIEUX + "/edit#gid=" + str(sid),
        "onglet_patients": lien_patients,
        "date": date_iso,
        "personnes": meta["personnes"],
        "lignes_de_postes": meta["n_postes"],
        "demi_journees_travaillees": presences,
        "cahiers_a_revoir": meta["ecarts"],
        "sans_postes_declares": meta["sans_cahier"],
        "services_sans_departement_reconnu": meta["sans_departement"],
        "sans_couleur": sans_couleur,
        "lignes": len(grille),
        "colonnes": meta["largeur"],
    }


# ------------------------------------------ passage par le pont de lieux_cycle
#
# Le client MCP de claude.ai garde en cache la liste des outils d'une
# conversation : un outil ajoute au serveur n'y apparait qu'a la
# conversation suivante. lieux_cycle route « action:nom clef=valeur » vers
# le pont d'outils_lieux ; ce module y greffe « vueadmin », avec
# date=aaaa-mm-jj en option, sans reecrire outils_lieux. Si la greffe
# echoue, l'outil lieux_vue_admin reste servi tel quel.

try:
    import shlex as _shlex

    import outils_lieux as _outils_lieux

    _pont_d_origine = _outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        try:
            morceaux = _shlex.split(brut)
        except ValueError:
            morceaux = brut.split()
        if morceaux and morceaux[0].lower() in ("vueadmin", "vue_admin"):
            params = dict(m.split("=", 1) for m in morceaux[1:] if "=" in m)
            publier = str(params.get("publier", "1")).lower() not in ("0", "faux", "false", "non")
            return lieux_vue_admin(date=params.get("date", ""), publier=publier)
        return _pont_d_origine(brut)

    _outils_lieux._pont = _pont
    print("[lieux admin] action vueadmin greffée au pont de lieux_cycle", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux admin] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


# ------------------------------ retrait du bloc des postes admin des grilles
#
# Alberto, 15.09.2026 au soir : « dans occupations bureaux in Patients tu
# dois donc enlever les postes admins, ca me va bien l'onglet a part. Dans
# planification aussi. Idem tout pour Propositions. » Les postes
# administratifs ne paraissent donc plus dans les grilles d'occupation
# (Propositions, Planification, Vue actuelle, et la copie publiee chez
# Patients) : la Vue admin, qui dit par personne son cahier des charges et
# sa presence, porte desormais seule cette information.
#
# Rien n'est detruit : le Referentiel - Bureaux garde ses postes, le
# registre Attributions garde ses lignes, et vider BATIMENTS_MASQUES les
# fait revenir au prochain passage de geometrie. Ce qui disparait, c'est
# la SAISIE d'une occupation administrative dans Propositions : elle se
# fait desormais dans le registre des attributions.
#
# La greffe enveloppe _squelette, qui construit la geometrie des grilles
# depuis le referentiel. outils_lieux l'a importee par son nom : c'est
# donc la reference de ce module-la qu'il faut remplacer, comme pour le
# pont ci-dessus.

BATIMENTS_MASQUES = (BATIMENT_ADMINISTRATION,)

try:
    import outils_lieux as _outils_lieux_geometrie

    _squelette_d_origine = _outils_lieux_geometrie._squelette

    def _squelette_sans_postes_admin(par_identifiant, annexes: bool = True):
        masques = {_normaliser(n) for n in BATIMENTS_MASQUES}
        retenus = {cle: fiche for cle, fiche in par_identifiant.items()
                   if _normaliser(fiche.get("nom_batiment", "")) not in masques}
        return _squelette_d_origine(retenus, annexes)

    _outils_lieux_geometrie._squelette = _squelette_sans_postes_admin
    print("[lieux admin] postes admin retirés des grilles d'occupation", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux admin] retrait des postes admin non greffé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
