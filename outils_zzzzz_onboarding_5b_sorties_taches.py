"""Almaval - onboarding porte en Python sous gestion@ : les taches de sortie automatisees, 28.09.2026.

Complement du module outils_zzzzz_onboarding_5_sorties, greffe en enveloppe
de sa fonction appliquer_les_conditions (appelee par le passage de nuit pour
chaque sortie ouverte, avec le contexte, la ligne, la cle, les initiales et
l'engagement) : a chaque passage (4 h 15), pour chaque sortie ouverte, chaque tache du referentiel « Sortie - Actions » qui porte
ici un moteur est executee si son moment est venu, et son etat est pose
dans « Sortie - Suivi » (En cours avec le produit et son lien, ou Fait quand
le fait est constate a la source). Decision d'Alberto du 28.09.2026 :
« costruisci tutto ». Rien n'est envoye a l'exterieur par le robot : ce qui
part vers un organisme est un BROUILLON depose dans « Courriels - File
d'attente », que le robot des courriels pose dans rh@ (CFG.MODE_COURRIEL =
Brouillon) ; l'envoi reste humain. Les documents sont des PROJETS Google
Docs dans le sous-dossier « 7. Fin des relations » du dossier RH (1a).

Moments (colonne « Jours par rapport a la sortie » du referentiel) :
  preparation : des l'ouverture ;
  j-45        : quarante-cinq jours avant la date de sortie ;
  echeance    : a partir de la date d'echeance de la tache ;
  apres       : strictement apres la date de sortie (gestes de fermeture).

Famille 2 et 7, calculs et salaire
  80  Solde de vacances : dernier mois pose dans BDU « Mois - Temps »
      (colonne « Solde de vacances »), ecrit dans « Solde de vacances a la
      sortie (jours) » de la fiche s'il est vide ; Fait avec la valeur.
  90  Heures a solder : « Heures supplementaires », « Rattrapage, solde
      (h) », « Ecart de pointage, cumul de l'annee (h) » du meme mois,
      ecrit dans « Heures a solder » ; En cours, l'arbitrage reste humain.
  120 Dernier salaire et prorata du treizieme : Registre - Engagements
      (salaire mensuel effectif, mois de salaire par an) ; Fait, calcul
      dans la remarque et repris par le brouillon 510.
  510 Dernier decompte : brouillon a la paie (salaires@gespower.ch) avec
      numero de paie, dates, dernier salaire, treizieme, solde de vacances
      et son montant, heures a solder, liberation ; En cours.
  520 Versement du solde de vacances : montant = salaire mensuel / 21.75 x
      jours, dans le brouillon 510 ; En cours.
  580 Annonce des salaires et masse salariale : Fait des que la date de
      sortie est au registre (la masse salariale se reconstruit depuis le
      registre) et que le brouillon 510 existe.

Famille 5, annonces externes, brouillons prerempli, destinataire lu dans la
colonne « Destinataire de l'annonce » de Sortie - Actions
  300 LPP Medpension, 310 AVS Medisuisse, 320 Caisse des medecins (Hotline
      et Salaires, fermeture du compte un mois apres), 380 AXA (LAA et perte
      de gain) : un brouillon chacun, j-45 ; En cours.
  350 et 360 DSAS : l'annonce trimestrielle (module a) porte les sorties ;
      Fait quand la personne figure dans l'onglet du trimestre de sa sortie
      du classeur DSAS, sinon remarque avec le trimestre attendu.

Famille 3, continuite clinique, depuis « Sortie - Continuite clinique »
  170 Attribution : Fait quand chaque patient « Repris » porte un « Repris
      par » ; sinon remarque avec le compte et la liste des patients a
      attribuer, En cours.
  180 Information des patients : PROJET « Lettres aux patients » (une lettre
      par patient repris, avec le nouveau therapeute et la date) dans le
      sous-dossier 7 ; Fait quand chaque patient repris porte « Patient
      informe le ».
  190 Prescriptions : les patients dont la prestation en cours est une
      psychotherapie prescrite, listes dans la remarque ; En cours ; Sans
      objet s'il n'y en a aucun.
  200 Medecins traitants : PROJET « Lettres aux medecins » depuis l'Index
      patients (medecin traitant du patient), un paragraphe par medecin ;
      En cours.

Famille 4, documents
  260 Attestation de l'employeur (chomage) : PROJET « Donnees pour
      l'attestation de l'employeur 10006 » dans le sous-dossier 7, quand le
      collaborateur l'a demandee ; En cours.
  280 Attestation LPP : a l'echeance (+30), Fait si une piece portant
      « LPP » datee d'apres la sortie est dans le sous-dossier 7, sinon
      remarque et brouillon de relance a Medpension.

Famille 6, acces et materiel
  430 Workspace : a la date, remarque avec la console ; Fait des que
      l'annuaire dit l'utilisateur suspendu (lecture seule, la suspension
      reste un geste humain tant que l'API n'a pas la portee d'ecriture).
  460 Agenda et bureau : a la date, Fait si aucune attribution active de
      « Almaval - Lieux - BDU » ne depasse la date de sortie, sinon la liste.
  470 Baserow et Almadesk : Fait quand le miroir BigQuery
      almaval_baserow.collaborateurs dit statut Ancien ; sinon remarque.
  480 Google Voice : a l'echeance (+7), remarque avec la console ; Fait
      quand l'annuaire ne porte plus de numero Voice pour le compte, ou le
      compte est suspendu.
  490 Site internet : Fait quand le miroir Baserow dit « cacher sur site
      internet » ou statut Ancien ; sinon remarque avec l'adresse de la
      page.

Idempotence : un brouillon n'est depose qu'une fois (type « Sortie <ordre> »
et cle d'engagement dans la file), un PROJET n'est cree qu'une fois (nom
exact dans le sous-dossier 7), un etat n'est jamais abaisse. Ligne d'essai
(Nom = Essai) : les brouillons vont a rh@ elle-meme, objet prefixe ESSAI,
aucun document n'est cree.
"""

import datetime
import re

import main
import outils_zzzzz_onboarding_5_sorties as sorties
from outils_zzzzz_distributeur import _classeur, _lire_grille, _onglet, _oublier
from outils_zzzzz_onboarding_0_socle import (
    CFG, CFG_MUT, COL, COL_SORTIE, COL_COURRIEL, ID_BDU, ID_EFFECTIF,
    creer_dossier, date_de, en_jour, enfants_de, lire_onglet, lire_onglet_de, maintenant, meme_texte,
    mettre_en_file, normaliser, onglet_courriels, texte,
)

_s = sorties._s
_est_date = sorties._est_date
_nombre_js = sorties._nombre_js
marquer_taches = sorties.marquer_taches
etat_de_tache = sorties.etat_de_tache

COL_DESTINATAIRE = "Destinataire de l'annonce"    # Sortie - Actions, colonne O depuis le 28.09.2026
ID_LIEUX = "10GbGcln6s-COFX_aYb_XG9Y2_QfXmX9YlgeZwFqN4qQ"
ID_DSAS = "1fBLLFawNDtPMlg-XnYHmt1uCWyXWtq7eocz8rEXsYQE"
ONGLET_ATTRIBUTIONS = "Attributions"
ONGLET_MOIS_TEMPS = "Mois - Temps"
PROJET_BQ = "gestion-almaval"
JOURS_OUVRES_PAR_MOIS = 21.75
CONSOLE_UTILISATEURS = "https://admin.google.com/ac/users"
CONSOLE_VOICE = "https://admin.google.com/ac/apps/voice/users"
BASEROW_COLLABORATEURS = "https://data.almaval.ch/database/93/table/506"


# ------------------------------------------------ petits outils

def _appeler(outil, **kwargs):
    """Un outil de main decore par FastMCP : on appelle la fonction d'origine."""
    fn = getattr(outil, "fn", outil)
    return fn(**kwargs)


def _nombre(v):
    n = _nombre_js(v)
    return n if n == n else 0.0


def _fr(n, dec=2):
    """Nombre en francais, separateur d'espace, virgule decimale."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return _s(n)
    t = ("{:,.%df}" % dec).format(n).replace(",", " ").replace(".", ",")
    return t


def _chf(n):
    return _fr(n, 2) + " CHF"


def _jour_texte(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _essai(sortie):
    return meme_texte(sortie.ligne.get(COL["NOM"]), "Essai")


def _lien_doc(ident):
    return "https://docs.google.com/document/d/" + ident + "/edit"


def _echapper(t):
    return str("" if t is None else t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------ le contexte d'une sortie

class _Sortie:
    """Tout ce que les moteurs lisent une fois pour une sortie ouverte."""

    def __init__(self, ctx, ligne, cle, initiales, engagement):
        self.ctx = ctx
        self.ligne = ligne
        self.cle = cle
        self.init = initiales
        self.engagement = engagement or {}
        self.nom = _s(ligne.get(COL["NOM"])).strip()
        self.prenom = _s(ligne.get(COL["PRENOM"])).strip()
        self.nom_prenom = (self.nom + " " + self.prenom).strip()
        self.date_sortie = date_de(ligne.get(COL["DATE_SORTIE"])) if _est_date(ligne.get(COL["DATE_SORTIE"])) else None
        self.aujourdhui = maintenant().replace(hour=0, minute=0, second=0, microsecond=0)
        self._cache = {}

    def memo(self, cle, fabrique):
        if cle not in self._cache:
            self._cache[cle] = fabrique()
        return self._cache[cle]

    # -- lectures a la source, une fois par passage (cache du contexte du passage)

    def personne(self):
        def lire():
            for p in _onglet_partage(self.ctx, "personnes", lambda: lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"], rafraichir=True)).lignes:
                if meme_texte(p.get("Initiales"), self.init):
                    return p
            return {}
        return self.memo("personne", lire)

    def mois_temps(self):
        """Les lignes de Mois - Temps de la cle, triees par periode."""
        def lire():
            o = _onglet_partage(self.ctx, "mois_temps", lambda: lire_onglet_de(ID_BDU, ONGLET_MOIS_TEMPS, rafraichir=True))
            lignes = [l for l in o.lignes if meme_texte(l.get("Clé engagement"), self.cle)]
            lignes.sort(key=lambda l: _s(l.get("Période")))
            return lignes
        return self.memo("mois_temps", lire)

    def dernier_mois(self):
        """Le dernier mois pose qui n'est pas dans le futur."""
        limite = self.aujourdhui.strftime("%Y%m")
        candidats = [l for l in self.mois_temps() if _s(l.get("Période")) <= limite]
        return candidats[-1] if candidats else None

    def continuite(self):
        def lire():
            o = _onglet_partage(self.ctx, "continuite", lambda: lire_onglet(CFG["ONGLET_SORTIE_PATIENTS"], rafraichir=True))
            return [l for l in o.lignes if meme_texte(l.get("Clé engagement"), self.cle)
                    or (not _s(l.get("Clé engagement")).strip() and meme_texte(l.get("Initiales du sortant"), self.init))]
        return self.memo("continuite", lire)

    def baserow(self):
        def lire():
            try:
                import outils_bigquery
                rep = _appeler(outils_bigquery.bq_requete, project_id=PROJET_BQ, limite=5, sql=(
                    "SELECT id, rowid, statut, actif, url, cacher_sur_site_internet, encadres_actuels, utilisateur, nom_complet "
                    "FROM `gestion-almaval.almaval_baserow.collaborateurs` WHERE LOWER(TRIM(initiales)) = '"
                    + normaliser(self.init).replace("'", "") + "'"))
                lignes = rep.get("resultats") or []
                return lignes[0] if lignes else {}
            except Exception as exc:  # noqa: BLE001
                return {"_erreur": str(exc)[:160]}
        return self.memo("baserow", lire)

    def utilisateur(self):
        """L'utilisateur Workspace (annuaire, lecture seule) du courriel Almaval."""
        def lire():
            adresse = _s(self.ligne.get("E-mail Almaval")).strip()
            if not adresse:
                return {}
            try:
                import outils_annuaire
                return _appeler(outils_annuaire.utilisateur_lire, adresse=adresse) or {}
            except Exception as exc:  # noqa: BLE001
                return {"_erreur": str(exc)[:160]}
        return self.memo("utilisateur", lire)

    def attributions(self):
        def lire():
            o = _onglet_partage(self.ctx, "attributions", lambda: lire_onglet_de(ID_LIEUX, ONGLET_ATTRIBUTIONS, rafraichir=True))
            noms = sorties._jetons(self.nom + " " + _s(self.ligne.get("Nom d'usage")))
            prenoms = sorties._jetons(self.prenom + " " + _s(self.ligne.get("Prénom d'usage")))
            tous = noms + prenoms
            trouvees = []
            for l in o.lignes:
                t = sorties._jetons(l.get("Collaborateur"))
                if len(t) >= 2 and all(x in tous for x in t) and any(x in noms for x in t) and any(x in prenoms for x in t):
                    trouvees.append(l)
            return trouvees
        return self.memo("attributions", lire)

    def id_dossier_rh(self):
        return sorties._id_depuis_url(_s(self.ligne.get(COL["DOSSIER_RH"])))

    def sous_dossier_7(self):
        """Le sous-dossier « 7. Fin des relations » du dossier RH, cree s'il manque (jamais en simulation)."""
        def lire():
            id_rh = self.id_dossier_rh()
            if not id_rh:
                return None
            try:
                for d in enfants_de(id_rh):
                    if d.get("mimeType") == "application/vnd.google-apps.folder" and re.match(r"^\s*7\.", str(d.get("name") or "")):
                        return d
            except Exception:  # noqa: BLE001
                return None
            if not self.ctx.confirmer:
                return {"id": None, "name": "7. Fin des relations (serait créé)"}
            try:
                return creer_dossier("7. Fin des relations", id_rh)
            except Exception:  # noqa: BLE001
                return None
        return self.memo("dossier7", lire)

    def fichiers_du_7(self):
        def lire():
            d = self.sous_dossier_7()
            if not d or not d.get("id"):
                return []
            try:
                return [f for f in enfants_de(d["id"]) if f.get("mimeType") != "application/vnd.google-apps.folder"]
            except Exception:  # noqa: BLE001
                return []
        return self.memo("fichiers7", lire)

    # -- moments

    def jours_depuis_sortie(self):
        if not self.date_sortie:
            return None
        return (self.aujourdhui - self.date_sortie.replace(hour=0, minute=0, second=0, microsecond=0)).days

    def moment_venu(self, quand, jours_tache=0):
        j = self.jours_depuis_sortie()
        if j is None:
            return False
        if quand == "preparation":
            return True
        if quand == "j-45":
            return j >= -45
        if quand == "echeance":
            return j >= int(jours_tache)
        if quand == "apres":
            return j >= 1
        return False


def _onglet_partage(ctx, cle, fabrique):
    """Un onglet lu une fois par passage, dans le cache du contexte du module 5."""
    if cle not in ctx.onglets:
        ctx.onglets[cle] = fabrique()
    return ctx.onglets[cle]


# ------------------------------------------------ la file des courriels, sans doublon

def _file_lue(ctx):
    return _onglet_partage(ctx, "file_courriels", onglet_courriels)


def _brouillon_existe(ctx, type_, cle, initiales):
    for l in _file_lue(ctx).lignes:
        if meme_texte(l.get(COL_COURRIEL["TYPE"]), type_) and (
                meme_texte(l.get(COL_COURRIEL["INITIALES"]), initiales)):
            return l
    return None


def _deposer_brouillon(sortie, ordre, destinataire, objet, corps_html):
    """Un brouillon dans la file (rh@ le pose en brouillon), une fois par tache et par personne."""
    ctx = sortie.ctx
    type_ = "Sortie " + str(ordre)
    deja = _brouillon_existe(ctx, type_, sortie.cle, sortie.init)
    if deja:
        return {"existant": True, "ligne": deja.get("_ligne")}
    if _essai(sortie):
        destinataire = CFG["EMAIL_RH"]
        objet = "ESSAI " + objet
    message = {"type": type_, "initiales": sortie.init, "nomPrenom": sortie.nom_prenom,
               "destinataire": destinataire or "", "objet": objet, "corps": corps_html,
               "mode": CFG["MODE_COURRIEL"],
               "detail": "Brouillon préparé par le moteur des sorties" + ("" if destinataire else " ; destinataire à compléter")}
    ctx.rendu["file"].append({"tache": ordre, "initiales": sortie.init, "destinataire": destinataire, "objet": objet})
    if not ctx.confirmer:
        return {"existant": False, "ligne": None}
    numero = mettre_en_file(message)
    f = _file_lue(ctx)
    f.lignes.append({"_ligne": numero, COL_COURRIEL["TYPE"]: type_, COL_COURRIEL["INITIALES"]: sortie.init})
    return {"existant": False, "ligne": numero}


# ------------------------------------------------ les documents PROJET dans le sous-dossier 7

def _document_projet(sortie, nom, markdown):
    """Cree (une fois) un Google Docs au gabarit de la maison dans le sous-dossier 7. Rend {id, url, existant}."""
    if _essai(sortie):
        return {"id": None, "url": "", "existant": False, "essai": True}
    for f in sortie.fichiers_du_7():
        if meme_texte(f.get("name"), nom):
            return {"id": f["id"], "url": f.get("webViewLink") or _lien_doc(f["id"]), "existant": True}
    d = sortie.sous_dossier_7()
    sortie.ctx.rendu["drive"].append({"action": "créer le PROJET", "nom": nom, "dossier": (d or {}).get("id")})
    if not sortie.ctx.confirmer or not d or not d.get("id"):
        return {"id": None, "url": "", "existant": False}
    cree = _appeler(main.create_document, title=nom, folder_id=d["id"])
    if not isinstance(cree, dict) or not cree.get("document_id"):
        raise ValueError("création du document refusée : " + str(cree)[:160])
    _appeler(main.write_markdown, document_id=cree["document_id"], markdown=markdown, clear_first=True)
    sortie.fichiers_du_7().append({"id": cree["document_id"], "name": nom, "webViewLink": cree.get("url")})
    return {"id": cree["document_id"], "url": cree.get("url") or _lien_doc(cree["document_id"]), "existant": False}


def _nom_projet(sortie, objet, type_="Lettre"):
    return (sortie.aujourdhui.strftime("%Y%m%d") + " " + sortie.nom_prenom + " - " + objet + " - " + type_ + " PROJET")


# ------------------------------------------------ les etats

def _poser(sortie, ordre, etat, remarque):
    return marquer_taches(sortie.ctx, sortie.cle, sortie.init, [ordre], etat, remarque)


def _tache(sortie, ordre):
    return etat_de_tache(sortie.ctx, sortie.cle, sortie.init, ordre)


def _reglee(sortie, ordre):
    t = _tache(sortie, ordre)
    return t is not None and t["etat"] in ("Fait", "Sans objet")


# ------------------------------------------------ famille 2 et 7 : calculs et salaire

def _calculs_salaire(sortie):
    """Les nombres partages par 80, 90, 120, 510, 520."""
    def calc():
        e = sortie.engagement
        mensuel = _nombre(e.get("Salaire mensuel effectif"))
        mois_par_an = _nombre(e.get("Mois de salaire par an")) or 12.0
        d = sortie.date_sortie
        r = {"mensuel": mensuel, "mois_par_an": mois_par_an, "date": d}
        if d:
            fin_de_mois = (d + datetime.timedelta(days=1)).month != d.month
            jours_du_mois = ((d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)).day
            r["dernier_salaire"] = mensuel if fin_de_mois else round(mensuel * d.day / jours_du_mois, 2)
            r["dernier_mois_complet"] = fin_de_mois
            debut = date_de(e.get("Date de début")) if _est_date(e.get("Date de début")) else None
            debut_annee = datetime.datetime(d.year, 1, 1)
            depuis = max(debut_annee, debut) if debut else debut_annee
            jours_travailles = (d - depuis).days + 1
            jours_annee = 366 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) else 365
            r["fraction_annee"] = max(0.0, min(1.0, jours_travailles / jours_annee))
            r["treizieme"] = round(mensuel * r["fraction_annee"], 2) if mois_par_an >= 13 else 0.0
        m = sortie.dernier_mois() or {}
        r["periode"] = _s(m.get("Période"))
        r["solde_vacances"] = _nombre(m.get("Solde de vacances")) if m else None
        r["heures_sup"] = _nombre(m.get("Heures supplémentaires")) if m else None
        r["rattrapage"] = _nombre(m.get("Rattrapage, solde (h)")) if m else None
        r["ecart_pointage"] = _nombre(m.get("Écart de pointage, cumul de l'année (h)")) if m else None
        r["elements_paie"] = _s(m.get("Éléments de paie à traiter")) if m else ""
        r["journalier"] = round(mensuel / JOURS_OUVRES_PAR_MOIS, 2) if mensuel else 0.0
        r["montant_vacances"] = round(r["journalier"] * (r["solde_vacances"] or 0.0), 2)
        return r
    return sortie.memo("calculs", calc)


def t080_solde_vacances(sortie):
    c = _calculs_salaire(sortie)
    if c["solde_vacances"] is None:
        return _poser(sortie, 80, "", "Aucun mois posé dans BDU Mois - Temps pour " + sortie.cle + " : solde à calculer à la main")
    saisie = sortie.ctx.saisie()
    if saisie.existe(COL["SOLDE_VACANCES"]) and _s(sortie.ligne.get(COL["SOLDE_VACANCES"])).strip() == "":
        sorties._poser_objet(sortie.ctx, saisie, sortie.ligne, sortie.ligne["_ligne"], {COL["SOLDE_VACANCES"]: c["solde_vacances"]})
    return _poser(sortie, 80, "Fait", "Solde de vacances lu dans BDU Mois - Temps, période " + c["periode"] + " : "
                  + _fr(c["solde_vacances"], 2) + " jour(s), écrit dans la fiche (colonne « " + COL["SOLDE_VACANCES"] + " »)")


def t090_heures(sortie):
    c = _calculs_salaire(sortie)
    if c["heures_sup"] is None:
        return _poser(sortie, 90, "", "Aucun mois posé dans BDU Mois - Temps pour " + sortie.cle)
    total = (c["heures_sup"] or 0.0) + (c["rattrapage"] or 0.0)
    saisie = sortie.ctx.saisie()
    ecrit = ""
    if total and saisie.existe(COL["HEURES_SOLDE"]) and _s(sortie.ligne.get(COL["HEURES_SOLDE"])).strip() == "":
        sorties._poser_objet(sortie.ctx, saisie, sortie.ligne, sortie.ligne["_ligne"], {COL["HEURES_SOLDE"]: round(total, 2)})
        ecrit = " ; « " + COL["HEURES_SOLDE"] + " » = " + _fr(total) + " h écrit dans la fiche"
    return _poser(sortie, 90, "En cours", "BDU Mois - Temps, période " + c["periode"] + " : heures supplémentaires "
                  + _fr(c["heures_sup"]) + " h, rattrapage " + _fr(c["rattrapage"]) + " h, écart de pointage cumulé sur l'année "
                  + _fr(c["ecart_pointage"]) + " h" + ecrit + " ; l'arbitrage (heures à payer, à compenser ou négatives) reste humain, à inscrire dans « "
                  + COL["HEURES_SOLDE"] + " »" + (" ; éléments de paie : " + c["elements_paie"] if c["elements_paie"] else ""))


def t120_dernier_salaire(sortie):
    c = _calculs_salaire(sortie)
    if not c["mensuel"]:
        return _poser(sortie, 120, "", "Salaire mensuel effectif absent du Registre - Engagements pour " + sortie.cle)
    texte_ = ("Salaire mensuel effectif " + _chf(c["mensuel"]) + " ; dernier salaire "
              + (_chf(c["dernier_salaire"]) + (" (mois complet)" if c["dernier_mois_complet"] else " (prorata au " + _jour_texte(c["date"]) + ")"))
              + " ; treizième : " + (_chf(c["treizieme"]) + " (" + _fr(c["fraction_annee"] * 100, 1) + " % de l'année)" if c["treizieme"] else "sans objet, " + _fr(c["mois_par_an"], 0) + " mois de salaire"))
    return _poser(sortie, 120, "Fait", texte_ + " ; repris dans le brouillon à la paie (tâche 510)")


def _corps_paie(sortie, c):
    p = sortie.personne()
    lignes = [
        ("Collaborateur", sortie.nom_prenom),
        ("Numéro de paie", _s(p.get("N° paie")) or "à compléter"),
        ("Date d'entrée", en_jour(sortie.engagement.get("Date de début"))),
        ("Date de sortie", _jour_texte(sortie.date_sortie)),
        ("Dernier jour travaillé", en_jour(sortie.ligne.get(COL["DERNIER_JOUR"])) or _jour_texte(sortie.date_sortie)),
        ("Libéré de l'obligation de travailler", _s(sortie.ligne.get(COL["LIBERE"])) or "non renseigné"),
        ("Motif", _s(sortie.ligne.get(COL["TYPE_FIN"])) or _s(sortie.ligne.get(COL["MOTIF_SORTIE"])) or "non renseigné"),
        ("Salaire mensuel effectif", _chf(c["mensuel"])),
        ("Dernier salaire", _chf(c.get("dernier_salaire") or 0) + ("" if c.get("dernier_mois_complet") else ", prorata")),
        ("Prorata du treizième", _chf(c.get("treizieme") or 0) if c.get("treizieme") else "sans objet"),
        ("Solde de vacances", (_fr(c["solde_vacances"]) + " jour(s), soit " + _chf(abs(c["montant_vacances"])) + (" à verser" if c["montant_vacances"] >= 0 else " à retenir, vacances prises en avance")
                               + " (" + _chf(c["journalier"]) + " par jour)") if c["solde_vacances"] is not None else "à confirmer"),
        ("Heures à solder", (_fr((c["heures_sup"] or 0) + (c["rattrapage"] or 0)) + " h") if c["heures_sup"] is not None else "à confirmer"),
        ("Éléments de paie signalés", c["elements_paie"] or "aucun"),
    ]
    tableau = "".join("<tr><td>" + _echapper(k) + "</td><td>" + _echapper(v) + "</td></tr>" for k, v in lignes)
    if c["solde_vacances"] is None:
        vacances = "en tenant compte du solde de vacances que nous vous confirmerons"
    elif c["montant_vacances"] >= 0:
        vacances = "avec le versement du solde de vacances"
    else:
        vacances = "avec la retenue des vacances prises en avance"
    return ("<p>Bonjour " + _echapper(CFG["NOM_PAIE"]) + ",</p>"
            "<p>Nous vous annonçons la sortie de " + _echapper(sortie.nom_prenom) + " au " + _jour_texte(sortie.date_sortie)
            + ". Voici les éléments du dernier décompte.</p>"
            "<p><strong>Éléments du dernier décompte</strong></p><table>" + tableau + "</table>"
            "<p>Merci d'établir le dernier décompte de salaire " + vacances + " et de nous transmettre la fiche finale ainsi que le certificat de salaire.</p>")


def t510_decompte_paie(sortie, destinataire):
    c = _calculs_salaire(sortie)
    r = _deposer_brouillon(sortie, 510, destinataire or CFG["EMAIL_PAIE"],
                           "Sortie de " + sortie.nom_prenom + " au " + _jour_texte(sortie.date_sortie) + " : dernier décompte de salaire",
                           _corps_paie(sortie, c))
    return _poser(sortie, 510, "En cours", "Brouillon à la paie déposé dans la file des courriels"
                  + (" (ligne " + str(r["ligne"]) + ")" if r["ligne"] else "") + ", posé dans rh@ par le robot des courriels ; relire, joindre, envoyer, puis Fait")


def t520_solde_vacances_versement(sortie):
    c = _calculs_salaire(sortie)
    if c["solde_vacances"] is None:
        return _poser(sortie, 520, "", "Solde de vacances inconnu (aucun mois posé dans la BDU)")
    if c["solde_vacances"] == 0:
        return _poser(sortie, 520, "Sans objet", "Solde de vacances nul : rien à verser")
    if c["solde_vacances"] < 0:
        return _poser(sortie, 520, "En cours", "Solde négatif de " + _fr(c["solde_vacances"]) + " jour(s), vacances prises en avance : retenue de "
                      + _chf(-c["montant_vacances"]) + " (" + _chf(c["journalier"]) + " par jour) à arbitrer, inscrite dans le brouillon à la paie (tâche 510)")
    return _poser(sortie, 520, "En cours", "Montant à verser : " + _chf(c["montant_vacances"]) + " (" + _fr(c["solde_vacances"])
                  + " j x " + _chf(c["journalier"]) + "), inscrit dans le brouillon à la paie (tâche 510)")


def t580_annonce_salaires(sortie):
    t45 = _tache(sortie, 45)
    t510 = _tache(sortie, 510)
    if t45 and t45["etat"] == "Fait" and t510 and t510["etat"] in ("En cours", "Fait"):
        return _poser(sortie, 580, "Fait", "La masse salariale se reconstruit depuis le Registre - Engagements, qui porte la date de sortie ; "
                      "l'annonce mensuelle à la paie porte la sortie par le brouillon de la tâche 510")
    return _poser(sortie, 580, "", "En attente : date de sortie au registre (tâche 45) et brouillon à la paie (tâche 510)")


# ------------------------------------------------ famille 5 : annonces externes

def _fiche_annonce(sortie, avec_salaire=False):
    p = sortie.personne()
    e = sortie.engagement
    lignes = [
        ("Nom et prénom", sortie.nom_prenom),
        ("Date de naissance", en_jour(p.get("Date de naissance"))),
        ("Numéro AVS", _s(p.get("AVS")) or "à compléter"),
        ("Adresse", _s(p.get("Adresse"))),
        ("Entité employeuse", _s(e.get("Entité employeuse")) or _s(sortie.ligne.get(COL["ENTITE"])) or CFG["ENTITE_PAR_DEFAUT"]),
        ("Date d'entrée", en_jour(e.get("Date de début"))),
        ("Date de sortie", _jour_texte(sortie.date_sortie)),
        ("Motif", _s(sortie.ligne.get(COL["TYPE_FIN"])) or "fin des rapports de travail"),
    ]
    if avec_salaire:
        lignes.append(("Salaire annuel effectif", _chf(_nombre(e.get("Salaire annuel effectif")))))
        lignes.append(("Taux d'activité", _fr(_nombre(e.get("EPT total")) * 100, 0) + " %"))
    return "<table>" + "".join("<tr><td>" + _echapper(k) + "</td><td>" + _echapper(v) + "</td></tr>" for k, v in lignes) + "</table>"


def _annonce(sortie, ordre, destinataire, organisme, objet_court, phrase, avec_salaire=False, complement=""):
    corps = ("<p>Bonjour,</p><p>" + phrase + "</p><p><strong>Personne concernée</strong></p>"
             + _fiche_annonce(sortie, avec_salaire) + (("<p>" + complement + "</p>") if complement else "")
             + "<p>Nous restons à disposition pour toute pièce complémentaire.</p>")
    r = _deposer_brouillon(sortie, ordre, destinataire, objet_court + " : " + sortie.nom_prenom + ", sortie au " + _jour_texte(sortie.date_sortie), corps)
    return _poser(sortie, ordre, "En cours", "Brouillon " + organisme + " déposé dans la file des courriels"
                  + (" (ligne " + str(r["ligne"]) + ")" if r["ligne"] else "")
                  + (", destinataire " + destinataire if destinataire else ", destinataire à compléter dans Sortie - Actions")
                  + " ; relire, compléter le formulaire de l'organisme, envoyer, puis Fait")


def t300_lpp(sortie, dest):
    return _annonce(sortie, 300, dest, "Medpension (LPP)", "Annonce de sortie LPP",
                    "Nous vous annonçons la sortie de la caisse de pensions de la personne ci-dessous, à la fin des rapports de travail. "
                    "Merci de nous transmettre le décompte de sortie et l'attestation de libre passage.", avec_salaire=True)


def t310_avs(sortie, dest):
    return _annonce(sortie, 310, dest, "Medisuisse (AVS)", "Annonce de sortie AVS",
                    "Nous vous annonçons la sortie de la personne ci-dessous pour la caisse de compensation.", avec_salaire=True)


def t320_cdm(sortie, dest):
    e = sortie.engagement
    p = sortie.personne()
    fermeture = (sortie.date_sortie + datetime.timedelta(days=30)) if sortie.date_sortie else None
    complement = ("Comptes concernés : RCC " + (_s(e.get("RCC utilisé")) or _s(p.get("RCC personnel")) or "à compléter")
                  + ", GLN " + (_s(p.get("GLN")) or "à compléter")
                  + ". Merci de garder le compte ouvert pour les dernières factures et de le fermer dès le "
                  + _jour_texte(fermeture) + ", et d'annuler à cette date toute retenue en cours. Cette annonce vaut pour la Hotline et pour le service des salaires.")
    return _annonce(sortie, 320, dest, "Caisse des médecins", "Annonce de sortie Caisse des médecins",
                    "Nous vous annonçons la fin de l'activité de la personne ci-dessous au sein de notre institution.", complement=complement)


def t380_axa(sortie, dest):
    return _annonce(sortie, 380, dest, "AXA (LAA et perte de gain)", "Annonce de sortie assurance de personnes",
                    "Nous vous annonçons la sortie de la personne ci-dessous des polices LAA et perte de gain maladie de notre institution.",
                    avec_salaire=True)


def _dsas_trimestre(d):
    return str(d.year) + " T" + str((d.month - 1) // 3 + 1)


def _dsas_porte_la_personne(sortie):
    """Vrai si l'onglet du trimestre de la sortie, dans le classeur DSAS, nomme la personne."""
    q = _dsas_trimestre(sortie.date_sortie)
    def lire():
        try:
            classeur = _classeur(ID_DSAS, rafraichir=True)
            prop = _onglet(classeur, q)
            if prop is None:
                return None
            _oublier(ID_DSAS, prop["title"])
            grille = _lire_grille(ID_DSAS, prop["title"])
        except Exception:  # noqa: BLE001
            return None
        noms = [x for x in sorties._jetons(sortie.nom) if len(x) >= 3] or sorties._jetons(sortie.nom)
        prenoms = [x for x in sorties._jetons(sortie.prenom) if len(x) >= 3] or sorties._jetons(sortie.prenom)
        for r in grille:
            texte_ligne = normaliser(" ".join(texte(v) for v in r if v not in (None, "")))
            if noms and prenoms and any(x in texte_ligne for x in noms) and any(x in texte_ligne for x in prenoms):
                return True
        return False
    return sortie.memo("dsas_" + q, lire)


def t350_dsas(sortie):
    q = _dsas_trimestre(sortie.date_sortie)
    r = _dsas_porte_la_personne(sortie)
    if r is True:
        return _poser(sortie, 350, "Fait", "Sortie portée par l'annonce trimestrielle DSAS " + q)
    if r is None:
        return _poser(sortie, 350, "", "Annonce trimestrielle DSAS " + q + " pas encore produite : la sortie y sera portée par le robot DSAS (fenêtre du 15 au dernier jour du trimestre)")
    return _poser(sortie, 350, "", "L'onglet DSAS " + q + " existe mais ne nomme pas la personne : à vérifier avant l'envoi de l'annonce")


def t360_registre_dsas(sortie):
    q = _dsas_trimestre(sortie.date_sortie)
    r = _dsas_porte_la_personne(sortie)
    if r is True:
        return _poser(sortie, 360, "Fait", "Ligne présente dans l'onglet DSAS " + q + ", registre des annonces tenu par le robot DSAS")
    return _poser(sortie, 360, "", "Sera inscrite par le robot DSAS dans l'onglet " + q)


# ------------------------------------------------ famille 3 : continuite clinique

def _patients_repris(sortie):
    return [l for l in sortie.continuite() if normaliser(l.get("Décision")).startswith("repris")]


def t170_attribution(sortie):
    rows = sortie.continuite()
    if not rows:
        return _poser(sortie, 170, "", "Liste des patients pas encore éditée (tâche 150)")
    repris = _patients_repris(sortie)
    sans = [l for l in repris if not _s(l.get("Repris par")).strip()]
    non_decides = [l for l in rows if not _s(l.get("Décision")).strip()]
    if not repris and not non_decides:
        return _poser(sortie, 170, "Sans objet", "Aucun patient repris en interne (" + str(len(rows)) + " patient(s) listés, tous adressés ou clôturés)")
    if not sans and not non_decides:
        return _poser(sortie, 170, "Fait", str(len(repris)) + " patient(s) repris, chacun attribué à son nouveau thérapeute")
    noms = ", ".join(_s(l.get("Patient")) for l in sans[:12]) + (" …" if len(sans) > 12 else "")
    return _poser(sortie, 170, "En cours", str(len(sans)) + " patient(s) repris sans thérapeute attribué" + (" : " + noms if noms else "")
                  + (" ; " + str(len(non_decides)) + " sans décision" if non_decides else ""))


def t180_information_patients(sortie):
    repris = [l for l in _patients_repris(sortie) if _s(l.get("Repris par")).strip()]
    if not repris:
        return 0
    non_informes = [l for l in repris if not _est_date(l.get("Patient informé le")) and not _s(l.get("Patient informé le")).strip()]
    if not non_informes:
        return _poser(sortie, 180, "Fait", str(len(repris)) + " patient(s) informé(s) par écrit")
    md = ["# Lettres aux patients, changement de thérapeute", "",
          "Projet préparé par le moteur des sorties le " + _jour_texte(sortie.aujourdhui) + " pour la sortie de " + sortie.nom_prenom
          + " au " + _jour_texte(sortie.date_sortie) + ". Une lettre par patient repris ; à relire et signer par le thérapeute.", ""]
    for l in non_informes:
        md += ["## " + _s(l.get("Patient")) + (" (" + _s(l.get("Identifiant patient")) + ")" if _s(l.get("Identifiant patient")) else ""), "",
               "Madame, Monsieur,", "",
               "Votre thérapeute, " + sortie.nom_prenom + ", quitte Almaval le " + _jour_texte(sortie.date_sortie)
               + ". Afin d'assurer la continuité de votre suivi, " + _s(l.get("Repris par")) + " reprend votre accompagnement"
               + (" dès le " + en_jour(l.get("Date de reprise")) if _s(l.get("Date de reprise")) else "") + ".", "",
               "Prestation en cours : " + (_s(l.get("Prestation en cours")) or "non précisée") + ".", "",
               "Nous restons à votre disposition pour toute question et vous remercions de votre confiance.", ""]
    doc = _document_projet(sortie, _nom_projet(sortie, "Lettres aux patients"), "\n".join(md))
    return _poser(sortie, 180, "En cours", str(len(non_informes)) + " lettre(s) en PROJET" + (" : " + doc["url"] if doc.get("url") else " (créé au passage confirmé)")
                  + " ; relire, signer, envoyer, puis dater « Patient informé le » dans Sortie - Continuité clinique")


def t190_prescriptions(sortie):
    rows = sortie.continuite()
    if not rows:
        return 0
    prescrits = [l for l in rows if re.search(r"psychoth|prescri|pp\s?\d|délégu|delegu", normaliser(l.get("Prestation en cours")))]
    if not prescrits:
        return _poser(sortie, 190, "Sans objet", "Aucune psychothérapie prescrite en cours parmi les " + str(len(rows)) + " patient(s)")
    noms = ", ".join(_s(l.get("Patient")) + (" (" + _s(l.get("Repris par")) + ")" if _s(l.get("Repris par")) else "") for l in prescrits[:15])
    return _poser(sortie, 190, "En cours", str(len(prescrits)) + " prescription(s) à transférer au nouveau thérapeute, nouvelle demande au médecin prescripteur : " + noms)


def _index_patients(ctx):
    return _onglet_partage(ctx, "index_patients", lambda: lire_onglet_de(CFG["CLASSEUR_PATIENTS"], CFG["ONGLET_INDEX_PATIENTS"], rafraichir=True))


def t200_medecins(sortie):
    rows = sortie.continuite()
    if not rows:
        return 0
    try:
        index = _index_patients(sortie.ctx)
    except Exception as exc:  # noqa: BLE001
        return _poser(sortie, 200, "", "Index patients illisible : " + str(exc)[:120])
    par_id = {}
    for p in index.lignes:
        for k in ("ID Almaval", "N Patient MediOnline"):
            v = _s(p.get(k)).strip()
            if v:
                par_id[v] = p
    medecins = {}
    sans_medecin = 0
    for l in rows:
        p = par_id.get(_s(l.get("Identifiant patient")).strip()) or par_id.get(_s(l.get("N patient MediOnline")).strip())
        nom_med = _s((p or {}).get("Medecin traitant - Nom")).strip()
        if not p or not nom_med or not re.search(r"[a-zà-ÿ]{2,}\s+[a-zà-ÿ]{2,}", nom_med.lower()):
            sans_medecin += 1
            continue
        m = medecins.setdefault(nom_med, {"email": _s(p.get("Medecin traitant - E-mail")), "adresse": _s(p.get("Medecin traitant - Adresse")), "patients": []})
        m["patients"].append(_s(l.get("Patient")) + (" (repris par " + _s(l.get("Repris par")) + ")" if _s(l.get("Repris par")) else ""))
    if not medecins:
        return _poser(sortie, 200, "Sans objet", "Aucun médecin traitant identifié pour les " + str(len(rows)) + " patient(s)")
    md = ["# Lettres aux médecins traitants et prescripteurs", "",
          "Projet préparé par le moteur des sorties le " + _jour_texte(sortie.aujourdhui) + " : " + sortie.nom_prenom + " quitte Almaval le "
          + _jour_texte(sortie.date_sortie) + ". Un paragraphe par médecin, à relire et signer.", ""]
    for nom_med, m in sorted(medecins.items()):
        md += ["## " + nom_med + ((", " + m["email"]) if m["email"] else ""), "",
               (m["adresse"] + "" if m["adresse"] else ""), "",
               "Docteur,", "",
               "Nous vous informons que " + sortie.nom_prenom + ", qui suivait " + ("votre patient " if len(m["patients"]) == 1 else "vos patients ")
               + ", ".join(m["patients"]) + ", quitte notre institution le " + _jour_texte(sortie.date_sortie)
               + ". La continuité du suivi est assurée comme indiqué entre parenthèses ; nous vous remercions de nous adresser toute nouvelle prescription au thérapeute repreneur.", ""]
    doc = _document_projet(sortie, _nom_projet(sortie, "Lettres aux médecins traitants"), "\n".join(md))
    return _poser(sortie, 200, "En cours", str(len(medecins)) + " médecin(s) à informer, lettres en PROJET" + (" : " + doc["url"] if doc.get("url") else " (créé au passage confirmé)")
                  + (" ; " + str(sans_medecin) + " patient(s) sans médecin identifié" if sans_medecin else ""))


# ------------------------------------------------ famille 4 : documents

def t260_attestation_chomage(sortie):
    p = sortie.personne()
    e = sortie.engagement
    c = _calculs_salaire(sortie)
    md = ["# Données pour l'attestation de l'employeur (formulaire 10006 f, assurance-chômage)", "",
          "Préparé par le moteur des sorties le " + _jour_texte(sortie.aujourdhui) + ". À reporter dans le formulaire officiel, puis signer.", "",
          "## Employeur", "",
          "Entité : " + (_s(e.get("Entité employeuse")) or CFG["ENTITE_PAR_DEFAUT"]), "",
          "## Personne", "",
          "Nom et prénom : " + sortie.nom_prenom, "",
          "Date de naissance : " + en_jour(p.get("Date de naissance")), "",
          "Numéro AVS : " + (_s(p.get("AVS")) or "à compléter"), "",
          "Adresse : " + _s(p.get("Adresse")), "",
          "## Rapports de travail", "",
          "Du " + en_jour(e.get("Date de début")) + " au " + _jour_texte(sortie.date_sortie), "",
          "Fonction : " + (_s(e.get("Profession")) or _s(sortie.ligne.get(COL["PROFESSION"]))), "",
          "Taux d'activité : " + _fr(_nombre(e.get("EPT total")) * 100, 0) + " %", "",
          "Motif de la fin des rapports : " + (_s(sortie.ligne.get(COL["TYPE_FIN"])) or "à compléter"), "",
          "Résiliation reçue le : " + en_jour(sortie.ligne.get(COL["RESILIATION_RECUE"])), "",
          "## Salaire", "",
          "Salaire mensuel effectif : " + _chf(c["mensuel"]), "",
          "Mois de salaire par an : " + _fr(c["mois_par_an"], 0), "",
          "Solde de vacances à la sortie : " + (_fr(c["solde_vacances"]) + " jour(s)" if c["solde_vacances"] is not None else "à confirmer"), "",
          "Les salaires mensuels des douze derniers mois se lisent dans les fiches de salaire du dossier personnel (1b).", ""]
    doc = _document_projet(sortie, _nom_projet(sortie, "Attestation de l'employeur, données", "Document"), "\n".join(md))
    return _poser(sortie, 260, "En cours", "Données réunies en PROJET" + (" : " + doc["url"] if doc.get("url") else " (créé au passage confirmé)")
                  + " ; remplir le formulaire 10006 f, signer, remettre, puis Fait")


def t280_attestation_lpp(sortie, dest):
    limite = sortie.date_sortie
    for f in sortie.fichiers_du_7():
        nom = normaliser(f.get("name"))
        cree = f.get("createdTime") or f.get("modifiedTime") or ""
        if "lpp" in nom and cree[:10] >= limite.strftime("%Y-%m-%d"):
            return _poser(sortie, 280, "Fait", "Attestation LPP présente dans le sous-dossier 7 : " + _s(f.get("name")))
    r = _deposer_brouillon(sortie, 280, dest, "Attestation de sortie LPP : " + sortie.nom_prenom,
                           "<p>Bonjour,</p><p>Nous vous remercions de nous transmettre l'attestation de sortie LPP et le décompte de libre passage de "
                           + _echapper(sortie.nom_prenom) + ", sorti(e) de nos effectifs le " + _jour_texte(sortie.date_sortie) + ".</p>" + _fiche_annonce(sortie))
    return _poser(sortie, 280, "En cours", "Aucune attestation LPP dans le sous-dossier 7 trente jours après la sortie ; brouillon de relance à Medpension "
                  + "déposé dans la file" + (" (ligne " + str(r["ligne"]) + ")" if r["ligne"] else ""))


# ------------------------------------------------ famille 6 : acces et materiel

def t430_workspace(sortie):
    u = sortie.utilisateur()
    adresse = _s(sortie.ligne.get("E-mail Almaval")).strip()
    if not adresse:
        return _poser(sortie, 430, "Sans objet", "Aucun compte Almaval sur la fiche")
    if u.get("suspendu") is True:
        return _poser(sortie, 430, "Fait", "Compte " + adresse + " suspendu dans l'annuaire")
    if u.get("_erreur") or u.get("erreur") or not u:
        return _poser(sortie, 430, "", "Compte " + adresse + " : annuaire illisible (" + _s(u.get("_erreur") or u.get("detail") or u.get("erreur"))
                      + ") ; suspendre dans la console " + CONSOLE_UTILISATEURS)
    return _poser(sortie, 430, "En cours", "Compte " + adresse + " encore actif : suspendre dans la console " + CONSOLE_UTILISATEURS
                  + " (la suspension reste un geste humain, l'annuaire n'a que la lecture) ; le passage suivant constatera la suspension")


def t480_voice(sortie):
    u = sortie.utilisateur()
    adresse = _s(sortie.ligne.get("E-mail Almaval")).strip()
    if not adresse:
        return _poser(sortie, 480, "Sans objet", "Aucun compte Almaval sur la fiche")
    if u.get("suspendu") is True:
        return _poser(sortie, 480, "Fait", "Compte " + adresse + " suspendu : le numéro Voice est libéré à la suppression du compte")
    return _poser(sortie, 480, "En cours", "Libérer le numéro Voice du compte " + adresse + " dans la console " + CONSOLE_VOICE
                  + " ; Fait dès que le compte est suspendu")


def t460_agenda_bureau(sortie):
    lignes = sortie.attributions()
    fin = sortie.date_sortie
    actives = []
    for l in lignes:
        if not meme_texte(l.get("Statut"), "Active"):
            continue
        d_fin = date_de(l.get("Date de fin")) if _est_date(l.get("Date de fin")) else None
        if d_fin is None or d_fin > fin:
            actives.append(_s(l.get("Bureau")) + " " + _s(l.get("Jour")) + " " + _s(l.get("Demi-journée")) + (" jusqu'au " + _jour_texte(d_fin) if d_fin else " sans fin"))
    if not lignes:
        return _poser(sortie, 460, "Sans objet", "Aucune attribution de bureau au nom de la personne dans Almaval - Lieux - BDU")
    if not actives:
        return _poser(sortie, 460, "Fait", "Toutes les attributions de bureau se terminent au plus tard le " + _jour_texte(fin))
    return _poser(sortie, 460, "En cours", str(len(actives)) + " attribution(s) encore active(s) après la sortie : " + " ; ".join(actives[:8])
                  + " ; à fermer dans la grille des lieux")


def t470_baserow(sortie):
    b = sortie.baserow()
    if b.get("_erreur"):
        return _poser(sortie, 470, "", "Miroir Baserow illisible : " + b["_erreur"])
    if not b:
        return _poser(sortie, 470, "Sans objet", "Aucune fiche Baserow aux initiales " + sortie.init)
    statut = _s(b.get("statut"))
    if normaliser(statut) == "ancien" or normaliser(b.get("actif")) in ("false", "0", "non"):
        return _poser(sortie, 470, "Fait", "Fiche Baserow en statut « " + statut + " », accès Almadesk fermés")
    return _poser(sortie, 470, "En cours", "Fiche Baserow encore en statut « " + statut + " » : passer la fiche en Ancien dans " + BASEROW_COLLABORATEURS
                  + " (ce qui ferme Almadesk), retirer les accès applicatifs, informer Gaby pour BR")


def t490_site(sortie):
    b = sortie.baserow()
    if b.get("_erreur"):
        return _poser(sortie, 490, "", "Miroir Baserow illisible : " + b["_erreur"])
    if not b:
        return _poser(sortie, 490, "Sans objet", "Aucune fiche Baserow, donc aucune page sur le site")
    cache = normaliser(b.get("cacher_sur_site_internet")) in ("true", "1", "oui", "x")
    if cache or normaliser(b.get("statut")) == "ancien":
        return _poser(sortie, 490, "Fait", "Fiche Baserow masquée du site (« cacher sur site internet » ou statut Ancien)")
    return _poser(sortie, 490, "En cours", "Page encore publiée" + (" : " + _s(b.get("url")) if _s(b.get("url")) else "") + " ; cocher « cacher sur site internet » dans la fiche Baserow "
                  + BASEROW_COLLABORATEURS)


# ------------------------------------------------ le registre des moteurs et le crochet

MOTEURS = {
    80: ("preparation", lambda s, d: t080_solde_vacances(s)),
    90: ("preparation", lambda s, d: t090_heures(s)),
    120: ("preparation", lambda s, d: t120_dernier_salaire(s)),
    510: ("j-45", lambda s, d: t510_decompte_paie(s, d)),
    520: ("j-45", lambda s, d: t520_solde_vacances_versement(s)),
    580: ("preparation", lambda s, d: t580_annonce_salaires(s)),
    300: ("j-45", lambda s, d: t300_lpp(s, d)),
    310: ("j-45", lambda s, d: t310_avs(s, d)),
    320: ("j-45", lambda s, d: t320_cdm(s, d)),
    380: ("j-45", lambda s, d: t380_axa(s, d)),
    350: ("preparation", lambda s, d: t350_dsas(s)),
    360: ("preparation", lambda s, d: t360_registre_dsas(s)),
    170: ("preparation", lambda s, d: t170_attribution(s)),
    180: ("preparation", lambda s, d: t180_information_patients(s)),
    190: ("preparation", lambda s, d: t190_prescriptions(s)),
    200: ("preparation", lambda s, d: t200_medecins(s)),
    260: ("preparation", lambda s, d: t260_attestation_chomage(s)),
    280: ("echeance", lambda s, d: t280_attestation_lpp(s, d)),
    430: ("apres", lambda s, d: t430_workspace(s)),
    480: ("echeance", lambda s, d: t480_voice(s)),
    460: ("echeance", lambda s, d: t460_agenda_bureau(s)),
    470: ("apres", lambda s, d: t470_baserow(s)),
    490: ("apres", lambda s, d: t490_site(s)),
}


def _destinataires(ctx):
    """Ordre -> destinataire de l'annonce, jours par rapport a la sortie et condition d'application, lus dans Sortie - Actions."""
    dest, jours, regles = {}, {}, {}
    for t in ctx.actions().lignes:
        o = _s(t.get(COL_SORTIE["ORDRE"])).strip()
        if o:
            dest[o] = _s(t.get(COL_DESTINATAIRE)).strip()
            jours[o] = _nombre(t.get(COL_SORTIE["JOURS"]))
            regles[o] = _s(t.get(sorties.COL_CONDITION)).strip()
    return dest, jours, regles


def executer_les_moteurs(ctx, ligne, cle, initiales, engagement):
    """Le crochet appele par le passage de nuit pour chaque sortie ouverte. Rend { ordre: resultat }."""
    sortie = _Sortie(ctx, ligne, cle, initiales, engagement)
    rendu = {}
    if not sortie.date_sortie:
        return rendu
    dest, jours, regles = _destinataires(ctx)
    for ordre, (quand, moteur) in MOTEURS.items():
        t = _tache(sortie, ordre)
        if t is None:
            continue
        if t["etat"] in ("Fait", "Sans objet"):
            continue
        if not sortie.moment_venu(quand, jours.get(str(ordre), 0)):
            continue
        regle = regles.get(str(ordre), "")
        if regle:
            verdict, _lecture = sorties.evaluer_condition(regle, ligne, engagement)
            if verdict != "oui":
                rendu[str(ordre)] = {"etat": t["etat"], "touchee": False, "attente": "condition " + (verdict or "sans verdict")}
                continue
        try:
            n = moteur(sortie, dest.get(str(ordre), ""))
            apres = _tache(sortie, ordre) or {}
            rendu[str(ordre)] = {"etat": apres.get("etat", ""), "touchee": bool(n)}
        except Exception as exc:  # noqa: BLE001
            rendu[str(ordre)] = {"erreur": str(exc)[:200]}
            try:
                _poser(sortie, ordre, "", "Moteur en échec : " + str(exc)[:160])
            except Exception:  # noqa: BLE001
                pass
    return rendu


def _greffer():
    """Enveloppe appliquer_les_conditions du module 5 : conditions d'abord, moteurs ensuite,
    compte rendu par cle dans rendu["moteurs"], compteur de taches touchees ajoute au bilan."""
    if getattr(sorties.appliquer_les_conditions, "_moteurs_greffes", False):
        return
    original = sorties.appliquer_les_conditions

    def enveloppe(ctx, ligne, cle, initiales, engagement):
        bilan = original(ctx, ligne, cle, initiales, engagement)
        try:
            moteurs = executer_les_moteurs(ctx, ligne, cle, initiales, engagement)
        except Exception as exc:  # noqa: BLE001
            moteurs = {"_erreur": str(exc)[:200]}
        if moteurs:
            ctx.rendu.setdefault("moteurs", {})[cle or initiales] = moteurs
            touchees = [o for o, r in moteurs.items() if isinstance(r, dict) and r.get("touchee")]
            bilan.setdefault("moteurs_touchees", []).extend(touchees)
        return bilan

    enveloppe._moteurs_greffes = True
    sorties.appliquer_les_conditions = enveloppe


_greffer()
