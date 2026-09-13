"""Almaval - schemas « qui fait quoi, ou » poses dans un document Google.

Raison d'etre

Un manuel de reference se lit par les yeux avant de se lire par les
mots : un schema par chapitre, avec des couloirs par acteur et des
fleches numerotees, dit ou l'on va, ce qu'on y fait et qui le fait. Ce
module dessine ces schemas a la charte de la maison (teal #128da0, or
#f7cb4d, gris #666666, jaune de saisie, violet du moteur, saumon de la
decision), les depose sur le Drive et les insere dans le document, en
un seul geste, sans qu'aucune image ne transite par la conversation.

Pourquoi ici et non chez le client

Une image de 30 ko pese des dizaines de milliers de jetons une fois
encodee en base64 dans un appel d'outil. Le serveur, lui, dessine,
televerse et insere pour le prix d'une description en JSON.

Deux genres de schema

  couloirs : un couloir par acteur, une boite par etape dans le couloir
             de celui qui agit, fleches dans l'ordre des etapes.
  couches  : un empilement de boites, une par couche, fleches
             descendantes ; pour dire d'ou vient une donnee et ou elle va.

Police : Manjari, telechargee une fois depuis le depot public des
polices Google et gardee dans le dossier temporaire du serveur ; a
defaut, la police de secours de Pillow.
"""

import io
import json
import os
import re
import urllib.request

from googleapiclient.http import MediaIoBaseUpload

from main import mcp, tolerant, _docs, _drive

TEAL = "#128da0"
DORE = "#f7cb4d"
JAUNE = "#fff2cc"
VIOLET = "#efebf7"
SAUMON = "#ffe6dd"
GRIS = "#666666"
GRIS_CLAIR = "#e6e6e6"
BLANC = "#ffffff"

FONDS = {"saisie": JAUNE, "moteur": VIOLET, "decision": SAUMON, "lecture": BLANC}
LEGENDE = (("Une personne saisit", JAUNE), ("Le moteur écrit", VIOLET),
           ("Une décision se prend", SAUMON), ("On lit seulement", BLANC))

POLICES = {
    "regular": "https://raw.githubusercontent.com/google/fonts/main/ofl/manjari/Manjari-Regular.ttf",
    "bold": "https://raw.githubusercontent.com/google/fonts/main/ofl/manjari/Manjari-Bold.ttf",
    "thin": "https://raw.githubusercontent.com/google/fonts/main/ofl/manjari/Manjari-Thin.ttf",
}
DOSSIER_POLICES = "/tmp/almaval_polices"


# ------------------------------------------------------------- polices

def _chemin_police(nom: str):
    os.makedirs(DOSSIER_POLICES, exist_ok=True)
    chemin = os.path.join(DOSSIER_POLICES, nom + ".ttf")
    if not os.path.exists(chemin) or os.path.getsize(chemin) < 10000:
        try:
            with urllib.request.urlopen(POLICES[nom], timeout=20) as reponse:
                donnees = reponse.read()
            if donnees[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                with open(chemin, "wb") as f:
                    f.write(donnees)
        except Exception:  # noqa: BLE001
            return None
    return chemin if os.path.exists(chemin) else None


def _police(nom: str, taille: int):
    from PIL import ImageFont
    chemin = _chemin_police(nom)
    if chemin:
        try:
            return ImageFont.truetype(chemin, taille)
        except Exception:  # noqa: BLE001
            pass
    try:
        return ImageFont.load_default(size=taille)
    except TypeError:
        return ImageFont.load_default()


def _couper(texte, fonte, largeur, dessin):
    lignes = []
    for paragraphe in str(texte or "").split("\n"):
        ligne = ""
        for mot in paragraphe.split():
            essai = (ligne + " " + mot).strip()
            if dessin.textlength(essai, font=fonte) <= largeur:
                ligne = essai
            else:
                if ligne:
                    lignes.append(ligne)
                ligne = mot
        lignes.append(ligne)
    return lignes


def _pointe(d, p, sens, ech):
    x, y = p
    s = 9 * ech
    if sens == "bas":
        pts = [(x, y), (x - s, y - s), (x + s, y - s)]
    elif sens == "droite":
        pts = [(x, y), (x - s, y - s), (x - s, y + s)]
    else:
        pts = [(x, y), (x + s, y - s), (x + s, y + s)]
    d.polygon(pts, fill=GRIS)


# ------------------------------------------------------------- dessin
#
# Geometrie en unites logiques (ech = 2 pixels par unite au dessin, puis
# reduction a 1400 px). Une largeur logique de 1200 posee a 470 points
# dans la page donne 0,39 point par unite : une fonte de 22 unites se lit
# a 8,6 points, celle de 18 a 7 points. Les boites prennent la hauteur de
# leur texte, le schema s'allonge au lieu de couper.

LARGEUR = 1200
HAUTEUR_MAX_POINTS = 600


def _hauteur_texte(d, e, f_quoi, f_ou, larg_txt, max_quoi=5, max_ou=3):
    lq = _couper(e.get("quoi", ""), f_quoi, larg_txt, d)[:max_quoi]
    lo = _couper(e.get("ou", ""), f_ou, larg_txt, d)[:max_ou] if e.get("ou") else []
    return lq, lo


def _dessiner_couloirs(titre, acteurs, etapes, legende=True):
    from PIL import Image, ImageDraw
    ech = 2
    L = LARGEUR * ech
    marge = 20 * ech
    haut_titre = 62 * ech if titre else 14 * ech
    haut_entete = 44 * ech
    n = max(1, len(acteurs))
    larg_couloir = (L - 2 * marge) // n
    ecart = 22 * ech
    bas_legende = 54 * ech if legende else 0
    f_titre = _police("bold", 26 * ech)
    f_acteur = _police("bold", 21 * ech)
    f_quoi = _police("bold", 21 * ech)
    f_ou = _police("regular", 17 * ech)
    f_num = _police("bold", 17 * ech)
    f_leg = _police("regular", 16 * ech)
    int_quoi, int_ou = 26 * ech, 21 * ech

    sonde = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    boites = []
    for e in etapes:
        try:
            k = acteurs.index(e.get("acteur"))
        except ValueError:
            k = 0
        x0 = marge + k * larg_couloir + 10 * ech
        x1 = marge + (k + 1) * larg_couloir - 16 * ech
        tx = x0 + 42 * ech
        larg_txt = x1 - tx - 10 * ech
        lq, lo = _hauteur_texte(sonde, e, f_quoi, f_ou, larg_txt)
        h = 10 * ech + len(lq) * int_quoi + (len(lo) * int_ou + 4 * ech if lo else 0) + 10 * ech
        h = max(h, 46 * ech)
        boites.append((k, x0, x1, tx, larg_txt, lq, lo, h))

    H = haut_titre + haut_entete + 14 * ech + sum(b[7] + ecart for b in boites) + 14 * ech + bas_legende
    im = Image.new("RGB", (L, H), BLANC)
    d = ImageDraw.Draw(im)
    if titre:
        d.text((marge, 18 * ech), titre, font=f_titre, fill=TEAL)

    y0 = haut_titre
    for k, acteur in enumerate(acteurs):
        x0 = marge + k * larg_couloir
        d.rectangle([x0, y0, x0 + larg_couloir - 6 * ech, y0 + haut_entete], fill=DORE)
        lignes = _couper(acteur, f_acteur, larg_couloir - 24 * ech, d)[:2]
        ty = y0 + (haut_entete - len(lignes) * 24 * ech) / 2
        for l in lignes:
            tw = d.textlength(l, font=f_acteur)
            d.text((x0 + (larg_couloir - 6 * ech - tw) / 2, ty), l, font=f_acteur, fill=TEAL)
            ty += 24 * ech
        d.rectangle([x0, y0 + haut_entete, x0 + larg_couloir - 6 * ech, H - 14 * ech - bas_legende],
                    fill=BLANC, outline=GRIS_CLAIR, width=ech)

    centres = []
    y = y0 + haut_entete + 14 * ech
    for i, (e, (k, x0, x1, tx, larg_txt, lq, lo, h)) in enumerate(zip(etapes, boites)):
        d.rounded_rectangle([x0, y, x1, y + h], radius=8 * ech,
                            fill=FONDS.get(e.get("nature", "lecture"), BLANC), outline=TEAL, width=2 * ech)
        r = 14 * ech
        cx, cy = x0 + 20 * ech, y + 20 * ech
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=TEAL)
        num = str(i + 1)
        tw = d.textlength(num, font=f_num)
        d.text((cx - tw / 2, cy - 12 * ech), num, font=f_num, fill=BLANC)
        ty = y + 9 * ech
        for l in lq:
            d.text((tx, ty), l, font=f_quoi, fill=TEAL)
            ty += int_quoi
        ty += 3 * ech
        for l in lo:
            d.text((tx, ty), l, font=f_ou, fill=GRIS)
            ty += int_ou
        centres.append(((x0 + x1) // 2, y, y + h, x0, x1))
        y += h + ecart

    for i in range(1, len(centres)):
        (cx0, ya0, yb0, xa0, xb0) = centres[i - 1]
        (cx1, ya1, yb1, xa1, xb1) = centres[i]
        if cx0 == cx1:
            p0, p1 = (cx0, yb0), (cx1, ya1)
            d.line([p0, p1], fill=GRIS, width=3 * ech)
            _pointe(d, p1, "bas", ech)
        else:
            if cx1 > cx0:
                p0 = (xb0, (ya0 + yb0) // 2)
                p1 = (xa1, (ya1 + yb1) // 2)
            else:
                p0 = (xa0, (ya0 + yb0) // 2)
                p1 = (xb1, (ya1 + yb1) // 2)
            xm = (p0[0] + p1[0]) // 2 + ((i % 3) - 1) * 7 * ech
            d.line([p0, (xm, p0[1]), (xm, p1[1]), p1], fill=GRIS, width=3 * ech, joint="curve")
            _pointe(d, p1, "droite" if cx1 > cx0 else "gauche", ech)

    if legende:
        y = H - 46 * ech
        x = marge
        for nom, fond in LEGENDE:
            d.rounded_rectangle([x, y, x + 30 * ech, y + 20 * ech], radius=4 * ech, fill=fond, outline=TEAL, width=ech)
            d.text((x + 38 * ech, y - 1 * ech), nom, font=f_leg, fill=GRIS)
            x += 38 * ech + d.textlength(nom, font=f_leg) + 34 * ech
    return im, ech


def _dessiner_couches(titre, couches):
    from PIL import Image, ImageDraw
    ech = 2
    L = LARGEUR * ech
    marge = 20 * ech
    haut_titre = 62 * ech if titre else 14 * ech
    ecart = 30 * ech
    f_titre = _police("bold", 26 * ech)
    f_lib = _police("bold", 23 * ech)
    f_det = _police("regular", 18 * ech)
    x0, x1 = marge + 60 * ech, L - marge - 60 * ech
    sonde = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    boites = []
    for c in couches:
        lq, lo = _hauteur_texte(sonde, c, f_lib, f_det, x1 - x0 - 32 * ech, max_quoi=2, max_ou=3)
        h = 10 * ech + len(lq) * 28 * ech + (len(lo) * 22 * ech + 4 * ech if lo else 0) + 10 * ech
        boites.append((lq, lo, h))
    H = haut_titre + sum(b[2] + ecart for b in boites) - ecart + 20 * ech
    im = Image.new("RGB", (L, H), BLANC)
    d = ImageDraw.Draw(im)
    if titre:
        d.text((marge, 18 * ech), titre, font=f_titre, fill=TEAL)
    y = haut_titre
    for i, (c, (lq, lo, h)) in enumerate(zip(couches, boites)):
        d.rounded_rectangle([x0, y, x1, y + h], radius=8 * ech,
                            fill=FONDS.get(c.get("nature", "lecture"), BLANC), outline=TEAL, width=2 * ech)
        ty = y + 9 * ech
        for l in lq:
            d.text((x0 + 16 * ech, ty), l, font=f_lib, fill=TEAL)
            ty += 28 * ech
        ty += 3 * ech
        for l in lo:
            d.text((x0 + 16 * ech, ty), l, font=f_det, fill=GRIS)
            ty += 22 * ech
        if i < len(couches) - 1:
            cx = (x0 + x1) // 2
            d.line([(cx, y + h), (cx, y + h + ecart)], fill=GRIS, width=3 * ech)
            _pointe(d, (cx, y + h + ecart), "bas", ech)
        y += h + ecart
    return im, ech


def _png(im, ech, largeur=1400):
    from PIL import Image
    hauteur = int(im.height / ech * largeur / (im.width / ech))
    im = im.resize((largeur, hauteur), Image.LANCZOS).convert("RGB")
    im = im.quantize(colors=128, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
    tampon = io.BytesIO()
    im.save(tampon, format="PNG", optimize=True)
    return tampon.getvalue(), largeur, hauteur


# ------------------------------------------------------------- document

def _index_apres(document, apres_texte: str):
    """Index de debut du paragraphe qui suit le premier paragraphe
    commencant par apres_texte ; a defaut, la fin du corps."""
    contenu = document.get("body", {}).get("content", [])
    cible = _normaliser(apres_texte)
    trouve = False
    for element in contenu:
        p = element.get("paragraph")
        if not p:
            continue
        texte = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        if trouve:
            return element["startIndex"]
        if cible and _normaliser(texte).startswith(cible):
            trouve = True
    fin = contenu[-1]["endIndex"] - 1 if contenu else 1
    return fin


def _normaliser(texte):
    return re.sub(r"\s+", " ", str(texte or "")).strip().lower()


def _deposer(donnees: bytes, nom: str, dossier_id: str):
    media = MediaIoBaseUpload(io.BytesIO(donnees), mimetype="image/png", resumable=False)
    corps = {"name": nom, "mimeType": "image/png"}
    if dossier_id:
        corps["parents"] = [dossier_id]
    fichier = _drive().files().create(body=corps, media_body=media, fields="id,webViewLink",
                                      supportsAllDrives=True).execute()
    return fichier


def _ranger(fichier_id: str, dossier_id: str):
    """Deplace le fichier dans le dossier demande, en retirant tous ses parents."""
    actuel = _drive().files().get(fileId=fichier_id, fields="parents", supportsAllDrives=True).execute()
    _drive().files().update(fileId=fichier_id, addParents=dossier_id,
                            removeParents=",".join(actuel.get("parents", [])),
                            supportsAllDrives=True, fields="id,parents").execute()


def _inserer(document_id: str, fichier_id: str, largeur_px: int, hauteur_px: int,
             apres_texte: str, largeur_points: float):
    """Insere l'image dans son propre paragraphe centre, apres le paragraphe
    demande. Le fichier est ouvert en lecture par lien le temps de
    l'insertion, puis referme : le document en garde sa propre copie."""
    permission = _drive().permissions().create(
        fileId=fichier_id, body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True, fields="id").execute()
    try:
        document = _docs().documents().get(documentId=document_id).execute()
        index = _index_apres(document, apres_texte)
        # Un schema plus haut que la page utile est reduit en largeur,
        # jamais coupe : 600 points de haut laissent la place a l'en-tete
        # et au pied de page du gabarit.
        largeur_points = min(largeur_points, HAUTEUR_MAX_POINTS * largeur_px / hauteur_px)
        hauteur_points = largeur_points * hauteur_px / largeur_px
        uri = "https://drive.google.com/uc?export=view&id=" + fichier_id
        requetes = [
            {"insertText": {"location": {"index": index}, "text": "\n"}},
            {"insertInlineImage": {
                "location": {"index": index},
                "uri": uri,
                "objectSize": {
                    "width": {"magnitude": largeur_points, "unit": "PT"},
                    "height": {"magnitude": hauteur_points, "unit": "PT"},
                }}},
            {"updateParagraphStyle": {
                "range": {"startIndex": index, "endIndex": index + 2},
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT", "alignment": "CENTER",
                                   "spaceAbove": {"magnitude": 6, "unit": "PT"},
                                   "spaceBelow": {"magnitude": 10, "unit": "PT"}},
                "fields": "namedStyleType,alignment,spaceAbove,spaceBelow"}},
        ]
        _docs().documents().batchUpdate(documentId=document_id, body={"requests": requetes}).execute()
    finally:
        try:
            _drive().permissions().delete(fileId=fichier_id, permissionId=permission["id"],
                                          supportsAllDrives=True).execute()
        except Exception:  # noqa: BLE001
            pass
    return index


# ------------------------------------------------------------- outils

@mcp.tool()
@tolerant
def schema_poser(document_id: str, nom: str, genre: str = "couloirs", titre: str = "",
                 acteurs: list = None, etapes: list = None, apres_texte: str = "",
                 dossier_id: str = "", largeur_points: float = 470, legende: bool = True,
                 spec_json: str = "", couches: list = None):
    """Dessine un schema a la charte, le depose sur le Drive et l'insere dans un document.

    genre : « couloirs » (un couloir par acteur, etapes numerotees et
    fleches) ou « couches » (empilement de boites, fleches descendantes).
    acteurs : noms des couloirs, dans l'ordre. etapes : liste de
    {acteur, quoi, ou, nature}, nature valant saisie, moteur, decision ou
    lecture. Pour « couches », etapes vaut la liste des couches {quoi, ou,
    nature}, ou se donne par couches. spec_json peut porter tout cela en une chaine JSON
    {titre, acteurs, etapes} quand le client prefere.
    apres_texte : debut du paragraphe apres lequel poser l'image ; vide,
    l'image va en fin de document. dossier_id : dossier Drive du PNG.
    largeur_points : largeur dans la page, 470 points remplit une page A4
    aux marges du gabarit. genre « titres » ne dessine rien et renvoie
    les titres du document avec leurs liens, comme document_titres.
    """
    if genre == "titres":
        return document_titres(document_id)
    if spec_json:
        spec = json.loads(spec_json)
        titre = spec.get("titre", titre)
        acteurs = spec.get("acteurs", acteurs)
        etapes = spec.get("etapes", spec.get("couches", etapes))
    acteurs = list(acteurs or [])
    etapes = list(etapes or couches or [])
    if genre == "couches":
        im, ech = _dessiner_couches(titre, etapes)
    else:
        if not acteurs:
            acteurs = sorted({e.get("acteur", "") for e in etapes})
        im, ech = _dessiner_couloirs(titre, acteurs, etapes, legende=legende)
    donnees, largeur_px, hauteur_px = _png(im, ech)
    # Le PNG est depose d'abord dans le Drive personnel du compte, ou le
    # partage par lien est permis, puis deplace dans le dossier demande
    # une fois insere : un Drive partage qui interdit le partage hors
    # domaine (celui du chantier des BDU, 13.09.2026) refuse la permission
    # temporaire, et Docs ne peut pas lire l'image.
    fichier = _deposer(donnees, nom if nom.lower().endswith(".png") else nom + ".png", "")
    index = _inserer(document_id, fichier["id"], largeur_px, hauteur_px, apres_texte, largeur_points)
    if dossier_id:
        _ranger(fichier["id"], dossier_id)
    return {"image_id": fichier["id"], "image_url": fichier.get("webViewLink"),
            "octets": len(donnees), "pixels": [largeur_px, hauteur_px], "index": index,
            "police": "Manjari" if _chemin_police("bold") else "secours",
            "document": "https://docs.google.com/document/d/" + document_id + "/edit"}


@mcp.tool()
@tolerant
def schema_apercu(nom: str, genre: str = "couloirs", titre: str = "", acteurs: list = None,
                  etapes: list = None, dossier_id: str = "", legende: bool = True, spec_json: str = "",
                  couches: list = None):
    """Dessine le schema et le depose seulement sur le Drive, sans l'inserer
    nulle part : pour regarder avant de poser. Memes parametres que
    schema_poser, sans document."""
    if spec_json:
        spec = json.loads(spec_json)
        titre = spec.get("titre", titre)
        acteurs = spec.get("acteurs", acteurs)
        etapes = spec.get("etapes", spec.get("couches", etapes))
    acteurs = list(acteurs or [])
    etapes = list(etapes or couches or [])
    if genre == "couches":
        im, ech = _dessiner_couches(titre, etapes)
    else:
        if not acteurs:
            acteurs = sorted({e.get("acteur", "") for e in etapes})
        im, ech = _dessiner_couloirs(titre, acteurs, etapes, legende=legende)
    donnees, largeur_px, hauteur_px = _png(im, ech)
    fichier = _deposer(donnees, nom if nom.lower().endswith(".png") else nom + ".png", dossier_id)
    return {"image_id": fichier["id"], "image_url": fichier.get("webViewLink"),
            "octets": len(donnees), "pixels": [largeur_px, hauteur_px],
            "police": "Manjari" if _chemin_police("bold") else "secours"}


@mcp.tool()
@tolerant
def document_titres(document_id: str):
    """Les titres d'un document avec leur ancre : pour envoyer le lien d'un
    chapitre precis. Chaque entree porte le niveau, le texte et l'URL
    docs.google.com/document/d/ID/edit#heading=ID_DU_TITRE."""
    document = _docs().documents().get(documentId=document_id).execute()
    base = "https://docs.google.com/document/d/" + document_id + "/edit#heading="
    titres = []
    for element in document.get("body", {}).get("content", []):
        p = element.get("paragraph")
        if not p:
            continue
        style = p.get("paragraphStyle", {})
        nom_style = style.get("namedStyleType", "")
        if not nom_style.startswith("HEADING_"):
            continue
        texte = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", [])).strip()
        if not texte:
            continue
        ancre = style.get("headingId", "")
        titres.append({"niveau": int(nom_style[-1]), "texte": texte, "ancre": ancre,
                       "url": base + ancre if ancre else ""})
    return {"document_id": document_id, "titres": titres}
