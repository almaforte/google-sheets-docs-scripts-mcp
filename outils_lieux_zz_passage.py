"""Almaval - moteur des lieux : ce que le passage du matin devait encore faire.

Deux gestes manquaient au passage quotidien, constate le 16.09.2026.

Le ponctuel des agendas de salles, depose dans Almaval - Patients par
outils_lieux_ponctuel. Sans lui, la photo du jour de l'onglet Occupation
bureaux ne montre que le standard des contrats et les absences : un
colloque, une formation, une location ou une indisponibilite pour
travaux, poses la veille dans l'agenda d'une salle, n'apparaissent
jamais. Le depot se refait donc chaque matin, sur les huit semaines a
venir.

La vue des postes admin, qui lit l'EPT administratif et sa ventilation
par service dans Registre - Engagements, et le nom de chaque poste dans
Registre - Postes admin. Elle se regenere au passage du matin, dans le
classeur des lieux et dans Almaval - Patients, pour qu'un taux corrige
se voie sans qu'on ait rien a lancer.

UN TROISIEME GESTE, RETIRE LE JOUR MEME.
Alberto a demande le 16.09.2026 que Propositions redevienne la porte
d'entree unique de l'occupation des bureaux, l'aplatissement de la
grille vers le registre des attributions ayant ete debranche a la
migration du 13.09. L'aplatissement a donc ete ajoute en tete de ce
passage, puis RETIRE dans l'heure : a l'essai, le registre Attributions
est ressorti avec sa seule ligne d'en-tete, ses 713 lignes disparues.
Restaurees depuis l'onglet masque « Archive - Attributions 16092026 »,
pris juste avant l'essai.

La cause n'est pas etablie. Deux pistes, a departager sur une COPIE du
classeur et jamais en production : l'appel a ete coupe cote client au
bout d'une minute alors que le serveur ecrivait encore, et la lecture
est tombee entre l'effacement de l'onglet et sa reecriture ; ou
_lire_la_grille rend desormais une grille vide, ce qui ferait ecrire un
registre vide. La seconde piste est la plus inquietante et merite d'etre
ecartee d'abord, la geometrie de Propositions ayant change le 15.09 avec
le retrait du bloc ADMIN des grilles d'occupation.

Tant que ce n'est pas tranche, le passage du matin NE TOUCHE PAS au
registre autrement que par la consolidation, qui n'efface rien. Un nom
ecrit dans Propositions ne remonte donc pas tout seul : il faut demander
« action:construire ».

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

import outils_lieux_admin
import outils_lieux_ponctuel
import outils_lieux_transitoire


_passage_d_origine = outils_lieux_transitoire.lieux_passage_quotidien


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

    Consolide le registre Attributions, repose sa charte, regenere la Vue
    actuelle et la Planification, publie la vue du jour dans Almaval -
    Patients et renvoie les sites vers Registre - Engagements, puis
    depose le ponctuel des agendas de salles et regenere la vue des
    postes admin dans les deux classeurs. Lance chaque matin par la tache
    planifiee « Almaval - Lieux - Passage quotidien ».

    Il n'aplatit PAS Propositions vers le registre : voir la note en tete
    de module, l'essai du 16.09.2026 a vide le registre.
    """
    resultat = _passage_d_origine(sujet=sujet)
    if not isinstance(resultat, dict):
        resultat = {"passage": resultat}
    resultat["ponctuel_agendas"] = _tenter(
        "ponctuel des agendas", outils_lieux_ponctuel.lieux_ponctuels_agendas, sujet=sujet)
    resultat["vue_admin"] = _tenter(
        "vue des postes admin", outils_lieux_admin.lieux_vue_admin, publier=True, sujet=sujet)
    return resultat


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
      + " : ponctuel des agendas et vue des postes admin", flush=True)
