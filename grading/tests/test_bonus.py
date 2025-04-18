
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


# === BONUS TESTS ===

# --- HTML BONUS TESTS ---

def test_html_favicon_link():
    """
    pass: Você adicionou um favicon com sucesso! Sua página está mais profissional.
    fail: Faltando favicon. Adicione um `<link rel='icon'>` dentro do `<head>` para exibir o ícone na aba do navegador.
    """
    soup = parse_html()
    assert soup.find('link', rel='icon') is not None, "Favicon is not included in the <head>."

def test_html_section_ids_are_meaningful():
    """
    pass: Os IDs das seções são significativos e bem nomeados. Excelente uso de kebab-case!
    fail: Alguns IDs de seção estão genéricos ou mal formatados. Use nomes descritivos com hífens (kebab-case), como `minha-secao`.
    """
    soup = parse_html()
    sections = soup.find_all('section')
    for section in sections:
        sid = section.get('id')
        assert sid is not None and '-' in sid, "Section ID is missing or not meaningful (use kebab-case)."

def test_html_article_or_aside_used():
    """
    pass: Você utilizou <article> ou <aside>, melhorando a semântica da sua página.
    fail: Nenhum <article> ou <aside> foi encontrado. Considere usar essas tags para estruturar conteúdos relacionados ou independentes.
    """
    soup = parse_html()
    assert soup.find('article') or soup.find('aside'), "No <article> or <aside> tags found."


# --- CSS BONUS TESTS ---

def test_css_dark_mode_support():
    """
    pass: Modo escuro detectado! Sua página se adapta às preferências do usuário.
    fail: Não encontramos suporte a modo escuro. Considere usar `@media (prefers-color-scheme: dark)` para atender melhor os usuários.
    """
    css = parse_css()
    assert '@media (prefers-color-scheme: dark)' in css, "No dark mode support detected."

def test_css_custom_font_imported():
    """
    pass: Uma fonte personalizada foi importada com sucesso. Sua identidade visual está mais marcante!
    fail: Você ainda não importou nenhuma fonte personalizada. Experimente usar o Google Fonts para trazer mais estilo ao texto.
    """
    css = parse_css()
    assert '@import url(' in css or 'fonts.googleapis.com' in css, "Custom font not imported."

def test_css_css_animation():
    """
    pass: Ótimo uso de animações com CSS! Isso deixa a interface mais viva.
    fail: Nenhuma animação CSS detectada. Considere adicionar efeitos com `@keyframes` ou `animation` para enriquecer a experiência do usuário.
    """
    css = parse_css()
    assert '@keyframes' in css or 'animation:' in css, "No CSS animation detected."

def test_css_responsive_typography():
    """
    pass: Sua tipografia é responsiva! Uso de `clamp()`, `vw` ou `rem` aprovado.
    fail: A tipografia parece fixa. Utilize `rem`, `vw` ou `clamp()` para tornar o texto adaptável a diferentes telas.
    """
    css = parse_css()
    assert 'clamp(' in css or 'vw' in css or 'rem' in css, "Responsive typography not found (use clamp, rem, vw, etc.)."


# --- JS BONUS TESTS ---

def test_js_js_uses_template_literals():
    """
    pass: Você utilizou template literals no JavaScript. Muito bem!
    fail: Template literals (`${}` dentro de crase) deixam o código mais limpo. Considere adotá-los para montar strings dinamicamente.
    """
    js = parse_js()
    assert '`' in js and '${' in js, "No usage of template literals found in JavaScript."

def test_js_local_or_session_storage():
    """
    pass: Você utilizou `localStorage` ou `sessionStorage` para persistir dados no navegador. Excelente!
    fail: Considere usar `localStorage` ou `sessionStorage` para guardar preferências do usuário ou dados temporários.
    """
    js = parse_js()
    assert 'localStorage.' in js or 'sessionStorage.' in js, "No use of localStorage or sessionStorage."

def test_js_interaction_feedback():
    """
    pass: Comportamentos interativos detectados! O usuário recebe retorno ao interagir.
    fail: Sua página ainda não oferece feedback visual nas interações. Tente usar `classList.add`, `innerHTML` ou `toggle` para isso.
    """
    js = parse_js()
    keywords = ['classList.add', 'innerHTML', 'textContent', 'disabled', 'toggle']
    assert any(k in js for k in keywords), "No dynamic feedback behavior found on user interaction."

def test_html_form_validation_logic():
    """
    pass: Lógica de validação detectada! Os formulários estão mais robustos.
    fail: Considere implementar validações nos formulários usando `.checkValidity()` ou expressões regulares.
    """
    js = parse_js()
    assert 'checkValidity' in js or 'regex' in js or '.test(' in js, "No form validation logic found."

def test_js_modular_code_structure():
    """
    pass: Seu código está estruturado em módulos ES6 com `import` e `export`. Excelente!
    fail: Modularize seu JavaScript com `export` e `import` para manter o projeto organizado e escalável.
    """
    js = parse_js()
    assert 'export ' in js or 'import ' in js, "JavaScript modular code structure (ES Modules) not detected."

# 13. Test for proper use of array methods (e.g., map, filter, reduce)
def test_js_array_methods():
    """
    pass: Métodos como `map`, `filter` ou `reduce` foram usados com sucesso!
    fail: Evite `for` e `while` para percorrer arrays. Tente usar métodos modernos como `map`, `filter` ou `reduce`.
    """
    js_content = parse_js()
    # Ensure that array methods like map, filter, reduce are used instead of traditional loops
    assert "map(" in js_content or "filter(" in js_content or "reduce(" in js_content, "Array methods like map, filter, or reduce are not used."

# 10. Test for preventing memory leaks
def test_js_memory_leaks():
    """
    pass: Muito bem! Sua aplicação cuida de possíveis vazamentos de memória com `removeEventListener`, `clearInterval` ou `clearTimeout`.
    fail: Detectamos ausência de tratamento para eventos ou timers. Lembre-se de usar `removeEventListener` ou `clearInterval` para evitar vazamentos.
    """
    js_content = parse_js()
    # Ensure that event listeners or intervals are properly cleaned up to avoid memory leaks
    assert ".removeEventListener" in js_content or "clearInterval" in js_content or "clearTimeout" in js_content, "Memory leaks may occur due to unremoved event listeners or intervals."

# 6. Test for Minification
def test_css_css_minification():
    """
    pass: O CSS está minificado. Seu código está limpo e otimizado!
    fail: O CSS contém quebras de linha ou espaços desnecessários. Considere minificar para carregar mais rápido.
    """
    css_content = parse_css()
    # Ensure that the CSS is minified (no extra spaces or line breaks)
    assert css_content == css_content.replace(" ", "").replace("", ""), "CSS is not minified."

def test_html_open_graph_description_tag():
    """
    pass: Sua página tem uma descrição Open Graph. Isso melhora a aparência dos links nas redes sociais.
    fail: Está faltando a meta tag Open Graph de descrição. Adicione `<meta property='og:description'>` no <head>.
    """
    soup = parse_html()
    # Ensure Open Graph meta description tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:description"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:description'> tag"

def test_html_open_graph_title_tag():
    """
    pass: Open Graph título presente! Sua página será bem apresentada ao ser compartilhada.
    fail: Adicione `<meta property='og:title'>` para definir um título ao compartilhar sua página em redes sociais.
    """
    soup = parse_html()
    # Ensure Open Graph meta title tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:title"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:title'> tag"

def test_html_meta_description():
    """
    pass: A meta descrição foi definida. Isso ajuda sua página a aparecer melhor em buscadores.
    fail: Inclua a tag `<meta name='description'>` com um resumo da sua página para melhorar o SEO.
    """
    soup = parse_html()
    # Ensure the meta description tag is present
    meta_tag = soup.find('meta', attrs={"name": "description"})
    assert meta_tag is not None, "Missing <meta name='description'> tag"
