"""Almaval - preuve du portage du distributeur : comparer sans ecrire.

Compare, abonnement par abonnement, ce que le distributeur Python ecrirait
a ce qui est en place dans l'onglet distribue, c'est a dire ce que le
distributeur Apps Script a laisse a son dernier passage. Un ecart est soit
une modification de la source depuis ce passage, soit un ecart de portage.
Pont : lieux_cycle avec le sujet « action:distributeur_comparer », drapeau
« tous » pour toutes les frequences, options lignes=2,3 et exemples=5.
"""

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import (
    _CACHE_CLASSEURS, _CACHE_GRILLES, _classeur, _est_vide, _lire_abonnements, _lire_grille, _onglet,
    _rogner_fin, _valider, construire_sortie, norm, normv, serialiser,
)


def _lignes_prevues(ab, sortie):
    """Les lignes que la disposition ecrirait, sans rien ecrire (meme calcul
    que _ecrire_sans_protection), et les lignes en place a comparer."""
    classeur = _classeur(ab["lien_dest"], rafraichir=True)
    prop = _onglet(classeur, ab["onglet_cible"])
    grille = _lire_grille(classeur["id"], prop["title"]) if prop else []
    cols = [norm(c["source"]) for c in sortie["colonnes"]]
    lignes = sortie["lignes"]
    if ab["disposition"] == "colonne":
        k, vus, valeurs = cols[0], set(), []
        for l in lignes:
            v = l.get(k, "")
            if _est_vide(v) or normv(v) in vus:
                continue
            vus.add(normv(v))
            valeurs.append([v])
        col = 0
        for i, h in enumerate(grille[0] if grille else []):
            if norm(h) == norm(ab["intitule"]):
                col = i + 1
                break
        en_place = _rogner_fin([[l[col - 1] if col - 1 < len(l) else ""] for l in grille[1:]]) if col else []
        return valeurs, en_place
    if ab["disposition"] == "long":
        decalage = 0 if ab["intitule"] else 1
        l5 = []
        for i, l in enumerate(lignes):
            nom = ab["intitule"] if ab["intitule"] else l.get(cols[0], "")
            valeur = l.get(cols[0 + decalage], "")
            if _est_vide(valeur) or _est_vide(nom):
                continue
            attribut = l.get(cols[1 + decalage], "") if len(cols) > 1 + decalage else ""
            ordre = l.get(cols[2 + decalage], "") if len(cols) > 2 + decalage else i + 1
            col_actif = cols[3 + decalage] if len(cols) > 3 + decalage else None
            actif = ("" if l.get(col_actif) is None else l.get(col_actif)) if col_actif else "x"
            l5.append([nom, valeur, "" if attribut is None else attribut, i + 1 if _est_vide(ordre) else ordre, actif])
        noms = {normv(r[0]) for r in l5}
        corps = _rogner_fin([(l + [""] * 5)[:5] for l in grille[1:]])
        en_place = [r for r in corps if normv(r[0]) in noms]
        return l5, en_place
    entetes = [c["alias"] for c in sortie["colonnes"]]
    tab = [entetes] + [[("" if l.get(k) is None else l.get(k, "")) for k in cols] for l in lignes]
    largeur = len(entetes)
    en_place = [(list(r[:largeur]) + [""] * (largeur - len(r[:largeur]))) for r in _rogner_fin(grille)]
    return tab, en_place


def comparer_tout(planifie=True, lignes=None, exemples=3):
    """Compare, sans rien ecrire, ce que le passage ecrirait a ce qui est en
    place dans chaque onglet distribue. Sert a prouver un portage."""
    _CACHE_CLASSEURS.clear()
    _CACHE_GRILLES.clear()
    lecture = _lire_abonnements()
    selection = [a for a in lecture["abonnements"] if a["actif"] and (not planifie or a["frequence"] == "quotidienne")]
    if lignes:
        selection = [a for a in selection if a["ligne"] in [int(x) for x in lignes]]
    sortie = []
    for ab in selection:
        try:
            _valider(ab)
            prevu, en_place = _lignes_prevues(ab, construire_sortie(ab))
            sp, se = [serialiser([r]) for r in prevu], [serialiser([r]) for r in en_place]
            identique = sp == se
            detail = {"ligne": ab["ligne"], "destinataire": ab["destinataire"], "onglet": ab["onglet_cible"],
                      "intitule": ab["intitule"], "disposition": ab["disposition"], "identique": identique,
                      "lignes_prevues": len(prevu), "lignes_en_place": len(en_place)}
            if not identique:
                ens_p, ens_e = set(sp), set(se)
                detail["seulement_prevues"] = len(ens_p - ens_e)
                detail["seulement_en_place"] = len(ens_e - ens_p)
                detail["meme_contenu_ordre_different"] = (ens_p == ens_e)
                detail["exemples_prevues"] = [r for r, s in zip(prevu, sp) if s not in ens_e][:exemples]
                detail["exemples_en_place"] = [r for r, s in zip(en_place, se) if s not in ens_p][:exemples]
                if ens_p == ens_e:
                    premier = next((i for i, (a, b) in enumerate(zip(sp, se)) if a != b), None)
                    detail["premiere_ligne_deplacee"] = premier
                    if premier is not None:
                        detail["exemples_prevues"] = prevu[premier:premier + exemples]
                        detail["exemples_en_place"] = en_place[premier:premier + exemples]
        except Exception as exc:  # noqa: BLE001
            detail = {"ligne": ab["ligne"], "destinataire": ab["destinataire"], "onglet": ab["onglet_cible"],
                      "erreur": str(exc)[:300]}
        sortie.append(detail)
    return {"compares": len(sortie), "identiques": sum(1 for d in sortie if d.get("identique")),
            "differents": [d for d in sortie if not d.get("identique")]}



@mcp.tool()
@tolerant
def distributeur_comparer(planifie: bool = True, lignes: str = "", exemples: int = 3):
    """Compare sans ecrire ce que le distributeur ecrirait a ce qui est en place."""
    return comparer_tout(planifie=planifie, lignes=[x for x in str(lignes or "").replace(";", ",").split(",") if x.strip()],
                         exemples=exemples)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "distributeur_comparer":
            return tolerant(comparer_tout)(planifie=("tous" not in drapeaux),
                                           lignes=[x for x in options.get("lignes", "").split(",") if x],
                                           exemples=int(options.get("exemples", "3")))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[distributeur comparer] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
