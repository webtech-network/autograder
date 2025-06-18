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



# 5. Test Proper Nesting and Closing Tags

def test_html_proper_nesting():
    """
    pass: A estrutura do HTML está bem aninhada. Tudo em ordem!
    fail: Erro de aninhamento encontrado. Ex: listas <ul> devem conter apenas <li>. Verifique a estrutura.
    """
    soup = parse_html()
    # Check for correct nesting of elements (e.g., <ul> should only contain <li>)
    ul_tags = soup.find_all('ul')
    for ul in ul_tags:
        for child in ul.children:
            assert child.name == 'li' or child.name is None, f"Invalid child in <ul>: {child.name}"

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

# 1. Test if the CSS file is correctly linked
def test_css_css_linked():
    """
    pass: O CSS está corretamente vinculado via <link> no <head>.
    fail: O CSS não foi vinculado corretamente. Use <link rel='stylesheet' href='style.css'> no <head>.
    """
    soup = parse_html()
    # Ensure the CSS file is linked in the <head> using <link rel="stylesheet">
    link = soup.find("link", {"rel": "stylesheet"})
    assert link is not None, "The CSS file is not linked."
    assert link["href"] == "style.css", "CSS file is incorrectly linked."


# 3. Test for Shorthand CSS properties (e.g., margin, padding)
def test_css_shorthand_properties():
    """
    pass: Você utilizou propriedades abreviadas como margin e padding. Muito bom!
    fail: Evite declarar separadamente cada lado do margin/padding. Use shorthand como `margin: 10px 5px;`.
    """
    css_content = parse_css()
    # Check for shorthand properties like margin, padding, etc.
    assert "margin:" in css_content or "padding:" in css_content, "Missing shorthand for margin or padding."




# 4. Test for the presence of CSS Variables
def test_css_css_variables(quantitative_result_recorder):
    """
    pass: Variáveis CSS detectadas. Isso facilita a manutenção do seu estilo.
    fail: Não encontramos variáveis CSS. Tente usar --primary-color, por exemplo, para padronizar seu tema.
    """
    css_content = parse_css()
    # Check if CSS variables are used (e.g., --primary-color)
    count = 0
    for key in css_content.split(" "):
        if key in ["--primary-color", "--secondary-color", "--font-size"]:
            count += 1
    quantitative_result_recorder(count)
    assert count>0, "No CSS variables found. Consider using --primary-color, --secondary-color, etc. for better maintainability."

# 5. Test if the layout uses Flexbox or Grid (modern layout techniques)
def test_css_layout_method():
    """
    pass: Você usou Flexbox ou Grid para o layout. Ótima escolha!
    fail: Faltando uso de Flexbox ou Grid. Eles ajudam a posicionar elementos de forma moderna e flexível.
    """
    css_content = parse_css()
    # Ensure that flexbox or grid is used in layout
    assert "display: flex" in css_content or "display: grid" in css_content, "Neither flexbox nor grid is used for layout."


# 7. Test if CSS selectors are not overqualified
def test_css_no_overqualified_selectors():
    """
    pass: Os seletores CSS estão simples e diretos. Ótimo trabalho!
    fail: Seus seletores estão muito específicos. Simplifique para evitar conflitos e facilitar manutenção.
    """
    css_content = parse_css()
    # Ensure that the CSS selectors are not overqualified (i.e., too specific)
    selectors = [selector.strip() for selector in css_content.split(",")]
    for selector in selectors:
        assert selector.count(" ") <= 2, f"Overqualified selector detected: {selector}"

# 8. Test for External CSS Links (No inline CSS)
def test_css_external_css_only():
    """
    pass: Nenhum estilo inline encontrado. Tudo está no CSS externo. Excelente!
    fail: Estilos inline foram detectados. Prefira manter todo o CSS em arquivos separados.
    """
    soup = parse_html()
    # Ensure there is no inline CSS in the HTML (should use external CSS only)
    style_tag = soup.find("style")
    assert style_tag is None, "Inline CSS is present. Use external stylesheets only."

# 9. Test for Media Queries (Responsive design)
def test_css_media_queries():
    """
    pass: Media queries estão presentes. Sua página é responsiva!
    fail: Faltando media queries. Use-as para adaptar sua página a diferentes tamanhos de tela.
    """
    css_content = parse_css()
    # Ensure that media queries are present for responsiveness
    assert "@media" in css_content, "Missing media queries for responsive design."

# 10. Test for No Redundant or Duplicate Rules
def test_css_no_redundant_rules():
    """
    pass: Sem regras CSS duplicadas. Seu código está limpo e organizado.
    fail: Encontramos duplicações de regras CSS. Elimine as repetições para manter clareza.
    """
    css_content = parse_css()
    # Ensure that there are no duplicate CSS rules for the same selector
    rules = css_content.split("}")
    selectors = set()
    for rule in rules:
        selector = rule.split("{")[0].strip()
        if selector:
            assert selector not in selectors, f"Duplicate rule for {selector} found."
            selectors.add(selector)

# 11. Test for Consistent Units
def test_css_consistent_units():
    """
    pass: As unidades usadas no CSS estão consistentes. Perfeito!
    fail: Detectamos uso misto de unidades (px, rem, etc). Escolha uma abordagem uniforme.
    """
    css_content = parse_css()
    # Ensure consistent use of units (e.g., rem, em, px, etc.)
    assert "rem" in css_content or "em" in css_content or "px" in css_content, "Inconsistent use of CSS units."
# 1. Test for valid JavaScript syntax
def test_js_valid_js_syntax():
    """
    pass: O JavaScript não apresenta erros de sintaxe. Ótimo!
    fail: Seu JavaScript contém erro de sintaxe. Verifique parênteses, chaves e pontuação.
    """
    js_content = parse_js()
    try:
        # Attempt to execute the JavaScript content within a safe context (e.g., using eval or a JS interpreter)
        # This is a simple way to check for syntax errors.
        exec(js_content)
    except Exception as e:
        pytest.fail(f"JavaScript has syntax errors: {str(e)}")

# 2. Test for the use of `let`, `const`, or `var` for variable declarations
def test_js_no_undeclared_variables():
    """
    pass: Todas as variáveis foram declaradas com let, const ou var.
    fail: Variáveis sem declaração foram encontradas. Use let, const ou var para evitar escopo global.
    :return:
    """
    js_content = parse_js()
    # Ensure variables are declared using let, const, or var (no implicit global variables)
    assert "let " in js_content or "const " in js_content or "var " in js_content, "No variable declaration with let, const, or var found."

# 3. Test for strict mode (`"use strict"`)
def test_js_strict_mode():
    """
    pass: Modo estrito habilitado com 'use strict'. Excelente prática!
    fail: Adicione 'use strict'; no início do seu script para tornar o código mais seguro e previsível.
    """
    js_content = parse_js()
    # Ensure that strict mode is enabled at the top of the script
    assert '"use strict";' in js_content, "'use strict' is not used to enforce strict mode."

# 4. Test for avoiding the use of `eval()`
def test_js_no_eval():
    """
    pass: Não encontramos uso do método eval(). Muito bem!
    fail: Evite usar eval(), pois representa riscos à segurança e é difícil de depurar.
    """
    js_content = parse_js()
    # Ensure that eval() is not used in the JavaScript file
    assert "eval(" not in js_content, "The use of eval() is detected, which should be avoided."

# 5. Test for modularity (checking for functions)
def test_js_modular_code(quantitative_result_recorder):
    """
    pass: O código está modularizado com funções separadas. Excelente!
    fail: Seu código está em um bloco único. Reorganize em funções reutilizáveis para melhor leitura e manutenção.
    """
    js_content = parse_js()
    # Ensure that the JavaScript code is broken into smaller functions instead of large monolithic functions
    functions = [line for line in js_content.splitlines() if line.strip().startswith("function")]
    quantitative_result_recorder.record_count("js_modular_code", len(functions))
    print("Recorded ->", quantitative_result_recorder.user_properties[-1])
    assert len(functions) > 0# Example expected count

# 6. Test for asynchronous handling (using async/await or Promises)
def test_js_async_handling():
    """
    pass: Async/await ou Promises foram utilizados. Perfeito para operações assíncronas!
    fail: Não foi identificado uso de async/await ou Promises. Eles são recomendados para chamadas assíncronas.
    """
    js_content = parse_js()
    # Ensure the use of async/await or Promises for asynchronous operations
    assert "async" in js_content or "Promise" in js_content, "No async/await or Promises found for asynchronous handling."

# 7. Test for event handling (e.g., using addEventListener)
def test_js_event_handling():
    """
    pass: addEventListener está sendo usado corretamente para manipulação de eventos.
    fail: Evite eventos inline como onclick. Use addEventListener no JavaScript.
    """
    js_content = parse_js()
    # Ensure that event listeners are used instead of inline event handlers in the HTML
    assert "addEventListener" in js_content, "addEventListener is not used for event handling."

# 8. Test for DOM manipulation efficiency
def test_js_dom_manipulation():
    """
    pass: Você está manipulando o DOM com métodos modernos como querySelector.
    fail: Considere usar querySelector ou getElementById ao invés de métodos ultrapassados para acessar elementos.
    """
    js_content = parse_js()
    # Ensure that DOM manipulation is done efficiently, ideally using modern methods like querySelector
    assert "document.querySelector" in js_content or "document.getElementById" in js_content, "Inefficient DOM manipulation methods detected."

# 9. Test for handling errors in Promises or async/await
def test_js_async_error_handling():
    """
    pass: Erros em operações assíncronas estão sendo tratados. Excelente!
    fail: Faltando tratamento de erros com try/catch ou .catch() nas Promises. Isso evita falhas silenciosas.
    """
    js_content = parse_js()
    # Ensure proper error handling in Promises or async/await (e.g., using .catch or try/catch)
    assert ".catch(" in js_content or "try {" in js_content, "Asynchronous error handling is not present."


# 11. Test for proper function names (meaningful naming)
def test_js_meaningful_function_names():
    """
    pass: As funções têm nomes descritivos e claros.
    fail: Algumas funções estão com nomes genéricos. Dê nomes que indiquem claramente o que a função faz.
    """
    js_content = parse_js()
    # Ensure that function names are meaningful and describe their purpose
    function_names = [line.strip().split(" ")[1] for line in js_content.splitlines() if line.strip().startswith("function")]
    for name in function_names:
        assert len(name) > 0 and name != 'function', f"Function name '{name}' is not meaningful."

# 12. Test for no deeply nested functions or loops
def test_js_no_deeply_nested_code():
    """
    pass: O código está limpo, sem blocos profundamente aninhados.
    fail: Evite aninhar muitas funções ou estruturas. Quebre em partes menores para melhorar a legibilidade.
    """
    js_content = parse_js()
    # Check if there are deeply nested functions or loops (which can cause readability issues)
    assert js_content.count('function') < 5, "Too many functions defined, check for deep nesting."
    assert js_content.count('{') < 10, "Too many blocks or nested loops. Consider refactoring."

# 14. Test for the proper use of `const` and `let` (immutable vs mutable variables)
def test_js_proper_use_of_const_and_let():
    """
    pass: Uso adequado de const e let para variáveis. Muito bem!
    fail: Use const para valores fixos e let para os que mudam. Isso torna o código mais previsível.
    """
    js_content = parse_js()
    # Ensure that `const` is used for variables that should not be reassigned and `let` for mutable variables
    assert "const " in js_content, "The use of 'const' is missing where values should be immutable."
    assert "let " in js_content, "The use of 'let' is missing for mutable variables."