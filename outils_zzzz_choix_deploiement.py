# -*- coding: utf-8 -*-
"""Correctif du choix de l'adresse d'application web d'un projet Apps Script.

Constaté le 23.09.2026, sur deux projets à la fois : le déploiement de
TÊTE d'un projet, celui dont le numéro de version est nul, n'accepte pas
les appels authentifiés par jeton. Il répond 403, ou rend la page de
connexion Google, que run_script_action traduisait alors en « Projet non
autorisé » et qui envoyait à tort ouvrir l'éditeur Apps Script. Les
déploiements VERSIONNÉS des mêmes projets, eux, répondaient 200.

_url_application_web, dans bootstrap.py, prenait la tête en priorité et
ne retombait sur une version publiée qu'à défaut. Tous les appels par
run_script_action échouaient donc, quel que soit le projet.

Ce module rétablit la règle déjà écrite dans la docstring de
update_web_app_deployment : prendre le déploiement versionné au numéro le
plus élevé, et ne retomber sur la tête qu'à défaut de tout autre.

Le correctif est posé ici, et non dans bootstrap.py, parce que ce fichier
demande expressément qu'on ne le réécrive pas en entier pour trois
lignes, manipulation qui finit par le tronquer sans prévenir.
"""

import sys

_NOMS_HOTES = ("__main__", "bootstrap")
_ATTRIBUT = "_url_application_web"


def _module_hote():
    """Le module qui porte _url_application_web.

    bootstrap.py est lancé par « python bootstrap.py », il vit donc sous
    le nom __main__ et non sous le nom bootstrap. L'importer par son nom
    le réexécuterait en entier et enregistrerait ses outils une seconde
    fois, on le retrouve donc dans sys.modules.
    """
    for nom in _NOMS_HOTES:
        module = sys.modules.get(nom)
        if module is not None and hasattr(module, _ATTRIBUT):
            return module
    return None


def _url_application_web(script_id):
    """L'adresse d'exécution de l'application web, version publiée d'abord."""
    hote = _module_hote()
    if hote is None:
        return ""
    liste = hote._script().projects().deployments().list(scriptId=script_id).execute()
    tete, versionne = None, None
    for deploiement in liste.get("deployments", []):
        url = ""
        for entree in deploiement.get("entryPoints", []):
            if entree.get("entryPointType") == "WEB_APP":
                url = entree.get("webApp", {}).get("url", "")
        if not url:
            continue
        version = deploiement.get("deploymentConfig", {}).get("versionNumber")
        if version is None:
            tete = url
        elif versionne is None or version > versionne[0]:
            versionne = (version, url)
    if versionne:
        return versionne[1]
    if tete:
        return tete
    return ""


_hote = _module_hote()
if _hote is not None:
    setattr(_hote, _ATTRIBUT, _url_application_web)
    print(
        "[outils_zzzz_choix_deploiement] choix corrige : version publiee "
        "d'abord, deploiement de tete en dernier recours",
        flush=True,
    )
else:
    print(
        "[outils_zzzz_choix_deploiement] module hote introuvable, "
        "correctif NON pose",
        flush=True,
    )
