"""Almaval - moteur des lieux : ce que le passage du matin devait encore faire.

Quatre gestes manquaient au passage quotidien, constate le 16.09.2026.

L'APLATISSEMENT DE PROPOSITIONS vers le registre des attributions. Depuis
la migration du 13.09.2026, le passage du matin se contentait de
consolider le registre : un nom ecrit dans Propositions n'y remontait
plus tout seul, il fallait demander « action:construire ». La chaine
etait donc coupee a son premier maillon, et l'occupation des bureaux
n'avait plus une porte d'entree unique. Alberto a tranche le 16.09.2026
(« fais-le, attributions n'a pas encore ete utilise a ce jour donc ca
peut changer ») : Propositions redevient la seule saisie de la semaine
type, le registre en garde la memoire datee, tout le reste en decoule.

LE DEFAUT QUI A VIDE LE REGISTRE, ET SA CORRECTION.
Au premier essai, le registre Attributions est ressorti avec sa seule
ligne d'en-tete, ses 713 lignes disparues. Restaurees depuis l'onglet
masque « Archive - Attributions 16092026 », pris juste avant l'essai.

La cause, trouvee au second essai parce que l'erreur est enfin remontee
en clair : « Requested writing within range [Attributions!A2:K712], but
tried writing to column [L] ». Le registre a gagne deux colonnes le
13.09.2026, « Fin selon registre RH » et « Origine », ecrites par la
consolidation. L'aplatissement, lui, ecrit onze colonnes, A a K. Il relit
les lignes existantes pour en garder les dates, et les complete par
`list(ligne) + [""] * (11 - len(ligne))` : avec treize colonnes lues, ce
compte est negatif, la ligne reste large de treize, et l'ecriture deborde
sur L. Or la plage A2:K a deja ete EFFACEE juste avant. L'ecriture
echoue, et le registre reste vide.

Correction ici plutot que dans outils_lieux.py, dont la moindre retouche
coute la retransmission de soixante-douze kilo-octets par l'API GitHub :
_ecrire_registre est enveloppe pour ramener chaque ligne a exactement
onze colonnes. C'est l'invariant que sa plage suppose depuis toujours.
Les colonnes L et M ne sont pas perdues : la consolidation, qui les ecrit
par _ecrire_registre_large, passe avant et apres l'aplatissement.

LEcON : un geste qui efface avant d'ecrire doit etre sur de son
ecriture. Effacer et ecrire ne sont pas deux gestes, c'en est un seul,
et il n'est pas atomique ici.

LE PONCTUEL DES AGENDAS de salles, depose dans Almaval - Patients par
outils_lieux_ponctuel. Sans lui, la photo du jour de l'onglet Occupation
bureaux ne montre que le standard des contrats et les absences : un
colloque, une formation, une location ou une indisponibilite pour
travaux, poses la veille dans l'agenda d'une salle, n'apparaissent
jamais. Le depot se refait donc chaque matin, sur les huit semaines a
venir.

LE REFERENTIEL DES POSTES, recopie d'Almaval - Listes vers Almaval -
Collaborateurs - Effectif. Le vocabulaire de la maison vit dans Almaval -
Listes, onglet « Postes - Referentiel » : une ligne par poste, avec son
departement calcule, son service, son sous-service et l'intitule d'EPT
normalise « EPT Service - Poste » demande par Alberto le 16.09.2026. Les
EPT, eux, vivent dans l'Effectif. Plutot qu'un IMPORTRANGE entre les deux
classeurs, fragile et silencieux quand il casse, le moteur en depose une
copie dans l'onglet masque « Aide - Postes referentiel » de l'Effectif,
comme il est deja fait ailleurs pour les comptes MediOnline. Registre -
Postes admin et l'onglet « Index des EPT » lisent cette copie locale.

Depuis le 16.09.2026 au soir la copie porte NEUF colonnes du referentiel,
deposees de B a J, la Remarque comprise. Le referentiel a gagne ce
jour-la « Intitule EPT abrege », le nom rapide destine au classeur de
Gestion, et « Destination de l'EPT », qui dit si le temps de ce poste
conditionne la facturation d'une seance (valeur Therapies : encadrement,
supervision, ADC, direction medicale, service social) ou s'il fait
tourner les services de support (valeur Support). L'index des EPT s'en
sert pour sommer separement ce qui se budgete sur les therapies et ce qui
reste charge de structure, sans qu'aucune saisie soit dupliquee : la
destination est une propriete du POSTE, jamais de la personne.

LA CARTE SERVICE VERS DEPARTEMENT SE NOURRIT DU REFERENTIEL. Le meme
16.09.2026, Alberto a renomme le service Partenariat en Relations et pose
la regle generale : tout prend depuis le referentiel, ses trois colonnes
Departement, Service, Poste. Or SERVICES_VERS_DEPARTEMENT, dans
outils_lieux_admin, etait une carte figee dans le code, qui ne pouvait
donc pas connaitre un service renomme. Elle est desormais rafraichie a
chaque copie du referentiel, depuis les colonnes Departement et Service
elles-memes. Un garde-fou est indispensable : la colonne Departement du
referentiel est une formule qui renvoie « service inconnu » quand la
carte ignore le service, et sans filtre cette valeur se reinjecterait
dans la carte, figeant l'erreur pour de bon. Seules les quatre valeurs de
departement reconnues entrent donc dans la carte. Les cles posees dans le
code restent en place, elles servent de filet quand la vue des postes
admin est appelee seule, avant toute copie du referentiel.

LA VUE DES POSTES ADMIN, qui lit l'EPT administratif et sa ventilation
par service dans Registre - Engagements, et le nom de chaque poste dans
Registre - Postes admin. Elle se regenere au passage du matin, dans le
classeur des lieux et dans Almaval - Patients, pour qu'un taux corrige
se voie sans qu'on ait rien a lancer.

Un mot sur la porte d'entree de la part administrative, parce que je m'y
suis trompe le 16.09.2026 au matin. La ventilation des EPT par service se
saisit dans l'onglet « Saisie - Collaborateurs » d'Almaval -
Collaborateurs - Gestion, avec tout le reste du dossier du collaborateur
et ses mutations ; le moteur d'onboarding la porte dans Registre -
Engagements. J'avais transforme ces colonnes du registre en formules
lisant Registre - Postes admin, ce qui creait une troisieme porte et,
pire, exposait des formules matricielles a l'ecriture du moteur
d'onboarding. Revenu en arriere le jour meme : le registre garde des
valeurs, Registre - Postes admin ne declare que le NOM du poste tenu dans
chaque service.

Ce module ne reecrit pas outils_lieux_transitoire : il enveloppe son
passage quotidien et remplace l'outil deja enregistre, exactement comme
transitoire enveloppe outils_lieux. Son nom le fait charger apres lui,
bootstrap important les modules outils_*.py dans l'ordre alphabetique.

Un echec de l'un de ces gestes ne fait pas tomber le passage : il est
rendu en clair dans le resultat, a sa place, et le reste du passage
tient. C'est la lecon du 15.09.2026 sur les echecs silencieux, prise
dans l'autre sens : ne rien taire, mais ne pas tout arreter pour un
depot d'agenda.
"""

from main import mcp, tolerant

import outils_lieux
import outils_lieux_admin
import outils_lieux_ponctuel
import outils_lieux_transitoire
from outils_lieux_socle import ID_EFFECTIF, _ecrire, _feuilles, _lire, _normaliser


LARGEUR_REGISTRE = 11

ID_LISTES = outils_lieux_admin.ID_LISTES
ONGLET_REFERENTIEL_POSTES = "Postes - Référentiel"
ONGLET_AIDE_POSTES = "Aide - Postes référentiel"
# La copie occupe B a J ; la colonne A de l'onglet d'aide porte une
# formule matricielle (la cle service|poste) qui ne doit jamais etre
# ecrasee par une valeur, sous peine de #REF!.
COLONNES_AIDE = 9

# Les quatre seules valeurs de departement qui ont le droit d'entrer dans
# SERVICES_VERS_DEPARTEMENT. Tout le reste, a commencer par le « service
# inconnu » que renvoie la formule du referentiel, est ecarte.
DEPARTEMENTS_CONNUS = (
    outils_lieux_admin.AUTORITE,
    outils_lieux_admin.DEPARTEMENT_SOINS,
    outils_lieux_admin.DEPARTEMENT_ADMINISTRATIF,
    outils_lieux_admin.DEPARTEMENT_RESSOURCES,
)

# Filet pose au chargement, pour le cas ou la vue des postes admin serait
# appelee avant toute copie du referentiel. Le service Partenariat a ete
# renomme Relations par Alberto le 16.09.2026.
outils_lieux_admin.SERVICES_VERS_DEPARTEMENT.setdefault(
    _normaliser("Relations"), outils_lieux_admin.DEPARTEMENT_RESSOURCES)

_ecrire_registre_d_origine = outils_lieux._ecrire_registre


def _ecrire_registre_onze_colonnes(lignes, sujet: str = ""):
    """Ecrit le registre en garantissant onze colonnes par ligne.

    La plage d'ecriture est A2:K. Une ligne plus large deborde sur L et
    fait echouer l'appel apres que la plage a ete effacee, ce qui vide le
    registre ; une ligne plus courte laisse des cellules non ecrites.
    """
    calibrees = [(list(l) + [""] * LARGEUR_REGISTRE)[:LARGEUR_REGISTRE] for l in lignes]
    return _ecrire_registre_d_origine(calibrees, sujet=sujet)


outils_lieux._ecrire_registre = _ecrire_registre_onze_colonnes


def _rafraichir_carte_des_services(corps):
    """Met a jour SERVICES_VERS_DEPARTEMENT depuis le referentiel copie.

    Le referentiel est la source unique du couple Departement, Service :
    un service renomme doit donc suffire a corriger la carte, sans
    retoucher le code. Seules les valeurs de departement reconnues
    entrent, pour que le « service inconnu » renvoye par la formule du
    referentiel ne se reinjecte jamais dans la carte.
    """
    poses = 0
    for ligne in corps:
        departement = str((list(ligne) + [""] * 2)[0] or "").strip()
        service = str((list(ligne) + [""] * 2)[1] or "").strip()
        if not service or departement not in DEPARTEMENTS_CONNUS:
            continue
        cle = _normaliser(service)
        if outils_lieux_admin.SERVICES_VERS_DEPARTEMENT.get(cle) != departement:
            poses += 1
        outils_lieux_admin.SERVICES_VERS_DEPARTEMENT[cle] = departement
    return poses


@mcp.tool()
@tolerant
def lieux_referentiel_postes(sujet: str = ""):
    """Recopie le referentiel des postes d'Almaval - Listes vers l'Effectif.

    Source : Almaval - Listes, onglet « Postes - Referentiel », colonnes
    Departement, Service, Sous-service, Poste, Intitule EPT, Actif,
    Remarque, Intitule EPT abrege, Destination de l'EPT.
    Cible : Almaval - Collaborateurs - Effectif, onglet masque « Aide -
    Postes referentiel », colonnes B a J. Sa colonne A, la cle
    service|poste, est une formule matricielle et n'est jamais touchee.

    Rafraichit au passage la carte service vers departement, pour qu'un
    service renomme dans le referentiel n'oblige pas a retoucher le code.

    Lu par Registre - Postes admin, qui en tire le sous-service, le
    departement et l'intitule normalise de chaque poste, et par l'onglet
    « Index des EPT », qui somme les EPT par departement, service,
    sous-service et poste, puis separe ce qui est destine aux therapies
    de ce qui fait tourner les services de support.
    """
    lignes = _lire(ONGLET_REFERENTIEL_POSTES, ID_LISTES, sujet=sujet)
    if len(lignes) < 2:
        return {"erreur": "référentiel vide ou introuvable", "onglet": ONGLET_REFERENTIEL_POSTES}
    corps = []
    for ligne in lignes[1:]:
        if not str((list(ligne) + [""] * 2)[1] or "").strip():
            continue  # pas de service : ligne vide du référentiel
        corps.append((list(ligne) + [""] * COLONNES_AIDE)[:COLONNES_AIDE])
    if not corps:
        return {"erreur": "aucune ligne de service dans le référentiel"}
    services_poses = _rafraichir_carte_des_services(corps)
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_EFFECTIF,
        range="'" + ONGLET_AIDE_POSTES + "'!B2:J",
        body={},
    ).execute()
    _ecrire(ONGLET_AIDE_POSTES, "B2:J" + str(len(corps) + 1), corps,
            classeur=ID_EFFECTIF, sujet=sujet)
    return {"postes": len(corps),
            "services_mis_a_jour": services_poses,
            "source": "https://docs.google.com/spreadsheets/d/" + ID_LISTES + "/edit",
            "cible": "https://docs.google.com/spreadsheets/d/" + ID_EFFECTIF + "/edit"}


def _tenter(nom, fonction, **arguments):
    """Lance un geste du passage sans laisser son echec emporter le reste."""
    try:
        return fonction(**arguments)
    except Exception as exc:  # noqa: BLE001
        print("[lieux passage] " + nom + " en echec : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return {"erreur": type(exc).__name__, "detail": str(exc)[:300]}


def lieux_passage_quotidien(sujet: str = ""):
    """Le passage du matin, tout compris, sans confirmation.

    Aplatit d'abord Propositions vers le registre des attributions, de
    sorte qu'un nom ecrit dans la grille remonte de lui-meme : une case
    qui apparait ouvre une ligne datee du jour meme, une case qui
    disparait ferme la sienne au jour meme, les deux dates restant a
    corriger a la main dans le registre, et une ligne portant « Registre
    seul » n'est jamais close.

    Consolide ensuite le registre, repose sa charte, regenere la Vue
    actuelle et la Planification, publie la vue du jour dans Almaval -
    Patients et renvoie les sites vers Registre - Engagements, puis
    depose le ponctuel des agendas de salles, recopie le referentiel des
    postes vers l'Effectif et regenere la vue des postes admin dans les
    deux classeurs. Lance chaque matin par la tache planifiee
    « Almaval - Lieux - Passage quotidien ».
    """
    aplatissement = _tenter(
        "aplatissement de Propositions",
        outils_lieux_transitoire.lieux_construire_attributions, sujet=sujet)
    resultat = _passage_d_origine(sujet=sujet)
    if not isinstance(resultat, dict):
        resultat = {"passage": resultat}
    resultat["aplatissement_propositions"] = aplatissement
    resultat["ponctuel_agendas"] = _tenter(
        "ponctuel des agendas", outils_lieux_ponctuel.lieux_ponctuels_agendas, sujet=sujet)
    resultat["referentiel_postes"] = _tenter(
        "référentiel des postes", lieux_referentiel_postes, sujet=sujet)
    resultat["vue_admin"] = _tenter(
        "vue des postes admin", outils_lieux_admin.lieux_vue_admin, publier=True, sujet=sujet)
    return resultat


_passage_d_origine = outils_lieux_transitoire.lieux_passage_quotidien

_remplace = False
try:
    _remplace = outils_lieux_transitoire._remplacer_outil(
        "lieux_passage_quotidien", lieux_passage_quotidien)
    if _remplace:
        # Le routeur « action:quotidien » de lieux_cycle appelle le nom tel
        # qu'il vit dans les globales de transitoire : il faut donc l'y
        # remplacer aussi, sans quoi le pont continuerait de servir l'ancien
        # passage aux clients dont la liste d'outils n'est pas a jour.
        outils_lieux_transitoire.lieux_passage_quotidien = tolerant(lieux_passage_quotidien)
except Exception as _exc:  # noqa: BLE001
    print("[lieux passage] passage quotidien non remplacé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
print("[lieux passage] passage quotidien " + ("enrichi" if _remplace else "inchangé")
      + " : aplatissement, ponctuel, référentiel des postes, vue des postes admin", flush=True)
