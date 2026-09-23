"""Almaval - édition chirurgicale des projets Apps Script.

Raison d'être

Le 23.09.2026, la bascule du vocabulaire vers « pôle » a buté sur un mur
qui n'est pas celui qu'on croit. L'API Apps Script n'a pas d'écriture
partielle : toute modification passe par un cycle lire, modifier, tout
réécrire. Ce n'est pas le problème, le serveur sait déjà le faire.

Le problème est que ce cycle passait par le CONTEXTE du modèle. Pour
changer treize mots dans trois fichiers de 1050, 608 et 708 lignes, il
fallait lire trois mille lignes de code de production, puis les retaper
intégralement dans l'appel d'écriture. Le risque tombait alors sur la
recopie, pas sur le changement, et la seule décision prudente était de
renoncer et de contourner par des enveloppes.

Ce module déplace le cycle là où il doit vivre : dans le serveur. Le
modèle envoie le texte cherché et le texte neuf, le serveur lit, compte,
remplace, écrit et relit. Rien d'autre ne circule.

Le même raisonnement vaut pour la lecture. get_script_content rend le
projet entier, soit 1,3 Mo pour le projet d'onboarding des
collaborateurs : inutilisable pour retrouver une ligne. script_chercher
et script_lire_lignes rendent ce qu'on demande, et rien de plus.

Garde-fous

Toute écriture passe par _lire_projet_verifie, le garde-fou posé après
l'incident du 05.09.2026 où une relecture avait rendu un autre projet et
où la réécriture avait effacé soixante-trois fichiers.

Le remplacement est TOUT OU RIEN et refuse le doute. Un texte cherché
introuvable, ou trouvé un nombre de fois différent de ce qui était
annoncé, fait échouer l'appel entier sans rien écrire. Un remplacement
qui ne changerait rien est refusé aussi : il signale presque toujours
qu'on ne modifie pas le fichier qu'on croit.

Les fichiers non visés sont recopiés octet pour octet, manifeste compris.
Après l'écriture, le projet est relu et la réponse dit si ce qui a été
relu est exactement ce qui a été écrit.
"""

import json
import re
from typing import Any

from main import mcp, tolerant, _script, _lire_projet_verifie


LIMITE_EXTRAIT = 300
MAX_RESULTATS = 400


def _extrait(texte: Any, limite: int = LIMITE_EXTRAIT) -> str:
    texte = str(texte)
    if len(texte) <= limite:
        return texte
    return texte[:limite] + " […]"


def _trouver_fichier(fichiers: list, nom: str) -> dict:
    for fichier in fichiers:
        if fichier.get("name") == nom:
            return fichier
    presents = ", ".join(sorted(str(f.get("name")) for f in fichiers))
    raise RuntimeError(
        "fichier introuvable dans ce projet : « " + str(nom) + " ». "
        "Noms présents : " + presents
    )


def _noms_demandes(fichiers: str) -> list:
    return [n.strip() for n in str(fichiers or "").split(",") if n.strip()]


def _lignes_des_occurrences(source: str, motif: str) -> list:
    lignes = []
    depart = 0
    while True:
        position = source.find(motif, depart)
        if position < 0:
            return lignes
        lignes.append(source.count("\n", 0, position) + 1)
        depart = position + max(len(motif), 1)


def _normaliser_remplacements(remplacements: Any) -> list:
    """Accepte une liste de dictionnaires, une liste de paires, ou du JSON.

    Forme de référence, la plus lisible :
        [{"ancien": "...", "nouveau": "...", "occurrences": 1}]
    « occurrences » vaut 1 par défaut, ce qui impose que le texte cherché
    soit unique dans le fichier. Mettre 0 remplace toutes les occurrences.
    """
    valeur = remplacements
    if isinstance(valeur, str):
        texte = valeur.strip()
        if not texte:
            raise RuntimeError("aucun remplacement fourni")
        try:
            valeur = json.loads(texte)
        except Exception:
            raise RuntimeError(
                "remplacements illisible : attendu une liste JSON de la forme "
                '[{"ancien": "...", "nouveau": "...", "occurrences": 1}]'
            )
    if isinstance(valeur, dict):
        valeur = [valeur]
    if not isinstance(valeur, list) or not valeur:
        raise RuntimeError("remplacements doit être une liste non vide")

    sortie = []
    for rang, brut in enumerate(valeur, start=1):
        if isinstance(brut, (list, tuple)):
            if len(brut) < 2:
                raise RuntimeError(
                    "remplacement " + str(rang) + " : paire incomplète, il faut "
                    "au moins le texte cherché et le texte neuf"
                )
            ancien = str(brut[0])
            nouveau = str(brut[1])
            occurrences = int(brut[2]) if len(brut) > 2 else 1
        elif isinstance(brut, dict):
            ancien = brut.get("ancien", brut.get("avant", brut.get("old")))
            nouveau = brut.get("nouveau", brut.get("apres", brut.get("new")))
            if ancien is None or nouveau is None:
                raise RuntimeError(
                    "remplacement " + str(rang) + " : il faut « ancien » et "
                    "« nouveau »"
                )
            ancien = str(ancien)
            nouveau = str(nouveau)
            occurrences = int(brut.get("occurrences", brut.get("nombre", 1)) or 0)
        else:
            raise RuntimeError(
                "remplacement " + str(rang) + " : format non reconnu, attendu un "
                "dictionnaire ou une paire"
            )
        if ancien == "":
            raise RuntimeError(
                "remplacement " + str(rang) + " : le texte cherché est vide"
            )
        if occurrences < 0:
            occurrences = 0
        sortie.append(
            {"ancien": ancien, "nouveau": nouveau, "occurrences": occurrences}
        )
    return sortie


def _appliquer(source: str, demandes: list, nom: str) -> tuple:
    """Applique les remplacements dans l'ordre. Tout ou rien."""
    courant = source
    journal = []
    for rang, demande in enumerate(demandes, start=1):
        ancien = demande["ancien"]
        attendu = demande["occurrences"]
        trouve = courant.count(ancien)
        if trouve == 0:
            raise RuntimeError(
                "remplacement " + str(rang) + " dans « " + nom + " » : le texte "
                "cherché n'existe pas dans ce fichier. RIEN n'a été écrit. "
                "Attention aux espaces d'indentation et aux accents, qui se "
                "recopient mal de mémoire. Cherché : " + _extrait(ancien)
            )
        if attendu and trouve != attendu:
            raise RuntimeError(
                "remplacement " + str(rang) + " dans « " + nom + " » : "
                + str(trouve) + " occurrence(s) trouvée(s) alors que "
                + str(attendu) + " était annoncé. RIEN n'a été écrit. Élargis "
                "le texte cherché avec les lignes voisines jusqu'à ce qu'il "
                "soit unique, ou mets occurrences à 0 pour toutes les "
                "remplacer. Cherché : " + _extrait(ancien)
            )
        lignes = _lignes_des_occurrences(courant, ancien)
        if attendu:
            courant = courant.replace(ancien, demande["nouveau"], attendu)
        else:
            courant = courant.replace(ancien, demande["nouveau"])
        journal.append(
            {
                "n": rang,
                "lignes": lignes,
                "occurrences": attendu or trouve,
                "avant": _extrait(ancien),
                "apres": _extrait(demande["nouveau"]),
            }
        )
    return courant, journal


def _ecrire_et_relire(script_id: str, fichiers: list, modifies: dict) -> dict:
    """Réécrit le projet, les fichiers non visés recopiés tels quels."""
    corps = []
    for fichier in fichiers:
        nom = fichier.get("name")
        corps.append(
            {
                "name": nom,
                "type": fichier.get("type"),
                "source": modifies.get(nom, fichier.get("source", "") or ""),
            }
        )
    _script().projects().updateContent(
        scriptId=script_id, body={"files": corps}
    ).execute()

    relu = _script().projects().getContent(scriptId=script_id).execute()
    fichiers_relus = relu.get("files", [])
    sources_relues = {f.get("name"): (f.get("source", "") or "") for f in fichiers_relus}
    non_conformes = [
        nom for nom, source in modifies.items() if sources_relues.get(nom) != source
    ]
    return {
        "fichiers_apres": len(fichiers_relus),
        "relu_conforme": not non_conformes,
        "non_conformes": non_conformes,
    }


@mcp.tool()
@tolerant
def script_inventaire(script_id: str) -> Any:
    """Liste les fichiers d'un projet Apps Script SANS rendre leur code.

    Pour chaque fichier : son nom, son type, son nombre de lignes et son
    nombre de signes. Plus le total du projet.

    C'EST L'OUTIL À APPELER EN PREMIER sur un projet inconnu.
    get_script_content rend le code de tous les fichiers d'un coup, ce qui
    fait 1,3 Mo sur le projet d'onboarding des collaborateurs et sature le
    contexte pour rien. Ici on voit la forme du projet, puis on va chercher
    ce qu'on veut avec script_chercher et script_lire_lignes.
    """
    fichiers = _script().projects().getContent(scriptId=script_id).execute().get(
        "files", []
    )
    detail = []
    total_lignes = 0
    total_signes = 0
    for fichier in fichiers:
        source = fichier.get("source", "") or ""
        lignes = source.count("\n") + 1 if source else 0
        total_lignes += lignes
        total_signes += len(source)
        detail.append(
            {
                "nom": fichier.get("name"),
                "type": fichier.get("type"),
                "lignes": lignes,
                "signes": len(source),
            }
        )
    return {
        "script_id": script_id,
        "fichiers": detail,
        "nombre_de_fichiers": len(detail),
        "lignes_totales": total_lignes,
        "signes_totaux": total_signes,
        "lien": "https://script.google.com/home/projects/" + str(script_id) + "/edit",
    }


@mcp.tool()
@tolerant
def script_chercher(
    script_id: str,
    motif: str,
    regex: bool = False,
    casse: bool = True,
    fichiers: str = "",
    contexte: int = 0,
    max_resultats: int = MAX_RESULTATS,
) -> Any:
    """Cherche un texte dans tous les fichiers d'un projet Apps Script.

    C'est le grep du projet, fait côté serveur : seules les lignes qui
    répondent reviennent, jamais le projet entier.

    motif : le texte cherché, littéral par défaut.
    regex : si vrai, motif est une expression régulière Python.
    casse : vrai par défaut, la casse compte. Faux pour ignorer la casse.
    fichiers : noms de fichiers séparés par des virgules pour s'y limiter ;
        vide, tout le projet.
    contexte : nombre de lignes à rendre avant et après chaque résultat.
    max_resultats : plafond, pour ne pas noyer une réponse.

    Rend, pour chaque résultat, le fichier, le numéro de ligne et la ligne
    entière. La réponse dit aussi combien de fichiers portent le motif et
    combien de fois, ce qui suffit souvent à décider sans rien lire d'autre.
    """
    if not str(motif or ""):
        raise RuntimeError("le motif cherché est vide")

    cherches = _noms_demandes(fichiers)
    if regex:
        try:
            expression = re.compile(motif, 0 if casse else re.IGNORECASE)
        except Exception as souci:
            raise RuntimeError("expression régulière invalide : " + str(souci))
    else:
        expression = None
        aiguille = motif if casse else motif.lower()

    contenu = _script().projects().getContent(scriptId=script_id).execute()
    resultats = []
    par_fichier = {}
    tronque = False

    for fichier in contenu.get("files", []):
        nom = fichier.get("name")
        if cherches and nom not in cherches:
            continue
        source = fichier.get("source", "") or ""
        lignes = source.split("\n")
        for rang, ligne in enumerate(lignes, start=1):
            if expression is not None:
                touche = expression.search(ligne) is not None
            else:
                touche = aiguille in (ligne if casse else ligne.lower())
            if not touche:
                continue
            par_fichier[nom] = par_fichier.get(nom, 0) + 1
            if len(resultats) >= max(1, int(max_resultats)):
                tronque = True
                continue
            trouvaille = {
                "fichier": nom,
                "ligne": rang,
                "texte": _extrait(ligne, 500),
            }
            if contexte and int(contexte) > 0:
                marge = int(contexte)
                debut = max(1, rang - marge)
                fin = min(len(lignes), rang + marge)
                trouvaille["contexte"] = [
                    {"ligne": n, "texte": _extrait(lignes[n - 1], 500)}
                    for n in range(debut, fin + 1)
                ]
            resultats.append(trouvaille)

    return {
        "script_id": script_id,
        "motif": motif,
        "resultats": resultats,
        "nombre": sum(par_fichier.values()),
        "par_fichier": par_fichier,
        "fichiers_touches": len(par_fichier),
        "tronque": tronque,
    }


@mcp.tool()
@tolerant
def script_lire_lignes(
    script_id: str,
    filename: str,
    debut: int = 1,
    fin: int = 0,
) -> Any:
    """Lit une TRANCHE d'un fichier d'un projet Apps Script, numérotée.

    filename : le nom du fichier, sans extension, tel qu'il apparaît dans
        l'éditeur.
    debut : première ligne rendue, 1 par défaut.
    fin : dernière ligne rendue. 0 pour aller jusqu'au bout du fichier.

    À préférer à get_script_content dès qu'on sait ce qu'on cherche. Le
    texte rendu est celui du fichier, caractère pour caractère : c'est lui
    qu'on recopie dans « ancien » pour script_remplacer, sans le retaper
    de mémoire, ce qui est la première cause d'échec d'un remplacement.
    """
    fichiers = _script().projects().getContent(scriptId=script_id).execute().get(
        "files", []
    )
    cible = _trouver_fichier(fichiers, filename)
    source = cible.get("source", "") or ""
    lignes = source.split("\n")

    premiere = max(1, int(debut or 1))
    derniere = len(lignes) if not fin else min(len(lignes), int(fin))
    if premiere > len(lignes):
        raise RuntimeError(
            "le fichier « " + filename + " » ne compte que " + str(len(lignes))
            + " lignes"
        )
    if derniere < premiere:
        derniere = premiere

    return {
        "script_id": script_id,
        "fichier": filename,
        "type": cible.get("type"),
        "lignes_du_fichier": len(lignes),
        "de": premiere,
        "a": derniere,
        "texte": "\n".join(lignes[premiere - 1 : derniere]),
        "lignes": [
            {"ligne": n, "texte": lignes[n - 1]}
            for n in range(premiere, derniere + 1)
        ],
    }


@mcp.tool()
@tolerant
def script_remplacer(
    script_id: str,
    filename: str,
    remplacements: Any,
    fichiers_attendus: int = 0,
    essai: bool = False,
) -> Any:
    """Remplace des morceaux de texte dans UN fichier d'un projet Apps Script.

    C'est l'outil qui évite de recopier un fichier entier pour changer
    trois lignes. Seuls le texte cherché et le texte neuf circulent ; la
    lecture, le remplacement, l'écriture et la relecture se font ici.

    remplacements : une liste, de la forme
        [{"ancien": "...", "nouveau": "...", "occurrences": 1}]
        Une liste de paires ["ancien", "nouveau"] est acceptée aussi, de
        même qu'une chaîne JSON portant l'une de ces deux formes.
        « occurrences » vaut 1 par défaut, ce qui EXIGE que le texte
        cherché soit unique dans le fichier ; mettre 0 remplace toutes les
        occurrences. Les remplacements s'appliquent DANS L'ORDRE, chacun
        voyant le résultat du précédent.
    fichiers_attendus : nombre de fichiers que le projet doit contenir
        avant l'écriture. 0 pour ne pas contrôler. À renseigner pendant une
        série d'écritures.
    essai : si vrai, rien n'est écrit. La réponse dit ce qui SERAIT changé,
        avec les numéros de ligne. À faire au moindre doute : un essai ne
        coûte rien, une écriture fausse coûte une restauration.

    TOUT OU RIEN. Un texte cherché introuvable, ou trouvé un nombre de fois
    différent de ce qui est annoncé, fait échouer l'appel ENTIER sans rien
    écrire, et le message dit combien d'occurrences ont réellement été
    vues. Un remplacement qui ne changerait rien est refusé également.

    Les autres fichiers du projet sont recopiés octet pour octet, manifeste
    compris : contrairement à write_script_file, le manifeste n'est pas
    refusionné, il est laissé exactement tel qu'il était.

    Après l'écriture, le projet est relu et « relu_conforme » dit si ce qui
    a été relu est exactement ce qui a été écrit.
    """
    demandes = _normaliser_remplacements(remplacements)
    fichiers = _lire_projet_verifie(script_id, fichiers_attendus)
    cible = _trouver_fichier(fichiers, filename)
    avant = cible.get("source", "") or ""
    apres, journal = _appliquer(avant, demandes, filename)

    if apres == avant:
        raise RuntimeError(
            "le remplacement ne change rien dans « " + filename + " » : "
            "écriture refusée. C'est presque toujours le signe qu'on ne "
            "modifie pas le fichier qu'on croit."
        )

    resume = {
        "script_id": script_id,
        "fichier": filename,
        "remplacements": journal,
        "lignes_avant": avant.count("\n") + 1,
        "lignes_apres": apres.count("\n") + 1,
        "signes_avant": len(avant),
        "signes_apres": len(apres),
        "fichiers_du_projet": len(fichiers),
    }

    if essai:
        resume["essai"] = True
        resume["ecrit"] = False
        return resume

    resume.update(_ecrire_et_relire(script_id, fichiers, {filename: apres}))
    resume["ecrit"] = True
    if not resume.get("relu_conforme"):
        resume["alerte"] = (
            "la relecture ne rend pas exactement ce qui a été écrit : vérifier "
            "dans l'éditeur avant d'aller plus loin"
        )
    return resume


@mcp.tool()
@tolerant
def script_remplacer_partout(
    script_id: str,
    ancien: str,
    nouveau: str,
    fichiers: str = "",
    fichiers_attendus: int = 0,
    essai: bool = False,
) -> Any:
    """Remplace un texte dans TOUS les fichiers d'un projet, d'un seul geste.

    Pour les renommages de vocabulaire, qui touchent un mot à vingt endroits
    dans cinq fichiers. Une seule écriture du projet, donc un seul moment où
    quelque chose peut échouer.

    ancien : le texte à remplacer, littéral. Jamais vide.
    nouveau : le texte neuf. Peut être vide pour supprimer.
    fichiers : noms séparés par des virgules pour limiter la portée ; vide,
        tout le projet. Le manifeste « appsscript » n'est jamais touché.
    fichiers_attendus : nombre de fichiers attendu avant l'écriture, 0 pour
        ne pas contrôler.
    essai : si vrai, rien n'est écrit ; la réponse dit ce qui serait changé,
        fichier par fichier, avec les numéros de ligne. À FAIRE D'ABORD sur
        un remplacement large.

    Refuse d'écrire si le texte n'est trouvé nulle part. Rend le détail par
    fichier, puis relit le projet et dit si tout est conforme.

    ATTENTION à la portée : un mot court se retrouve dans des endroits qu'on
    n'avait pas prévus, commentaires et chaînes de caractères compris.
    Passer par essai et lire le détail avant d'écrire.
    """
    if not str(ancien or ""):
        raise RuntimeError("le texte cherché est vide")

    cherches = _noms_demandes(fichiers)
    projet = _lire_projet_verifie(script_id, fichiers_attendus)

    modifies = {}
    detail = []
    for fichier in projet:
        nom = fichier.get("name")
        if nom == "appsscript":
            continue
        if cherches and nom not in cherches:
            continue
        source = fichier.get("source", "") or ""
        compte = source.count(ancien)
        if not compte:
            continue
        modifies[nom] = source.replace(ancien, nouveau)
        detail.append(
            {
                "fichier": nom,
                "occurrences": compte,
                "lignes": _lignes_des_occurrences(source, ancien),
            }
        )

    if not modifies:
        raise RuntimeError(
            "« " + _extrait(ancien, 120) + " » n'a été trouvé dans aucun fichier "
            "de ce projet. Rien n'a été écrit."
        )

    resume = {
        "script_id": script_id,
        "ancien": _extrait(ancien),
        "nouveau": _extrait(nouveau),
        "detail": detail,
        "fichiers_modifies": len(modifies),
        "occurrences_totales": sum(d["occurrences"] for d in detail),
        "fichiers_du_projet": len(projet),
    }

    if essai:
        resume["essai"] = True
        resume["ecrit"] = False
        return resume

    resume.update(_ecrire_et_relire(script_id, projet, modifies))
    resume["ecrit"] = True
    if not resume.get("relu_conforme"):
        resume["alerte"] = (
            "la relecture ne rend pas exactement ce qui a été écrit : vérifier "
            "dans l'éditeur avant d'aller plus loin"
        )
    return resume
