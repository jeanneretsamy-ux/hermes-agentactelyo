"""Build a private, portable act library from user-selected ZIP exports.

Only OOXML is read; Word, macros and external relationships are never executed.
No source content belongs in the repository. Output must be outside the checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LIMIT = 30_000_000


def xml_part(z, name):
    info = z.getinfo(name)
    if info.file_size > LIMIT:
        raise ValueError("Partie XML trop volumineuse")
    raw = z.read(info)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("Déclarations XML non prises en charge")
    return ET.fromstring(raw)


def word_text(raw):
    with ZipFile(BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist()) > LIMIT:
            raise ValueError("Document décompressé trop volumineux")
        relationships = xml_part(z, "_rels/.rels")
        main = next(r for r in relationships if r.attrib.get("Type", "").endswith("/officeDocument"))
        if main.attrib.get("TargetMode") == "External":
            raise ValueError("Document principal externe")
        root = xml_part(z, main.attrib["Target"].lstrip("/"))
        warnings = []
        if root.find(f".//{W}altChunk") is not None:
            raise ValueError("Contenu incorporé altChunk : conversion manuelle requise")
        if root.find(f".//{W}del") is not None or root.find(f".//{W}ins") is not None:
            warnings.append("Révisions présentes ; texte courant extrait, original conservé")
        fields = [node.text or "" for node in root.iter(f"{W}instrText")]
        fields += [node.get(f"{W}instr", "") for node in root.iter(f"{W}fldSimple")]
        controls = [node.get(f"{W}val", "") for node in root.iter(f"{W}tag")]

        def field_marker(code):
            match = re.match(r'\s*MERGEFIELD\s+(?:"([^"]+)"|([^\s\\]+))', code, re.I)
            if not match:
                raise ValueError('Champ Word non pris en charge : original à traiter manuellement')
            return '{{WORD:' + (match[1] or match[2]) + '}}'

        def paragraph_text(paragraph):
            output, stack = [], []

            def visit(node):
                if node.tag == f'{W}fldSimple':
                    output.append(field_marker(node.get(f'{W}instr', '')))
                    return
                if node.tag == f'{W}fldChar':
                    kind = node.get(f'{W}fldCharType')
                    if kind == 'begin':
                        if stack:
                            raise ValueError('Champs Word imbriqués : contrôle manuel requis')
                        stack.append({'code': '', 'emitted': False})
                    elif kind == 'separate' and stack:
                        output.append(field_marker(stack[-1]['code']))
                        stack[-1]['emitted'] = True
                    elif kind == 'end' and stack:
                        current = stack.pop()
                        if not current['emitted']:
                            output.append(field_marker(current['code']))
                elif node.tag == f'{W}instrText' and stack:
                    stack[-1]['code'] += node.text or ''
                elif not stack and node.tag in {f'{W}t', f'{W}tab', f'{W}br'}:
                    output.append((node.text or '') if node.tag == f'{W}t' else '\t' if node.tag == f'{W}tab' else '\n')
                for child in node:
                    visit(child)

            visit(paragraph)
            if stack:
                raise ValueError('Champ Word traversant plusieurs paragraphes : contrôle manuel requis')
            return ''.join(output)

        def blocks(node):
            if node.tag == f"{W}p":
                return [paragraph_text(node)]
            if node.tag == f"{W}tr":
                return [' | '.join('\n'.join(blocks(c)) for c in node if c.tag == f"{W}tc")]
            return [text for child in node for text in blocks(child)]

        body = '\n'.join(blocks(root)).strip()
        # Footnotes, headers and footers remain explicit reference sections.
        seen = {body}
        for name in sorted(z.namelist()):
            if re.fullmatch(r'word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml', name):
                text = '\n'.join(blocks(xml_part(z, name))).strip()
                if text and text not in seen:
                    body += f'\n\n--- Annexe source : {name} ---\n{text}'
                    seen.add(text)
        if fields or controls:
            warnings.append("MERGEFIELD convertis en {{WORD:nom}} ; codes originaux conservés, aucune fusion exécutée")
        if not body or len(body) > 190_000:
            raise ValueError("Texte vide ou trop long pour une entrée de bibliothèque")
        markers = sorted(set(re.findall(r'\[(?:\*|[^\[\]])[^\[\]]{0,1000}\]|\{\{WORD:[^{}]+\}\}', body)))
        return body, markers, fields, controls, warnings


def classify(title):
    """Conservative title-based filing, explicitly reviewable in the manifest."""
    name = ''.join(c for c in unicodedata.normalize('NFKD', title.casefold()) if not unicodedata.combining(c))
    rules = [
        ('social', ('prud\'hom', 'prud’hom', 'employeur', 'salarie', 'contrat de travail', 'defenseur syndical')),
        ('agricole', ('baux ruraux', 'bail rural', 'fermage')),
        ('societes', ('statuts', 'sarl', 'sas ', 'constitution de la societe', 'participer a la constitution', 'apport', 'gerant', 'capital', 'siege social', 'pme', 'conjoint commun', 'annonce legale', 'rcs', "chef d'entreprise", '199 terdecies')),
        ('recouvrement', ('injonction de payer', 'saisie-attribution', 'saisie conservatoire', 'saisie immobiliere', 'recouvrement', 'commandement de payer')),
        ('immobilier', ('bailleur', 'preneur', 'copropriete', 'bail ')),
        ('patrimonial-famille', ('divorce', 'heritier', 'successoral', 'affaires familiales', 'paternite', 'maternite', 'filiation', 'enfant', 'adoption', 'autorite parentale', "possession d'etat", 'separation de corps', 'subsides', 'epoux')),
        ('commercial', ('tribunal de commerce', 'activites economiques')),
    ]
    for domain, terms in rules:
        if any(re.search(r'\b' + re.escape(term), name) for term in terms):
            return domain
    return 'contentieux-judiciaire'


def build(archives, destination):
    destination = Path(destination).resolve()
    checkout = Path(__file__).resolve().parents[1]
    if destination.is_relative_to(checkout):
        raise ValueError("Conserver les documents privés hors du dépôt")
    destination.mkdir(parents=True, exist_ok=True)
    entries, originals, errors = {}, {}, []
    occurrences = 0
    for archive in archives:
        print(f"Lecture : {archive.name}", flush=True)
        with ZipFile(archive) as source:
            for item in source.infolist():
                if item.is_dir() or Path(item.filename).suffix.lower() not in {'.docx', '.docm', '.dotx', '.dotm'}:
                    continue
                occurrences += 1
                try:
                    if item.file_size > LIMIT:
                        raise ValueError("Document source trop volumineux")
                    raw = source.read(item)
                    sha = hashlib.sha256(raw).hexdigest()
                    body, markers, fields, controls, warnings = word_text(raw)
                    title = Path(item.filename).stem
                    # Deduplicate only identical extracted content + fields, never just filenames.
                    key = hashlib.sha256(json.dumps([body, fields, controls], ensure_ascii=False).encode()).hexdigest()
                    provenance = {'archive': archive.name, 'member': item.filename, 'sha256': sha}
                    originals.setdefault(sha, (Path(item.filename).suffix.lower(), raw))
                    if key in entries:
                        entries[key]['sources'].append(provenance)
                        continue
                    domain = classify(title)
                    entries[key] = {
                        'title': title, 'domain': domain, 'act_type': title[:100],
                        'body': body, 'markers': markers, 'word_fields': fields, 'content_controls': controls,
                        'review_required': True, 'classification': 'titre — à vérifier',
                        'warnings': warnings, 'sources': [provenance], 'content_sha256': key,
                    }
                except Exception as error:
                    errors.append({'archive': archive.name, 'member': item.filename, 'error': str(error)})
    package = {'format': 'actelyo-private-library-v1', 'entries': list(entries.values()), 'errors': errors}
    target = destination / 'bibliotheque-actelyo.json'
    target.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding='utf-8')
    counts = Counter(entry['domain'] for entry in entries.values())
    summary = {'archives': len(archives), 'documents': occurrences, 'entries': len(entries),
               'duplicates': occurrences - len(errors) - len(entries), 'errors': len(errors),
               'domains': dict(counts), 'entries_with_markers': sum(bool(e['markers']) for e in entries.values())}
    (destination / 'inventaire.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    readme = """BIBLIOTHÈQUE PRIVÉE ACTELYO

Dans le nouveau Harness : Cabinet juridique > domaine > espace > Bibliothèque et rédaction.
Choisir « Importer une bibliothèque privée », sélectionner bibliotheque-actelyo.json, vérifier
la sélection du domaine puis confirmer l'import. Répéter pour chaque domaine voulu.
Le classement est proposé d'après les titres et doit être vérifié.

Les sources sont des références À ADAPTER, non des modèles anonymisés ni validés à jour.
Elles peuvent contenir des faits déjà remplis. Ne jamais les transférer à un autre client.
Les balises textuelles sont préservées. Les MERGEFIELD deviennent {{WORD:nom}} à leur emplacement.
Leurs valeurs préremplies en cache ne sont pas reprises. La correspondance avec les données du
dossier reste à valider ; aucun calcul, aucune macro ni fusion Word ne sont exécutés.
Le texte importé ne reproduit pas la mise en page Word ; les originaux restent dans sources/.
Les noms d'origine et SHA-256 sont dans le JSON. Doublons textuels regroupés, provenance conservée.
Aucun de ces documents ne doit être ajouté au dépôt public ou au build redistribué.
"""
    (destination / 'LIRE-MOI.txt').write_text(readme, encoding='utf-8')
    output = destination / 'Bibliotheques-privees-Actelyo.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        for path in (target, destination / 'inventaire.json', destination / 'LIRE-MOI.txt'):
            z.write(path, path.name)
        for sha, (suffix, raw) in originals.items():
            z.writestr(f'sources/{sha}{suffix}', raw)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (destination / 'Bibliotheques-privees-Actelyo.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--pattern', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selected = sorted(args.source_directory.glob(args.pattern))
    if not selected:
        parser.error('Aucune archive trouvée')
    build(selected, args.output)
