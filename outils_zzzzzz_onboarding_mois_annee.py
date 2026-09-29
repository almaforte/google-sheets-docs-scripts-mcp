"""Almaval - onboarding : faux ecarts sur les colonnes mm.aaaa, 29.09.2026.

Suite du CoDir du 28.09.2026 (point 2, fiabilisation des moteurs), nuit du
29.09.2026, avec autorisation d'Alberto de lever tout blocage.

LE CONSTAT. Les colonnes « Début de la formation postgrade (mm.aaaa) » et
« Obtention du titre (mm.aaaa) » ont le format « Texte » dans Mutations -
Règles. La fiche les porte en texte (« 11.2025 ») ou en date affichee
mm.aaaa, le Registre - Personnes en date du premier du mois (01/11/2025).
_cle_de_comparaison les comparait comme du texte : une trentaine de fiches
affichaient chaque nuit « 1 changement non enregistré : Début de la
formation postgrade » alors que la valeur etait la meme.

LE REMEDE. Ce module ne reecrit pas le moteur. Il enveloppe
comparer_saisie_registre au chargement (nom global appele par
etat_de_la_saisie a chaque passage) et retire des changements ceux d'une
regle mm.aaaa dont les deux valeurs designent le meme mois. Aucune autre
regle n'est touchee, l'ecriture au registre non plus. Son nom le fait
charger apres outils_zzzzz_onboarding_6_mutations (ordre alphabetique de
bootstrap). Le projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », fichier « 13 Mutations », porte la meme correction depuis
le meme jour (cleDeComparaison_).
"""

try:
    import re as _re
    import outils_zzzzz_onboarding_6_mutations as _mut

    _RE_MOIS = _re.compile(r"^\s*(\d{1,2})[./](\d{4})\s*$")

    def _mois_de(v):
        """Cle « aaaa-mm » d'une valeur mm.aaaa, d'une date du premier du mois, ou None."""
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            if not 20000 < float(v) < 80000:
                return None
            try:
                d = _mut.date_de(float(v))
            except Exception:  # noqa: BLE001
                return None
            if d is None or d.day != 1:
                return None
            return "%04d-%02d" % (d.year, d.month)
        m = _RE_MOIS.match(str(v))
        if m and 1 <= int(m.group(1)) <= 12:
            return "%s-%02d" % (m.group(2), int(m.group(1)))
        m = _re.match(r"^\s*0?1[./]0?(\d{1,2})[./](\d{4})\s*$", str(v))
        if m and 1 <= int(m.group(1)) <= 12:
            return "%s-%02d" % (m.group(2), int(m.group(1)))
        return None

    def _est_regle_mm_aaaa(regle):
        try:
            return any(isinstance(x, str) and "(mm.aaaa)" in x for x in regle.values())
        except Exception:  # noqa: BLE001
            return False

    _comparer_origine = _mut.comparer_saisie_registre

    def _comparer_sans_faux_ecart_mois(*args, **kwargs):
        changements = _comparer_origine(*args, **kwargs)
        try:
            garde = []
            for c in changements or []:
                r = c.get("regle") or {}
                if _est_regle_mm_aaaa(r):
                    a, b = _mois_de(c.get("ancien")), _mois_de(c.get("nouveau"))
                    if a is not None and a == b:
                        continue
                garde.append(c)
            return garde
        except Exception:  # noqa: BLE001
            return changements

    if not getattr(_mut.comparer_saisie_registre, "_mois_annee", False):
        _comparer_sans_faux_ecart_mois._mois_annee = True
        _mut.comparer_saisie_registre = _comparer_sans_faux_ecart_mois
    print("[onboarding mois annee] comparaison mm.aaaa posee", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[onboarding mois annee] non posee : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
