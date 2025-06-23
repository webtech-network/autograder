import pytest
from conftest import parse_html, parse_css, parse_js
'''
TEST SUITE FOR HTML PAGE
'''

def test_html_doctype():
    """
    pass: Perfeito! A declaração <!DOCTYPE html> está presente no início do documento.
    fail: Seu HTML está sem a declaração <!DOCTYPE html>. Adicione-a no topo do arquivo para garantir compatibilidade com navegadores.
    """

    with open('submission/index.html', 'r', encoding='utf-8') as file:
        content = file.read().lower()
    assert '<!doctype html>' in content, "DOCTYPE declaration not found"


def test_html_quantitative_div_tags(quantitative_result_recorder):
    """
    pass: Você usou <div> de forma adequada. Ótimo trabalho!
    fail: Muitos <div> foram encontrados. Use-os com moderação, evitando mais de 10 para não poluir o HTML.
    """
    soup = parse_html()
    divs = soup.find_all('div')
    actual_count = len(divs)
    quantitative_result_recorder(actual_count)
    assert actual_count > 0 , f"Too many <div> tags found: {actual_count} (should be <= 10)"
def test_html_html_tag():
    """
    pass: A tag <html> está corretamente presente, iniciando o documento HTML.
    fail: O documento HTML está sem a tag <html>. Adicione-a para garantir a estrutura correta.
    """

    soup = parse_html()
    # Ensure the <html> tag is present
    assert soup.find('html') is not None, "The <html> tag is missing."

def test_html_head_tag():
    """
    pass: A tag <head> foi encontrada. Ótimo, é nela que vão os metadados e links de estilo.
    fail: A tag <head> está ausente. Certifique-se de incluí-la com título, links de CSS, etc.
    """
    soup = parse_html()
    # Ensure the <head> tag is present
    assert soup.find('head') is not None, "The <head> tag is missing."

def test_html_quantitative_section_tags(quantitative_result_recorder):
    """
    pass: Você usou <section> de forma adequada. Muito bom!
    fail: Muitos <section> foram encontrados. Use-os com moderação, evitando mais de 10 para não poluir o HTML.
    """
    soup = parse_html()
    sections = soup.find_all('section')
    actual_count = len(sections)
    quantitative_result_recorder(actual_count)
    assert actual_count > 0, f"Too many <section> tags found: {actual_count})"

def test_html_body_tag():
    """
    pass: A tag <body> está presente e pronta para exibir seu conteúdo.
    fail: A tag <body> está faltando. Toda a parte visível da página deve estar dentro dela.
    """
    soup = parse_html()
    # Ensure the <body> tag is present
    assert soup.find('body') is not None, "The <body> tag is missing."

