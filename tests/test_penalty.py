# place your penalty test suite here
import pytest
from bs4 import BeautifulSoup

def parse_html():
    with open('submission/index.html', 'r', encoding='utf-8') as file:
        return BeautifulSoup(file.read(), 'html.parser')

def parse_css():
    with open('submission/style.css', 'r', encoding='utf-8') as file:
        return file.read()

def parse_js():
    with open('submission/script.js', 'r', encoding='utf-8') as file:
        return file.read()


# === PENALTY TESTS (INVERTED LOGIC) ===

def test_html_use_of_br_tag():
    """
    pass: A tag <br> foi detectada. Prefira usar margens ou padding no CSS para espaçamento.
    fail: Nenhuma tag <br> foi encontrada. Ótimo! Use margens ou padding no CSS para espaçamento.
    """
    soup = parse_html()
    assert soup.find('br') is not None, "No <br> tag found (this test should pass when <br> is used)."

def test_css_inline_styles():
    """
    pass: Estilos inline encontrados. Prefira movê-los para o CSS externo.
    fail: Nenhum estilo inline foi encontrado. Seu código está bem organizado!
    """
    soup = parse_html()
    assert soup.find(attrs={"style": True}) is not None, "No inline styles found (should pass if inline styles exist)."

def test_html_overuse_of_divs():
    """
    pass: O uso de <div> está controlado. Muito bom!
    fail: Muito poucos <div> foram encontrados. Para penalidade, é necessário mais de 10 <div>.
    """
    soup = parse_html()
    divs = soup.find_all('div')
    assert len(divs) > 10, "Too few <div> tags for overuse penalty (needs > 10)."

def test_js_inline_script_tags():
    """
    pass: Nenhum <script> inline foi detectado. Ótimo trabalho!
    fail: Não encontramos <script> inline. Considere movê-lo para arquivos `.js` separados.
    """
    soup = parse_html()
    script_tags = soup.find_all('script')
    for script in script_tags:
        if not script.get('src'):
            assert True
            return
    assert False, "No inline <script> tag found."

def test_html_use_of_center_tag():
    """
    pass: A tag <center> não foi utilizada. Perfeito!
    fail: Nenhuma tag <center> foi encontrada. Para alinhamento, use `text-align: center` no CSS.
    """
    soup = parse_html()
    assert soup.find('center') is not None, "No <center> tag found."

def test_js_alert_usage():
    """
    pass: Nenhum uso de alert() encontrado. Ótimo!
    fail: Alertas `alert()` detectados. Evite usar `alert()` em seu código.
    """
    js = parse_js()
    assert "alert(" in js, "No use of alert() found in JS."

def test_js_document_write():
    """
    pass: Nenhum uso de document.write() encontrado. Excelente prática!
    fail: Detectamos uso de document.write(). Essa prática pode causar problemas na renderização.
    """
    js = parse_js()
    assert "document.write(" in js, "No use of document.write() found."

def test_html_deprecated_u_tag():
    """
    pass: A tag `<u>` não foi utilizada. Parabéns por evitar elementos ultrapassados!
    fail: A tag `<u>` foi usada. Evite-a, usando `text-decoration: underline` no CSS.
    """
    soup = parse_html()
    assert soup.find('u') is not None, "No deprecated <u> tag found."

def test_html_hardcoded_image_dimensions():
    """
    pass: Nenhuma imagem com largura ou altura fixa no HTML. Ótimo!
    fail: Encontramos dimensões fixas de `width` ou `height` no HTML. Prefira usar o CSS para essas dimensões.
    """
    soup = parse_html()
    imgs = soup.find_all('img')
    for img in imgs:
        if img.get('width') or img.get('height'):
            assert True
            return
    assert False, "No hardcoded width or height attributes found on images."

def test_css_no_important_usage():
    """
    pass: Não foi encontrado o uso de `!important` no CSS. Excelente prática!
    fail: Uso de `!important` detectado. Evite-o, pois dificulta a manutenção e pode gerar conflitos inesperados.
    """
    css_content = parse_css()
    assert "!important" in css_content, "Didn't Found !important in the CSS."

def test_html_forbidden_b_tag():
    """
    pass: Não encontramos a tag <b>. Para negrito, use `font-weight: bold` no CSS.
    fail: A tag `<b>` foi utilizada. Evite-a, utilizando o CSS para negrito.
    """
    soup = parse_html()
    assert soup.find('b') is not None, "Found forbidden <b> tag"

def test_html_forbidden_i_tag():
    """
    pass: Não encontramos a tag <i>. Para itálico, use `font-style: italic` no CSS.
    fail: A tag `<i>` foi usada. Evite-a, utilizando o CSS para itálico.
    """
    soup = parse_html()
    assert soup.find('i') is not None, "Found forbidden <i> tag"

def test_html_forbidden_font_tag():
    """
    pass: Não encontramos a tag `<font>`. Prefira usar o CSS para estilizar texto.
    fail: A tag `<font>` foi usada. Evite-a, utilizando o CSS moderno para estilo.
    """
    soup = parse_html()
    assert soup.find('font') is not None, "Found forbidden <font> tag"

def test_html_forbidden_marquee_tag():
    """
    pass: Não encontramos a tag `<marquee>`. Prefira usar animações CSS.
    fail: A tag `<marquee>` foi encontrada. Ela está obsoleta, prefira usar animações CSS.
    """
    soup = parse_html()
    assert soup.find('marquee') is not None, "Found forbidden <marquee> tag"

def test_html_forbidden_center_tag():
    """
    pass: Não encontramos a tag `<center>`. Use `text-align: center` no CSS para centralização.
    fail: A tag `<center>` foi encontrada. Use `text-align: center` ou `display: flex` no CSS para centralização.
    """
    soup = parse_html()
    assert soup.find('center') is not None, "Found forbidden <center> tag"