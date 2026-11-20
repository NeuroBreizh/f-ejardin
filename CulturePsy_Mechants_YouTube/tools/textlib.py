"""Outils texte partagés : lecture du script v3, typographie française, découpage en phrases et en mots."""
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'script' / 'Culture_Psy_Mechants_YouTube_Voix_off_v3.txt'
NNBSP = ' '  # espace fine insécable

# Intitulés des chapitres YouTube (brief §8), dans l'ordre des lignes [CHAPITRE · …] du script.
CHAPTER_TITLES = [
    'Deux enfants',
    'Walter : le petit-déjeuner et l’aveu',
    'Eren : avec qui a-t-on grandi ?',
    'Anakin : qui a levé la main ?',
    'Le test : changer la consigne',
    'Le plaisir de regarder',
    'Revenir au livre',
]

REF_MARKER = 'Références pour la description YouTube'


def typo(t: str) -> str:
    """Typographie française : espaces fines insécables avant ? ! : ; et à l'intérieur des « », apostrophes typographiques."""
    t = t.replace("'", '’')
    t = re.sub(r'[   ]*([?!:;»])', lambda m: NNBSP + m.group(1), t)
    t = re.sub(r'«[   ]*', '«' + NNBSP, t)
    # pas d'espace avant ces signes en début de chaîne
    t = re.sub(r'^ ', '', t)
    return t


def norm_ws(t: str) -> str:
    """Normalisation pour les comparaisons : toutes les espaces deviennent une espace simple."""
    t = unicodedata.normalize('NFC', t)
    t = re.sub(r'[\s  ]+', ' ', t)
    t = re.sub(r' ([?!:;»])', r'\1', t)
    t = re.sub(r'« ', '«', t)
    return t.strip()


def parse_script(path: Path = SCRIPT):
    """Retourne chapitres, paragraphes de narration (hors crochets), notes de montage, crédits et références."""
    lines = path.read_text(encoding='utf-8').splitlines()
    chapters, paragraphs, notes, credits, refs = [], [], [], [], []
    in_refs = False
    pending_notes = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith('['):
            inner = line[1:-1].strip() if line.endswith(']') else line[1:].strip()
            if in_refs:
                refs.append(inner)
                continue
            if inner.startswith(REF_MARKER):
                in_refs = True
                continue
            m = re.match(r'CHAPITRE\s*·\s*(.+)$', inner)
            if m:
                chapters.append({'index': len(chapters), 'script_label': m.group(1), 'title': CHAPTER_TITLES[len(chapters)], 'first_paragraph': len(paragraphs)})
                continue
            for cm in re.finditer(r'À l’écran\s*:\s*([^\]]+?)(?:\.\s*(?=[A-ZÀ-Ý]|$)|$)', inner):
                credits.append({'text': cm.group(1).strip().rstrip('.'), 'before_paragraph': len(paragraphs), 'note': inner})
            notes.append({'text': inner, 'before_paragraph': len(paragraphs)})
            pending_notes.append(inner)
            continue
        if in_refs:
            raise ValueError(f'Texte hors crochets après les références : {line}')
        paragraphs.append({'index': len(paragraphs), 'text': line, 'chapter': len(chapters) - 1, 'notes': pending_notes})
        pending_notes = []
    return {'chapters': chapters, 'paragraphs': paragraphs, 'notes': notes, 'credits': credits, 'refs': refs}


# Fin de phrase : . ? ! … éventuellement suivis de », puis espace et majuscule / « , ou fin de paragraphe.
_SENT_END = re.compile(r'([.?!…](?:\s*»)?)\s+(?=[«A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒ])')


def split_sentences(par: str):
    out, last = [], 0
    for m in _SENT_END.finditer(par):
        # « … », écoute : pas une fin de phrase (suivi d'une virgule) — géré par le lookahead (majuscule requise)
        end = m.end(1)
        out.append(par[last:end].strip())
        last = m.end()
    tail = par[last:].strip()
    if tail:
        out.append(tail)
    return out


WORD_RE = re.compile(r'[0-9A-Za-zÀ-ÿœæŒÆ’\'-]+')


def tokens(sentence: str):
    """Jetons séparés par des espaces ; chaque jeton porte son texte et, s'il en a un, le mot prononcé."""
    toks = []
    for t in sentence.split():
        w = ''.join(WORD_RE.findall(t))
        toks.append({'t': t, 'w': w})
    return toks


VOWELS = re.compile(r'[aeiouyàâäéèêëîïôöùûüœæ]+')
NUMBER_WORDS = {'50': 1, '1975': 4, '2023': 3, '1999': 4, '2001': 2, '2004': 2}


def spoken_words(w: str) -> float:
    """Nombre de mots prononcés pour le débit (les années se disent en plusieurs mots)."""
    if w in NUMBER_WORDS:
        return NUMBER_WORDS[w]
    return 1


def syllables(w0: str) -> int:
    w = w0.lower().replace('’', "'")
    w = re.sub(r"^(qu|j|l|d|n|s|c|t|m)'", '', w)
    if w in NUMBER_WORDS:
        return {'50': 3, '1975': 7, '2023': 5}.get(w, 5)
    groups = VOWELS.findall(w)
    n = 0
    for g in groups:
        n += 2 if re.search(r'(é[aeiou]|i[aoéè]|u[aé]|ou[aéi])', g) else 1
    if re.search(r'[^aeiouy]e(s|nt)?$', w) and n > 1:
        n -= 1
    return max(n, 1)


def narration_sentences():
    """Liste ordonnée des phrases de la narration avec identifiants stables (s001…)."""
    data = parse_script()
    sents = []
    for p in data['paragraphs']:
        for k, s in enumerate(split_sentences(p['text'])):
            sents.append({'id': f's{len(sents) + 1:03d}', 'text': s, 'paragraph': p['index'], 'first_in_paragraph': k == 0, 'chapter': p['chapter']})
    return data, sents


def find_sentence(sents, key: str):
    """Trouve une phrase par son début exact (ou, à défaut, par une sous-chaîne unique)."""
    k = norm_ws(key)
    hits = [s for s in sents if norm_ws(s['text']).startswith(k)]
    if not hits:
        hits = [s for s in sents if k in norm_ws(s['text'])]
    if len(hits) != 1:
        raise KeyError(f'Phrase introuvable ou ambiguë ({len(hits)}) : {key}')
    return hits[0]
