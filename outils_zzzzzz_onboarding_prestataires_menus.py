"""Almaval - menus imposes des colonnes du contrat de prestation de services, 29.09.2026.

Decision d'Alberto du 29.09.2026 : un prestataire ne recoit jamais de contrat
de travail, mais un seul document, le contrat de prestation de services,
assemble selon ce que ses prestations demandent (confidentialite, secret
professionnel, sous-traitance des donnees, acces aux systemes, droits
d'auteur, statut d'independant, resume des conditions en annexe). Ce contrat
se produit depuis AlmaDesk Admin, ecran Prestataires, qui lit ses parametres
dans deux onglets de l'Effectif :

  - Registre - Entites : identite de la partie (nature, IDE, adresse,
    representant, contact, dossier) ;
  - Registre - Contrats de prestations : lieu d'execution, preavis, TVA,
    acces, donnees, livrables, pieces, statut du contrat.

Ce module ajoute les menus de ces colonnes a MENUS_IMPOSES du moteur
outils_zzzzz_onboarding_4_validations (passage de 6 h, apres le distributeur),
sans le reecrire, comme outils_zzzzzz_onboarding_raison_sociale. Parite
tenue dans le fichier Apps Script « 13f Menus des entites et des contrats de
prestations » du projet d'onboarding. Les listes vivent dans Almaval - Listes,
onglet Valeurs, et sont distribuees a l'onglet Listes de l'Effectif par la
ligne 2 d'Abonnements.
"""

try:
    import outils_zzzzz_onboarding_4_validations as _validations
    from outils_zzzzz_onboarding_0_socle import ID_EFFECTIF as _ID_EFFECTIF

    _CONTRATS = "Registre - Contrats de prestations"
    _AJOUTS = [
        ("Registre - Entités", "Nature de la partie contractante", "Nature de la partie contractante"),
        (_CONTRATS, "Lieu d'exécution", "Lieu d'exécution"),
        (_CONTRATS, "Préavis de résiliation", "Préavis de résiliation"),
        (_CONTRATS, "Régime de TVA", "Régime de TVA"),
        (_CONTRATS, "Accès aux systèmes", "Coche"),
        (_CONTRATS, "Données personnelles traitées", "Coche"),
        (_CONTRATS, "Données de santé", "Coche"),
        (_CONTRATS, "Hébergement des données", "Hébergement des données"),
        (_CONTRATS, "Livrables et droits d'auteur", "Coche"),
        (_CONTRATS, "Pièces justificatives reçues", "Coche"),
        (_CONTRATS, "Statut du contrat de prestation", "Statut du contrat de prestation"),
    ]
    _menus = _validations.MENUS_IMPOSES.setdefault(_ID_EFFECTIF, [])
    _poses = 0
    for _onglet, _colonne, _liste in _AJOUTS:
        if any(m.get("onglet") == _onglet and m.get("colonne") == _colonne for m in _menus):
            continue
        _menus.append(_validations._m(_onglet, _colonne, _liste))
        _poses += 1
    print("[onboarding prestataires menus] menus imposes ajoutes : " + str(_poses), flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding prestataires menus] non pose : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
