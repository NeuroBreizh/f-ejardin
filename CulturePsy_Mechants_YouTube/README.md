# Culture Psy — « Pourquoi défend-on les méchants ? » · essai vidéo YouTube

Projet Remotion du master horizontal 16:9 (1920 × 1080, 30 i/s), narration française, environ 12 à 14 minutes selon le débit de la voix.
Le montage suit la voix. Chaque plan, titre, son et silence est accroché à une **phrase** du script v3 et, si besoin, à un **mot**. Aucun n'est placé à une seconde fixe.

## Ce dont le projet a besoin

| Dossier | Contenu | État |
|---|---|---|
| `public/rushes/` | les 12 captures `01_…mp4` à `12_…mp4` du dossier EXTRAITS (noms identiques) et, si elle existe, la capture Gretchen | **à déposer** |
| `public/planches/` | les 6 PNG 1920 × 1080 de `PLANCHES_16x9` : `identification.png`, `disposition_affective.png`, `justifications.png`, `deux_consignes.png`, `attributions.png`, `curiosite.png` | **à déposer** (renommer si besoin) |
| `public/audio/` | ta voix (wav, flac ou m4a) et, si tu en as une, une musique dont tu détiens les droits de publication | facultatif |
| `script/Culture_Psy_Mechants_YouTube_Voix_off_v3.txt` | script de référence (seul texte lu et sous-titré : hors crochets) | présent |
| `public/visuels/` | images du laboratoire (reconstitution) reprises de la version verticale | présent |
| `public/sfx/` | bruit sourd de l'explosion et grondements, filtrés en passe-bas à partir des captures | présent |

Tant qu'une capture manque, le rendu la remplace par une **mire de calage** grise, avec le numéro d'image et la bande de sous-titres. `tools/audit_montage.py --livraison` refuse toute livraison qui contient encore une mire.

## Installer

```bash
npm install
pip install numpy pillow          # outils de contrôle
pip install stable-ts             # alignement forcé de la voix (ou : pip install whisperx)
```

## 1. Déposer les captures

```bash
cp /chemin/vers/EXTRAITS/*.mp4 public/rushes/
python3 tools/inspect_captures.py --planches
```

Ce script effectue les opérations suivantes :
- mesure la zone active de chaque capture avec `cropdetect` ;
- détecte les coupes d'origine et les images où des sous-titres sont incrustés ;
- crée des proxys tout-intra (`-g 1`) dans `public/proxies/` ;
- produit des planches contact numérotées dans `controle/captures/`.

Les plages d'images propres, sans sous-titre, interface, filigrane ni plan voisin, se valident à l'œil sur ces planches. Elles vont dans le champ `plages_propres` de `src/data/sources.json`.

## 2. Déposer ta voix et relancer l'alignement

1. Dépose le fichier dans `public/audio/`, par exemple `public/audio/voix.wav`.
2. Dans `src/data/config.json`, indique `"voix": "audio/voix.wav"`.
3. Lance la reconstruction :

```bash
sh tools/build_all.sh
```

`build_all.sh` enchaîne quatre étapes :
1. `tools/align_voice.py`
   - aligne le script v3 mot à mot sur ta voix (stable-ts en français) ;
   - détecte les respirations (`silencedetect` à −38 dB, au moins 120 ms) ;
   - coupe la voix uniquement là où le montage exige un silence plus long que ta respiration : temps de réponse, test de 2 × 3 s, seconde de silence après « Qui a levé la main ? », cartes de chapitre. Chaque coupe tombe au milieu d'une respiration, jamais dans un mot.
2. `tools/build_text.py` recalcule les phrases et les mots minutés, le SRT, les chapitres YouTube et la description.
3. `tools/resolve_montage.py` replace tous les plans sur les nouveaux temps et réécrit `livrables/LISTE_DES_PLANS.md`.
4. Les audits de texte et de montage s'exécutent.

Les silences imposés et leur raison sont dans `src/data/pauses.json`. En version de calage, ce fichier règle aussi le débit (150 mots/min, hors silences).

## 3. Rendus d'essai, puis export

```bash
node tools/render.mjs --chapitre=1          # essai d'un chapitre → controle/essais/
node tools/render.mjs --frames=0-900        # essai d'une plage d'images
npx remotion studio                         # aperçu et lecture image par image

node tools/render.mjs                       # film entier → livrables/…_brut.mp4
python3 tools/finalize.py livrables/CulturePsy_Mechants_YouTube_master_brut.mp4
```

`finalize.py` traite l'audio et le conteneur :
- **Avec ta voix :** il amène le mix à −14 LUFS intégrés avec une crête vraie à −1 dBTP au plus (loudnorm en deux passes).
- **Dans tous les cas :** il encode l'audio en AAC 48 kHz et ajoute `+faststart`.
- **Nom du fichier :**
  - `CulturePsy_Mechants_YouTube_master.mp4` avec ta voix ;
  - `CulturePsy_Mechants_YouTube_VERSION_DE_CALAGE.mp4` sans elle. Cette version garde les sous-titres incrustés et le bandeau.

## 4. Auto-audit (§7 du brief)

```bash
python3 tools/audit_text.py                       # 7.1 diff narration ↔ SRT, normes SRT, textes à l'écran
python3 tools/audit_montage.py --livraison        # 7.3 durées ≤ 6,0 s, pas de scène contiguë, 11 captures, ×1,8 max pour 05/06/07, test identique
python3 tools/audit_final.py livrables/<film>.mp4 --planches   # 7.2, 7.4 à 7.7 : planches de plans et de coupes, lecture, son, fichier, couleurs
```

## Où modifier quoi

| Fichier | Rôle |
|---|---|
| `src/data/montage.json` | **le montage** : plans successifs (`visuel`), incrustations (crédits, questions, étiquettes), sons, enveloppe de musique |
| `src/data/pauses.json` | débit de calage et silences imposés |
| `src/data/sources.json` | captures : dimensions, zone active, bande de sous-titres, plages propres, coupes, agrandissement maximal |
| `src/data/config.json` | voix, musique, sous-titres incrustés (par défaut : seulement en calage) |
| `src/Film.tsx`, `src/components/` | rendu : plans, cadres intégrés, compositions, carte du « ça », sous-titres, bandeaux |
| `tools/` | chaîne texte, voix, résolution, rendu et audits |

### Ancres (dans `montage.json`)

| Ancre | Moment |
|---|---|
| `"Garde ta réponse"` | début de la phrase qui commence ainsi |
| `"Garde ta réponse\|réponse"` | début du mot « réponse » (`ça#2` désigne la 2ᵉ occurrence) |
| `"…\|réponse>"` | fin de ce mot |
| `"…\|>"` | fin de la phrase |
| `"…\|réponse\|+0.3"` | même point, avec un décalage en secondes |
| `"t:2.4"` | temps absolu |
| `"chap:2"` | début du 3ᵉ chapitre (le premier vaut 0) |
| `"parole_fin\|+1.0"` | une seconde après le dernier mot |

Un plan court jusqu'au plan suivant. Les images source se donnent en numéro d'image (30 i/s) ou en `"mm:ss.cc"`.

### Plans

| Champ | Effet |
|---|---|
| `layout: "plein"` | plein cadre ; le recadrage est calculé au rapport 16:9 |
| `layout: "cadre"` | cadre intégré sur fond flou ; agrandissement plafonné à 1,8 pour 05, 06 et 07 |
| `fit: "contain"` | garde toute la zone active, par exemple les deux sièges de l'opéra |
| `eviter_bas: true` | recadre au-dessus de la bande de sous-titres incrustés |
| `freeze: true` | image figée |
| `zoom` | légère poussée |
| `reprise: true` | retour volontaire sur un passage déjà vu, pour une lecture nouvelle |

Les compositions (`type: "compose"`) superposent des calques :
- `clip` : extrait vidéo ;
- `texte` : styles `question`, `citation` (paroles prêtées au spectateur, en italique entre « »), `mot`, `liste`, `etiquette`, `credit` ;
- `image` ;
- `trait` ;
- `cadre` ;
- `ca` : « Il fait ça pour sa famille » et ses compléments.

## Musique

`config.json → "musique": null` : pas de musique. L'enveloppe est déjà écrite (`montage.json → musique.enveloppe`) :
- un motif discret ;
- coupé pendant le test, du geste jusqu'à la question ;
- coupé avant la dernière question.

Dépose une piste dont les droits de publication sont adaptés, indique-la, et relance le rendu.

## Typographie

La typographie française est automatique :
- espace fine insécable avant `? ! : ;` et à l'intérieur des « » ;
- apostrophes typographiques.

Elle s'applique aux sous-titres, au SRT et à tous les textes du film.

Polices :
- Inter (titres, étiquettes, crédits) ;
- Newsreader (questions, paroles prêtées au spectateur).

Les deux sont sous licence SIL OFL (voir `public/fonts/`).
