from io import BytesIO
from zipfile import ZipFile

import pytest

from scripts.actelyo_library_pack import classify, word_text


def make_word(document):
    out = BytesIO()
    with ZipFile(out, 'w') as z:
        z.writestr('_rels/.rels', '<Relationships><Relationship Type="x/officeDocument" Target="word/document2.xml"/></Relationships>')
        z.writestr('word/document2.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + document + '</w:body></w:document>')
        z.writestr('word/vbaProject.bin', b'NOT EXECUTABLE')
    return out.getvalue()


def test_extract_keeps_split_markers_tables_and_nonstandard_main_part():
    text, markers, fields, controls, warnings = word_text(make_word(
        '<w:p><w:r><w:t>[*Da</w:t></w:r><w:r><w:t>te]</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Nom</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>[*Client]</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    ))
    assert text == '[*Date]\nNom | [*Client]'
    assert set(markers) == {'[*Date]', '[*Client]'}
    assert fields == controls == warnings == []


def test_unsupported_embedded_text_is_not_silently_lost():
    with pytest.raises(ValueError, match='altChunk'):
        word_text(make_word('<w:altChunk/>'))


def test_mergefields_replace_cached_client_facts_at_their_original_position():
    text, markers, fields, _, _ = word_text(make_word(
        '<w:p><w:r><w:t>Société : </w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText> MERGE</w:instrText></w:r>'
        '<w:r><w:instrText>FIELD "Societe.Nom" </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t>ANCIEN CLIENT</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '<w:fldSimple w:instr="MERGEFIELD Capital"><w:r><w:t>12345</w:t></w:r></w:fldSimple></w:p>'
    ))
    assert text == 'Société : {{WORD:Societe.Nom}}{{WORD:Capital}}'
    assert set(markers) == {'{{WORD:Societe.Nom}}', '{{WORD:Capital}}'}
    assert fields


def test_title_classification_does_not_confuse_procedural_constitution_with_company():
    assert classify("Conclusions d'inconstitutionnalité") == 'contentieux-judiciaire'
    assert classify("Requête conjointe") == 'contentieux-judiciaire'
    assert classify("Rapport d'expertise") == 'contentieux-judiciaire'
    assert classify('Statuts SARL') == 'societes'
    assert classify("Conclusions prud'homales") == 'social'
    assert classify('Exception devant la juridiction saisie') == 'contentieux-judiciaire'
    assert classify('Requête en adoption simple') == 'patrimonial-famille'
