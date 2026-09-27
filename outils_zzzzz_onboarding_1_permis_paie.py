"""Almaval - onboarding porte en Python sous gestion@ : alerte des permis et lignes de paie, 27.09.2026.

Deux moteurs de nuit du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrits a l'identique sur le socle
outils_zzzzz_onboarding_0_socle :

  1. alerteQuotidienneDesPermis (fichier « 20 Alerte permis », 7 h 15).
     Lit « Saisie - Collaborateurs », retient les permis de sejour qui
     arrivent a echeance dans JOURS_AVANT jours ou echus depuis moins de
     RAPPEL_APRES jours, ecarte les Suisses, les permis C et les personnes
     sorties, depose UN recapitulatif dans la file des courriels pour
     rh@almaval.ch et ecrit un mot dans « Message du service » de chaque
     ligne. Memoire des alertes : cles « permis:INITIALES:aaaa-mm-jj »
     dans la memoire du socle (remplacant de PropertiesService).

     AMORCAGE. Au premier passage Python la memoire est vide : tout ce que
     le robot Apps Script a deja signale repartirait. L'option amorcer=True
     considere comme deja signalees les lignes dont « Message du service »
     commence par « Permis » et cite l'echeance (jj.mm.aaaa), ecrit ces
     cles en memoire avec la date du jour, et n'envoie rien. A lancer une
     fois, avec confirmer, avant le premier passage reel.

  2. transmettreLesLignesDePaie (fichier « 18 Paie et validation », 7 h ;
     COL_PAIE declare dans « 45 Colonnes de paie et reprise des
     validations »). Pour chaque ligne de l'onglet Mutations du classeur
     Effectif qui porte un type, touche le salaire ou le taux et n'a pas
     de « Paie transmise le », redige un courriel a salaires@gespower.ch
     et le depose dans la file, puis date la colonne « Paie transmise le ».
     Le moteur ne touche aucun Google Doc : la validation electronique
     (validerElectroniquement, 18b) n'est pas un moteur de nuit et n'est
     pas portee ici.

Chaque moteur expose passage_<moteur>(confirmer=False, ...) qui, sans
confirmer, lit et calcule tout et rend ce qu'il ecrirait (cellules par
onglet) et mettrait en file (ligne complete de la file, corps HTML apres
charte et signature), sans rien ecrire ; avec confirmer il ecrit et rend le
meme compte rendu plus le texte de retour d'origine (resultat).

Outils : onboarding_permis(confirmer, amorcer, jours), onboarding_paie(confirmer).
Pont : lieux_cycle avec le sujet « action:onboarding_permis [confirmer]
[amorcer] [jours=90] » et « action:onboarding_paie [confirmer] ».
"""

import math
import re

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_onboarding_0_socle import (
    CFG, CFG_MUT, COL, COL_MUTATIONS, ID_EFFECTIF, _verrou, cellule_vide_mut, date_de, debut_de_jour, echapper,
    ecrire, est_actif, lire_onglet, lire_onglet_de, maintenant, meme_texte, memoire_ecrire_plusieurs,
    memoire_effacer, memoire_lire, mettre_en_file, nombre_js, nombre_ou_nul, nombre_ou_zero, normaliser,
    serial_de, texte,
)

# ------------------------------------------------ 20 Alerte permis

CFG_PERMIS = {
    "JOURS_AVANT": 90,
    "RAPPEL_APRES": 60,
    "HEURE_PASSAGE": 7,
    "COL_INITIALES": "Initiales",
    "COL_NOM": "Nom",
    "COL_PRENOM": "Prénom",
    "COL_PERMIS": "Permis de séjour",
    "COL_JUSQUA": "Permis valable jusqu'au",
    "COL_NATIONALITE": "Nationalité",
    "COL_MESSAGE": "Message du service",
    "COL_SORTIE": "Date sortie",
    "MARQUE": "permis:",
}

# 45 Colonnes de paie (les trois intitules de la ligne 1 de Mutations)
COL_PAIE = {"TRANSMIS_LE": "Paie transmise le", "VALIDE_LE": "Validé électroniquement le", "VALIDE_PAR": "Validé par"}

# 18 Paie et validation
CFG_PAIE = {"EMAIL_PAIE": "salaires@gespower.ch", "NOM_PAIE": "Lilia", "OBJET_PAIE": "Mutation salariale Almaval",
            "DELAI_JOURS_PAIE": 0}


def _s(v):
    """String(v || '') d'Apps Script : vide pour None, false et 0 ; 4 pour 4.0 ;
    jj.mm.aaaa pour une Date."""
    if v is None or v == "" or v is False:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return ""
    return texte(v)


def _jour_permis(d):
    return d.strftime("%d.%m.%Y")


def _cle_permis(c):
    return CFG_PERMIS["MARQUE"] + c["initiales"] + ":" + c["echeance"].strftime("%Y-%m-%d")


def _mot_du_service(c):
    """Le mot ecrit dans « Message du service » de la ligne concernee."""
    if c["restants"] >= 0:
        return ("Permis " + c["permis"] + " à renouveler, échéance le " + _jour_permis(c["echeance"])
                + ", dans " + str(c["restants"]) + " jours.")
    return "Permis " + c["permis"] + " ÉCHU depuis le " + _jour_permis(c["echeance"]) + "."


def objet_de_l_alerte_permis(liste):
    echus = sum(1 for c in liste if c["restants"] < 0)
    if echus and echus == len(liste):
        return str(echus) + " permis de séjour échus" if echus > 1 else "Permis de séjour échu"
    if echus:
        return "Permis de séjour : " + str(echus) + " échu(s) et " + str(len(liste) - echus) + " à renouveler"
    return (str(len(liste)) + " permis de séjour arrivent à échéance") if len(liste) > 1 \
        else "Un permis de séjour arrive à échéance"


def corps_de_l_alerte_permis(liste, jours, gid):
    lignes = ""
    for c in liste:
        if c["restants"] < 0:
            etat = '<span style="color:#cc0000;font-weight:bold;">Échu depuis ' + str(abs(c["restants"])) + " jours</span>"
        elif c["restants"] <= 30:
            etat = '<span style="color:#cc0000;">Dans ' + str(c["restants"]) + " jours</span>"
        else:
            etat = "Dans " + str(c["restants"]) + " jours"
        lignes += ("<tr>"
                   '<td style="padding:4px 10px;border-bottom:1px solid #e0e0e0;">' + echapper(c["nom"] + " " + c["prenom"]) + "</td>"
                   '<td style="padding:4px 10px;border-bottom:1px solid #e0e0e0;">' + echapper(c["permis"]) + "</td>"
                   '<td style="padding:4px 10px;border-bottom:1px solid #e0e0e0;">' + echapper(c["nationalite"]) + "</td>"
                   '<td style="padding:4px 10px;border-bottom:1px solid #e0e0e0;white-space:nowrap;">' + _jour_permis(c["echeance"]) + "</td>"
                   '<td style="padding:4px 10px;border-bottom:1px solid #e0e0e0;white-space:nowrap;">' + etat + "</td>"
                   "</tr>")
    lien = "https://docs.google.com/spreadsheets/d/" + CFG["CLASSEUR_RH"] + "/edit#gid=" + str(gid)
    return ("<p>Bonjour,</p>"
            "<p>Voici les permis de séjour qui arrivent à échéance dans les " + str(jours) + " jours, "
            "ou qui viennent d'échoir. Chaque personne n'est signalée qu'une fois par échéance.</p>"
            "<p><b>Les personnes concernées</b></p>"
            '<table style="border-collapse:collapse;font-size:14px;">'
            '<tr style="background:#f7cb4d;color:#128da0;font-weight:bold;">'
            '<td style="padding:6px 10px;">Collaborateur</td>'
            '<td style="padding:6px 10px;">Permis</td>'
            '<td style="padding:6px 10px;">Nationalité</td>'
            '<td style="padding:6px 10px;">Valable jusqu\'au</td>'
            '<td style="padding:6px 10px;">Échéance</td></tr>'
            + lignes +
            "</table>"
            "<p><b>Ce qu'il y a à faire</b></p>"
            "<ul>"
            "<li>Prévenir la personne et lui rappeler les pièces à rassembler pour le renouvellement.</li>"
            "<li>Mettre à jour la colonne « " + CFG_PERMIS["COL_JUSQUA"] + " » dès que le nouveau permis est reçu, "
            "et déposer la copie dans le registre des pièces.</li>"
            "<li>Signaler à la comptabilité si l'imposition à la source change.</li>"
            "</ul>"
            "<p>La fiche du collaborateur se trouve ici : "
            '<a href="' + lien + '">Almaval - Collaborateurs - Gestion, Saisie - Collaborateurs</a>. '
            "Un mot a été écrit dans la colonne « " + CFG_PERMIS["COL_MESSAGE"] + " » de chaque ligne concernée.</p>")


def _permis_concernes(saisie, jours):
    """Les lignes de la fiche dans la fenetre, triees par jours restants, comme alerterLesPermis."""
    aujourdhui = debut_de_jour(maintenant())
    concernes = []
    for ligne in saisie.lignes:
        echeance = date_de(ligne.get(CFG_PERMIS["COL_JUSQUA"]))
        if not echeance:
            continue
        nationalite = _s(ligne.get(CFG_PERMIS["COL_NATIONALITE"])).strip()
        permis = _s(ligne.get(CFG_PERMIS["COL_PERMIS"])).strip()
        if meme_texte(nationalite, "Suisse"):
            continue
        if meme_texte(permis, "Ressortissant suisse"):
            continue
        if meme_texte(permis, "C"):
            continue
        sortie = date_de(ligne.get(CFG_PERMIS["COL_SORTIE"]))
        if sortie and sortie < aujourdhui:
            continue
        restants = int(round((debut_de_jour(echeance) - aujourdhui).total_seconds() / 86400.0))
        if restants > jours:
            continue
        if restants < -CFG_PERMIS["RAPPEL_APRES"]:
            continue
        concernes.append({
            "initiales": _s(ligne.get(CFG_PERMIS["COL_INITIALES"])).strip(),
            "nom": _s(ligne.get(CFG_PERMIS["COL_NOM"])).strip(),
            "prenom": _s(ligne.get(CFG_PERMIS["COL_PRENOM"])).strip(),
            "permis": permis or "non renseigné",
            "nationalite": nationalite or "non renseignée",
            "echeance": echeance,
            "restants": restants,
            "numeroLigne": ligne["_ligne"],
            "message": _s(ligne.get(CFG_PERMIS["COL_MESSAGE"])),
        })
    concernes.sort(key=lambda c: c["restants"])
    return concernes


def _deja_signale_dans_la_fiche(c):
    """Pour l'amorcage : le mot du service commence par « Permis » et cite l'echeance."""
    m = c["message"].strip()
    return m.startswith("Permis") and _jour_permis(c["echeance"]) in m


def passage_permis(confirmer=False, amorcer=False, jours=None):
    """alerterLesPermis({ jours }) puis le declencheur alerteQuotidienneDesPermis.

    Sans confirmer : lit, calcule et rend ce qui serait ecrit (fiche, memoire)
    et mis en file. Avec confirmer : ecrit et rend le meme compte rendu plus
    « resultat », le texte de retour d'origine. Avec amorcer : n'envoie rien,
    inscrit en memoire les lignes deja signalees par l'ancien robot (mot du
    service commencant par « Permis » et citant l'echeance)."""
    j = nombre_ou_nul(jours)
    jours = int(j) if j and j > 0 else CFG_PERMIS["JOURS_AVANT"]
    saisie = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
    rendu = {"moteur": "permis", "confirme": bool(confirmer), "amorcage": bool(amorcer), "jours": jours,
             "ecritures": {}, "file": [], "memoire": {}}
    if not saisie.existe(CFG_PERMIS["COL_JUSQUA"]):
        rendu["resultat"] = ("La colonne « " + CFG_PERMIS["COL_JUSQUA"] + " » manque dans « " + CFG["ONGLET_SAISIE"] + " ».")
        return rendu

    concernes = _permis_concernes(saisie, jours)
    rendu["dans_la_fenetre"] = [{"ligne": c["numeroLigne"], "initiales": c["initiales"], "echeance": _jour_permis(c["echeance"]),
                                 "restants": c["restants"], "cle": _cle_permis(c), "deja_en_memoire": bool(memoire_lire(_cle_permis(c)))}
                                for c in concernes]

    if amorcer:
        jour = maintenant().strftime("%Y-%m-%d")
        a_inscrire = {_cle_permis(c): jour for c in concernes
                      if not memoire_lire(_cle_permis(c)) and _deja_signale_dans_la_fiche(c)}
        rendu["memoire"] = a_inscrire
        if confirmer and a_inscrire:
            memoire_ecrire_plusieurs(a_inscrire)
        rendu["resultat"] = ("Amorçage" + ("" if confirmer else " (simulation)") + " : " + str(len(a_inscrire))
                             + " alerte(s) déjà signalée(s) par la fiche inscrite(s) en mémoire, sur "
                             + str(len(concernes)) + " permis dans la fenêtre des " + str(jours) + " jours. Rien envoyé.")
        return rendu

    nouveaux = [c for c in concernes if not memoire_lire(_cle_permis(c))]
    if not nouveaux:
        rendu["resultat"] = ("Aucune alerte nouvelle. " + str(len(concernes)) + " permis dans la fenêtre des " + str(jours)
                             + " jours, déjà signalés.") if concernes else ("Aucun permis à échéance dans les " + str(jours) + " jours.")
        return rendu

    message = {
        "type": "Alerte permis",
        "initiales": "",
        "nomPrenom": "",
        "destinataire": CFG["EMAIL_RH"],
        "objet": objet_de_l_alerte_permis(nouveaux),
        "corps": corps_de_l_alerte_permis(nouveaux, jours, saisie.sheet_id),
        "mode": CFG["MODE_COURRIEL"],
        "statut": "En attente",
        "detail": str(len(nouveaux)) + " permis signalés",
    }
    rendu["file"].append(mettre_en_file(message, a_sec=True))
    jour = maintenant().strftime("%Y-%m-%d")
    rendu["memoire"] = {_cle_permis(c): jour for c in nouveaux}
    cellules = []
    if saisie.existe(CFG_PERMIS["COL_MESSAGE"]):
        cellules = [{"ligne": c["numeroLigne"], "colonne": CFG_PERMIS["COL_MESSAGE"], "valeur": _mot_du_service(c)} for c in nouveaux]
    rendu["ecritures"][CFG["ONGLET_SAISIE"]] = cellules

    if not confirmer:
        rendu["resultat_prevu"] = str(len(nouveaux)) + " permis signalés aux ressources humaines, message (non déposé) dans la file."
        return rendu

    with _verrou:
        numero = mettre_en_file(message)
        # La trace dans la fiche, la ou les ressources humaines travaillent.
        memoire_ecrire_plusieurs(rendu["memoire"])
        for cel in cellules:
            try:
                ecrire(saisie, cel["ligne"], cel["colonne"], cel["valeur"])
            except Exception:  # noqa: BLE001
                pass
    rendu["resultat"] = str(len(nouveaux)) + " permis signalés aux ressources humaines, message " + str(numero) + " déposé dans la file."
    return rendu


def oublier_les_alertes_de_permis():
    """oublierLesAlertesDePermis : vide la memoire des alertes. Entretien."""
    return str(memoire_effacer(CFG_PERMIS["MARQUE"])) + " alerte(s) de permis oubliée(s)."


# ------------------------------------------------ 13 Mutations, l'affichage humain

def _js_round(n):
    """Math.round de JavaScript : le demi vers le haut."""
    return math.floor(n + 0.5)


def nombre_fr(n, decimales=2):
    """nombreFr_ : arrondi, separateur des milliers ’, virgule decimale."""
    facteur = 10 ** decimales
    arrondi = _js_round(n * facteur) / facteur
    parties = nombre_js(abs(float(arrondi))).split(".")
    entier = re.sub(r"\B(?=(\d{3})+(?!\d))", "’", parties[0])
    return ("-" if arrondi < 0 else "") + entier + ("," + parties[1] if len(parties) > 1 and parties[1] else "")


def _fraction_de(n):
    return n / 100 if (n is not None and abs(n) > 1.5) else n


def _nombre_selon_format(v, f):
    n = nombre_ou_nul(v)
    return _fraction_de(n) if normaliser(f) == "pourcentage" else n


def valeur_affichee(v, format_):
    """valeurAffichee_ de « 13 Mutations » : montant, pourcentage, date, nombre, texte."""
    f = normaliser(format_)
    if f == "coche":
        return "oui" if est_actif(v) else "non"
    if cellule_vide_mut(v):
        return ""
    if f == "pourcentage":
        return nombre_fr((_nombre_selon_format(v, f) or 0) * 100) + " %"
    if f == "montant":
        return nombre_fr(nombre_ou_zero(v)) + " CHF"
    if f == "heures":
        return nombre_fr(nombre_ou_zero(v)) + " heures"
    if f == "semaines":
        s = nombre_ou_zero(v)
        return nombre_fr(s) + (" semaines" if s > 1 else " semaine")
    if f == "nombre":
        return nombre_fr(nombre_ou_zero(v))
    if f == "date":
        d = date_de(v)
        return d.strftime("%d/%m/%Y") if d else _s(v)
    return _s(v)


def cle_de_la_saisie(ligne):
    """cleDeLaSaisie_ : Initiales-N° d'engagement, 1 a defaut."""
    initiales = _s(ligne.get(COL["INITIALES"])).strip()
    if not initiales:
        return ""
    v = ligne.get(COL["NUMERO_ENGAGEMENT"])
    numero = ("" if v is None else texte(v)).strip()  # String(v), un 0 reste « 0 »
    return initiales + "-" + (numero or "1")


# ------------------------------------------------ 18 Paie

def est_une_mutation_de_paie(m):
    """Une mutation touche la paie si elle modifie le salaire ou le taux."""
    return (not cellule_vide_mut(m.get(COL_MUTATIONS["NOUVEAU_SALAIRE"]))
            or not cellule_vide_mut(m.get(COL_MUTATIONS["NOUVEAU_TAUX"])))


def resumer_pour_la_paie(m, engagement):
    """resumerPourLaPaie_ : la phrase pour la fiduciaire, a l'identique.

    La cle « Mois de salaire par an » est lue sur la ligne de la fiche, ou
    l'en-tete reel est « Mois de salaire (nb/an) » : comme dans l'original,
    les mensualites n'apparaissent donc jamais. Defaut conserve pour rendre
    le meme texte ; voir le rapport."""
    nom_prenom = (_s(engagement.get(COL["NOM"])) + " " + _s(engagement.get(COL["PRENOM"]))).strip() \
        or _s(m.get(COL_MUTATIONS["CLE"]))
    morceaux = [nom_prenom + ", à effet au " + valeur_affichee(m.get(COL_MUTATIONS["DATE"]), "Date")]
    if not cellule_vide_mut(m.get(COL_MUTATIONS["NOUVEAU_SALAIRE"])):
        ancien = "" if cellule_vide_mut(m.get(COL_MUTATIONS["ANCIEN_SALAIRE"])) \
            else valeur_affichee(m.get(COL_MUTATIONS["ANCIEN_SALAIRE"]), "Montant") + " puis "
        morceaux.append("salaire mensuel brut " + ancien + valeur_affichee(m.get(COL_MUTATIONS["NOUVEAU_SALAIRE"]), "Montant"))
    if not cellule_vide_mut(m.get(COL_MUTATIONS["NOUVEAU_TAUX"])):
        avant = "" if cellule_vide_mut(m.get(COL_MUTATIONS["ANCIEN_TAUX"])) \
            else valeur_affichee(m.get(COL_MUTATIONS["ANCIEN_TAUX"]), "Pourcentage") + " puis "
        morceaux.append("taux d'activité " + avant + valeur_affichee(m.get(COL_MUTATIONS["NOUVEAU_TAUX"]), "Pourcentage"))
    if not cellule_vide_mut(engagement.get("Mois de salaire par an")):
        morceaux.append(nombre_js(nombre_ou_zero(engagement.get("Mois de salaire par an"))) + " mensualités")
    if not cellule_vide_mut(m.get(COL_MUTATIONS["MOTIF"])):
        morceaux.append(_s(m.get(COL_MUTATIONS["MOTIF"])))
    return ", ".join(morceaux) + "."


def corps_de_la_ligne_de_paie(t):
    return ("<p>Bonjour " + CFG["NOM_PAIE"] + ",</p>"
            "<p>Une mutation à répercuter sur la paie :</p>"
            "<p><b>" + t + "</b></p>"
            "<p>Le contrat ou l'avenant correspondant est à disposition sur demande.</p>")


def passage_paie(confirmer=False):
    """transmettreLesLignesDePaie : les mutations de paie non transmises,
    un courriel chacune dans la file, puis la date dans « Paie transmise le »."""
    mutations = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"], rafraichir=True)
    saisie = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
    rendu = {"moteur": "paie", "confirme": bool(confirmer), "ecritures": {}, "file": []}

    a_transmettre = [m for m in mutations.lignes
                     if m.get(COL_MUTATIONS["TYPE"]) and est_une_mutation_de_paie(m)
                     and cellule_vide_mut(m.get(COL_PAIE["TRANSMIS_LE"]))]
    if not a_transmettre:
        rendu["resultat"] = "Aucune ligne de paie en attente."
        return rendu

    now = maintenant()
    horodatage = serial_de(now)
    messages, cellules = [], []
    for m in a_transmettre:
        cle = _s(m.get(COL_MUTATIONS["CLE"])).strip()
        engagement = next((s for s in saisie.lignes if cle_de_la_saisie(s) == cle), {})
        message = {
            "type": "Paie",
            "initiales": cle.split("-")[0] if cle else "",
            "nomPrenom": _s(engagement.get(COL["NOM"])) + " " + _s(engagement.get(COL["PRENOM"])),
            "destinataire": CFG_PAIE["EMAIL_PAIE"],
            "objet": CFG_PAIE["OBJET_PAIE"] + " - " + cle + " - " + _s(engagement.get(COL["NOM"])),
            "corps": corps_de_la_ligne_de_paie(resumer_pour_la_paie(m, engagement)),
            "mode": CFG["MODE_COURRIEL"],
            "statut": "En attente",
            "detail": "Ligne de mutation " + str(m["_ligne"]),
        }
        messages.append(message)
        rendu["file"].append(mettre_en_file(message, a_sec=True))
        cellules.append({"ligne": m["_ligne"], "colonne": COL_PAIE["TRANSMIS_LE"], "valeur": horodatage,
                         "affichee": now.strftime("%d.%m.%Y %H:%M")})
    rendu["ecritures"][CFG_MUT["ONGLET_MUTATIONS"]] = cellules

    texte_retour = str(len(a_transmettre)) + " ligne(s) de paie déposée(s) dans la file d'attente."
    if not confirmer:
        rendu["resultat_prevu"] = texte_retour
        return rendu
    with _verrou:
        for message, cel in zip(messages, cellules):
            mettre_en_file(message)
            ecrire(mutations, cel["ligne"], cel["colonne"], cel["valeur"])
    rendu["resultat"] = texte_retour
    return rendu


# ------------------------------------------------ outils et pont

@mcp.tool()
@tolerant
def onboarding_permis(confirmer: bool = False, amorcer: bool = False, jours: int = 90):
    """Alerte des permis de sejour (onboarding, 7 h 15) sous gestion@ ; simulation sans confirmer, amorcer pour reprendre la memoire."""
    return passage_permis(confirmer=confirmer, amorcer=amorcer, jours=jours)


@mcp.tool()
@tolerant
def onboarding_paie(confirmer: bool = False):
    """Lignes de paie des mutations vers GesPower (onboarding, 7 h) sous gestion@ ; simulation sans confirmer."""
    return passage_paie(confirmer=confirmer)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_permis":
            return tolerant(passage_permis)(confirmer=("confirmer" in drapeaux), amorcer=("amorcer" in drapeaux),
                                            jours=options.get("jours", "90"))
        if premier == "onboarding_paie":
            return tolerant(passage_paie)(confirmer=("confirmer" in drapeaux))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding permis paie] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
