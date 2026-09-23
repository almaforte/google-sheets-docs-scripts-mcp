"""Almaval - la porte des vignettes des villes, avec sa reprise.

Ce qui s'est passe le 23.09.2026. Le passage du matin a publie la Vue
actuelle chez les patients, bandeau compris, mais la pose des vignettes
y a rendu « reponse inattendue » : zero vignette, cinq villes sans leur
pictogramme. Le meme appel, relance a la main dans la minute qui a suivi,
a pose les cinq. La porte Apps Script du projet « Almaval - RH -
Onboarding des collaborateurs » repond donc par moments a cote, sans que
rien n'ait change ni du cote du classeur ni du cote des images.

Pourquoi une reprise, et pourquoi ici. Le passage quotidien tourne a 4h45
sans personne devant : un echec silencieux laisse la vue des patients sans
ses pictogrammes toute la journee, et c'est la vue que tout le monde
regarde. Une seconde tentative, trois secondes plus tard, suffit a couvrir
ce genre d'aleas de transport.

Correction ici plutot que dans outils_lieux_villes.py, selon la regle
posee dans outils_lieux_zz_passage.py : la moindre retouche d'un gros
module coute la retransmission de tout le fichier par l'API GitHub, avec
le risque que cela comporte pour un fichier qui tourne. Ce module est
charge apres lui, l'ordre alphabetique le voulant ainsi, et remplace
_poser_les_vignettes dans ses globales : les deux appelants, l'habillage
de la Vue actuelle et la reprise chez les patients, le cherchent par ce
nom et prennent donc la version reprise sans rien savoir d'elle.

Ce que la reprise ne fait PAS. Elle ne retente pas une vignette
individuellement manquee, que le retour nomme dans « manquees » : ce
cas-la vient de l'image elle-meme, pas du transport, et une seconde
tentative ne changerait rien.
"""

import time as _time

import outils_lieux_villes as _villes

try:
    _poser_amont = _villes._poser_les_vignettes

    def _poser_les_vignettes_avec_reprise(cibles):
        """Deux tentatives au lieu d'une, trois secondes d'ecart.

        Le retour est celui de la tentative qui a abouti, augmente du
        nombre de tentatives quand il en a fallu deux, de sorte que le
        compte rendu du passage quotidien garde la trace de l'aleas.
        """
        retour = _poser_amont(cibles)
        if not isinstance(retour, dict) or not retour.get("erreur"):
            return retour
        print("[lieux vignettes] première tentative sans effet ("
              + str(retour.get("erreur")) + "), reprise dans 3 s", flush=True)
        _time.sleep(3)
        repris = _poser_amont(cibles)
        if isinstance(repris, dict):
            repris["tentatives"] = 2
            if repris.get("erreur"):
                repris["premiere_erreur"] = retour.get("erreur")
        return repris

    _villes._poser_les_vignettes = _poser_les_vignettes_avec_reprise
    print("[lieux vignettes] pose des vignettes greffée : deux tentatives", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux vignettes] reprise non greffée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
