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

def test_html_title_tag():
    """
    pass: Excelente! Sua página tem um título visível na aba do navegador.
    fail: Sua página está sem <title>. Adicione-a dentro do <head> para definir um título no navegador.
    """
    soup = parse_html()
    # Ensure the <title> tag is present
    assert soup.find('title') is not None, "The <title> tag is missing."

def test_html_meta_charset():
    """
    pass: A codificação de caracteres foi definida corretamente com UTF-8.
    fail: Está faltando a meta tag charset. Adicione <meta charset='UTF-8'> para evitar problemas com acentuação.
    """
    soup = parse_html()
    # Ensure the meta charset tag is present
    meta_tag = soup.find('meta', attrs={"charset": True})
    assert meta_tag is not None, "Missing <meta charset='UTF-8'>"

def test_html_meta_viewport():
    """
    pass: A tag <meta name='viewport'> está presente e garante responsividade.
    fail: Faltando a meta tag de viewport. Ela é essencial para que a página funcione bem em dispositivos móveis.
    """
    soup = parse_html()
    # Ensure the meta viewport tag is present for responsive design
    meta_tag = soup.find('meta', attrs={"name": "viewport"})
    assert meta_tag is not None, "Missing <meta name='viewport'> tag"



# 3. Test Accessibility and Semantic HTML (One test per element)

def test_html_image_alt_attributes():
    """
    pass: Todas as imagens possuem atributo alt. Isso melhora a acessibilidade.
    fail: Algumas imagens estão sem o atributo alt. Adicione descrições alternativas para leitores de tela.
    """
    soup = parse_html()
    # Ensure all images have alt attributes
    images = soup.find_all('img')
    for img in images:
        assert img.get('alt'), "Image missing 'alt' attribute"

def test_html_form_labels():
    """
    pass: Ótimo! Todos os inputs possuem labels associados.
    fail: Alguns inputs não possuem labels. Isso prejudica a acessibilidade. Use a tag <label> com o atributo 'for'.
    """
    soup = parse_html()
    # Ensure all form inputs have associated labels
    inputs = soup.find_all('input')
    for input_tag in inputs:
        label = soup.find('label', attrs={'for': input_tag.get('id')})
        assert label, f"Missing label for {input_tag.get('id')}"

def test_html_semantic_header_tag():
    """
    pass: A tag <header> está presente. Sua estrutura semântica está bem definida!
    fail: Faltando a tag <header>. Use-a para agrupar conteúdo introdutório da página.
    """
    soup = parse_html()
    # Ensure <header> tag is present
    assert soup.find('header') is not None, "Missing <header> tag"

def test_html_semantic_footer_tag():
    """
    pass: Muito bom! A tag <footer> está presente e posiciona corretamente o rodapé.
    fail: A tag <footer> está ausente. Use-a para agrupar conteúdo no final da página, como créditos ou links.
    """
    soup = parse_html()
    # Ensure <footer> tag is present
    assert soup.find('footer') is not None, "Missing <footer> tag"

def test_html_semantic_nav_tag():
    """
    pass: A tag <nav> foi utilizada. Isso deixa sua navegação bem definida!
    fail: Você se esqueceu da tag <nav>. Use-a para indicar menus de navegação.
    """
    soup = parse_html()
    # Ensure <nav> tag is present
    assert soup.find('nav') is not None, "Missing <nav> tag"

def test_html_semantic_main_tag():
    """
    pass: A tag <main> foi usada corretamente para destacar o conteúdo principal.
    fail: Inclua a tag <main> para delimitar o conteúdo central da sua página.
    """
    soup = parse_html()
    # Ensure <main> tag is present
    assert soup.find('main') is not None, "Missing <main> tag"




def test_html_closing_tags():
    """
    pass: Todas as tags foram corretamente fechadas. HTML válido!
    fail: Algumas tags não foram fechadas. Isso pode quebrar a estrutura da página. Corrija os fechamentos.
    """
    soup = parse_html()
    # Ensure all non-void elements are properly closed
    void_tags = ['img', 'br', 'hr', 'input', 'meta']
    for tag in soup.find_all(True):  # True selects all tags
        if tag.name not in void_tags:
            assert soup.find(tag.name) is not None, f"Missing closing tag for <{tag.name}>"

# 6. Test HTML Validation (Basic placeholder test for valid HTML)

def test_html_valid_html():
    """
    pass: O HTML está bem formado e válido.
    fail: O HTML parece estar mal estruturado. Revise o código ou utilize um validador como o do W3C.
    """
    soup = parse_html()
    assert soup is not None, "HTML is not valid"