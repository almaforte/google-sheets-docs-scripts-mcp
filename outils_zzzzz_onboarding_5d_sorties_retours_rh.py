"""Almaval - sorties : annonces LPP, AVS et AXA selon les retours des RH, 29.09.2026.

Revision des taches 300, 310 et 380 du module outils_zzzzz_onboarding_5b_sorties_taches,
chargee apres lui (et apres 5c) par l'ordre alphabetique des modules. Elle remplace, dans
l'espace de noms du module 5b, les fonctions t300_lpp, t310_avs et t380_axa ; les lambdas
du registre MOTEURS les retrouvent par leur nom.

Pourquoi (retours de Mathilde Baillifard du 29.09.2026, document « TEST Nouveau processus
d'entree ») :
  300 et 310  l'annonce de sortie LPP (Medpension, Elite pour le surobligatoire) et AVS
      (Medisuisse) se fait directement sur les portails en ligne, plus par courriel ; on en
      profite pour corriger la LPP si besoin. Le robot ne depose plus de brouillon : il met
      la tache En cours avec les donnees a saisir sur le portail.
  380 AXA n'est informee QUE s'il y a un cas de maladie ou d'accident ouvert, et cela se
      fait aussi sur le portail. Le robot lit « Absences - Registre » : sans arret maladie
      ou accident en cours, ou fini moins de 30 jours avant la sortie, la tache passe Sans
      objet ; sinon En cours avec le cas. La liste Swibeco (acces aux avantages) est la
      tache 500, tenue par Anne-Marie, sans lien avec AXA.
Rien n'est envoye, rien n'est supprime ; un etat n'est jamais abaisse (marquer_taches).
"""

import datetime
import re

import outils_zzzzz_onboarding_5b_sorties_taches as t5b

_s = t5b._s
_nombre = t5b._nombre
_fr = t5b._fr
_chf = t5b._chf
_jour_texte = t5b._jour_texte
_poser = t5b._poser
_onglet_partage = t5b._onglet_partage
_est_date = t5b._est_date
date_de = t5b.date_de
en_jour = t5b.en_jour
meme_texte = t5b.meme_texte
normaliser = t5b.normaliser
lire_onglet = t5b.lire_onglet

JOURS_CAS_OUVERT_AXA = 30
ONGLET_ABSENCES = "Absences - Registre"


def _donnees_portail(sortie, avec_salaire=True):
    """Les donnees a reporter sur un portail d'organisme, en une phrase."""
    p = sortie.personne()
    e = sortie.engagement
    morceaux = ["AVS " + (_s(p.get("AVS")) or "à compléter"),
                "entrée le " + en_jour(e.get("Date de début")),
                "sortie le " + _jour_texte(sortie.date_sortie)]
    if avec_salaire:
        morceaux.append("salaire annuel effectif " + _chf(_nombre(e.get("Salaire annuel effectif"))))
        morceaux.append("taux " + _fr(_nombre(e.get("EPT total")) * 100, 0) + " %")
    return ", ".join(m for m in morceaux if m)


def t300_lpp(sortie, dest):
    return _poser(sortie, 300, "En cours",
                  "À annoncer sur le portail en ligne de Medpension (et d'Elite pour le surobligatoire le cas échéant), "
                  "en profitant pour corriger la LPP si besoin. Données : " + _donnees_portail(sortie) + ". Puis Fait")


def t310_avs(sortie, dest):
    return _poser(sortie, 310, "En cours",
                  "À annoncer sur le portail en ligne de Medisuisse. Données : " + _donnees_portail(sortie) + ". Puis Fait")


def _cas_maladie_accident(sortie):
    """Absences maladie ou accident encore ouvertes, ou finies moins de 30 jours avant la sortie. None si illisible."""
    def lire():
        try:
            return lire_onglet(ONGLET_ABSENCES).lignes
        except Exception:  # noqa: BLE001
            return None
    lignes = _onglet_partage(sortie.ctx, "absences_registre_5d", lire)
    if lignes is None:
        return None
    reference = sortie.date_sortie or sortie.aujourdhui
    seuil = reference - datetime.timedelta(days=JOURS_CAS_OUVERT_AXA)
    cas = []
    for l in lignes:
        if not meme_texte(l.get("Initiales"), sortie.init):
            continue
        motif = normaliser(_s(l.get("Motif d'absence")) + " " + _s(l.get("Famille")))
        if not re.search(r"maladie|accident|incapacit", motif):
            continue
        if re.search(r"refus|annul", normaliser(l.get("Statut de la demande"))):
            continue
        fin = date_de(l.get("Date de fin")) if _est_date(l.get("Date de fin")) else None
        try:
            if fin is not None and fin < seuil:
                continue
        except TypeError:
            if fin is not None and datetime.datetime(fin.year, fin.month, fin.day) < datetime.datetime(seuil.year, seuil.month, seuil.day):
                continue
        debut = date_de(l.get("Date de début")) if _est_date(l.get("Date de début")) else None
        cas.append(_s(l.get("Motif d'absence")) + (" du " + _jour_texte(debut) if debut else "")
                   + (" au " + _jour_texte(fin) if fin else " (sans date de fin)"))
    return cas


def t380_axa(sortie, dest):
    cas = _cas_maladie_accident(sortie)
    if cas is None:
        return _poser(sortie, 380, "", "Registre des absences illisible ce passage : vérifier s'il y a un cas de maladie ou d'accident ouvert")
    if not cas:
        return _poser(sortie, 380, "Sans objet",
                      "Aucun cas de maladie ou d'accident ouvert au registre des absences : rien à annoncer à AXA. "
                      "Si un cas est ouvert chez AXA, rouvrir la tâche et l'annoncer sur le portail en ligne")
    return _poser(sortie, 380, "En cours",
                  "Cas ouvert : " + " ; ".join(cas[:5]) + ". Annoncer la sortie à AXA sur le portail en ligne, en rattachant le cas. "
                  "Données : " + _donnees_portail(sortie) + ". Puis Fait")


# Greffe dans l'espace de noms du module 5b : les lambdas du registre MOTEURS
# appellent t300_lpp, t310_avs et t380_axa par leur nom global.
t5b.t300_lpp = t300_lpp
t5b.t310_avs = t310_avs
t5b.t380_axa = t380_axa
