"""Almaval - onboarding : ecart avec le registre sur le taux en vigueur, 28.09.2026.

Chantier Referent de lieu, demande d'Alberto du 28.09.2026 : « clore
integralement le chantier », avec autorisation de lever tout blocage.

La colonne « Ecart avec le registre » de Registre - Engagements, posee
chaque nuit par poser_l_ecart_des_affectations (outils_zzzzz_onboarding_
7_postes, passage de 4 h 45 sous gestion@), sommait TOUTES les lignes de
Registre - Affectations d'un engagement : l'historique clos et les lignes
a venir comptaient comme si elles etaient en vigueur. Chaque mutation du
cahier des charges faisait donc paraitre un faux ecart (Foery et Cencio
d'abord, puis les quatre referents de lieu mutes au 01.10.2026).

La somme porte desormais sur « Taux en vigueur », la colonne que
l'enveloppe 49 pose a zero pour une ligne hors vigueur a la date de
reference de l'engagement. Verifie en place le 28.09.2026 : zero ecart
sur tout le registre avec cette formule, contre sept avec l'ancienne. Le
fichier Apps Script « 28 Postes et responsables » porte la meme
correction depuis le meme jour.

Ce module ne reecrit pas le moteur : il remplace sa fonction
_formule_ecart au chargement, comme outils_zzzzzz_lieux_cloture le fait
pour les lieux. Son nom le fait charger apres outils_zzzzz_onboarding_
7_postes (bootstrap importe les modules par ordre alphabetique).
poser_l_ecart_des_affectations appelle _formule_ecart par son nom de
module a chaque passage, d'ou l'effet du remplacement.
"""

try:
    import outils_zzzzz_onboarding_7_postes as _postes

    def _formule_ecart_en_vigueur(s):
        aff = "'" + _postes.CFG_POSTES["ONGLET_AFFECTATIONS"] + "'"

        def colonne(nom):
            return "INDEX($A$3:$FA" + s + "0" + s + 'MATCH("' + nom + '"' + s + "$1:$1" + s + "0))"

        def colonne_aff(nom):
            return ("INDEX(" + aff + "!$A$3:$AZ" + s + "0" + s + 'MATCH("' + nom + '"' + s
                    + aff + "!$A$1:$AZ$1" + s + "0))")

        return ('={"calcul";ARRAYFORMULA(IF((' + colonne("Initiales") + '="")+('
                + colonne("État de l'engagement") + '="Clos")>0' + s + '""' + s
                + "ROUND(N(" + colonne("EPT total") + ")-SUMIF(" + colonne_aff("Clé engagement") + s
                + "$A$3:$A" + s + colonne_aff(_postes.PA["COL_TAUX_VIGUEUR"]) + ")"
                + s + "3)))}")

    _postes._formule_ecart = _formule_ecart_en_vigueur
    print("[onboarding ecart] formule de l'ecart posee sur le taux en vigueur", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding ecart] non posee : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
