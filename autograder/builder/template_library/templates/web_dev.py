import re
from bs4 import BeautifulSoup

from autograder.builder.template_library.templates.template import Template
from autograder.core.models.test_result import TestResult


# Assuming these classes are in their respective, importable files
# from autograder.builder.template_library.templates.template import Template
# from autograder.core.models.test_result import TestResult

class WebDevLibrary(Template):
    # ... (constructor and other unchanged methods)


    @staticmethod
    def has_tag(submission_files, tag: str, required_count: int) -> TestResult:
        """
        Verifies that a specific HTML tag appears a minimum number of times in `index.html`.
        The score is calculated as the ratio of found tags to required tags, capped at 100%.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"Foram encontradas {found_count} de {required_count} tags `<{tag}>`  necessárias."
        return TestResult("has_tag", score, report, parameters={"tag": tag, "required_count": required_count})

    @staticmethod
    def has_forbidden_tag(submission_files, tag: str) -> TestResult:
        """
        Checks for the presence of a forbidden HTML tag in `index.html`.
        The score is 0 if the tag is found, otherwise 100.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(tag) is not None
        score = 0 if found else 100
        report = (
            f"A tag `<{tag}>` foi encontrada e é proibida." if found
            else f"A tag `<{tag}>` não foi encontrada, ótimo!"
        )
        return TestResult("has_forbidden_tag", score, report, parameters={"tag": tag})

    @staticmethod
    def has_attribute(submission_files, attribute: str, required_count: int) -> TestResult:
        """
        Checks if a specific HTML attribute is present on any tag, a minimum number of times.
        The score is proportional to the count found versus the count required.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(attrs={attribute: True}))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = f"O atributo `{attribute}` foi encontrado {found_count} vez(es) de {required_count} necessárias."
        return TestResult("has_attribute", score, report, parameters={"attribute": attribute, "required_count": required_count})


    @staticmethod
    def has_structure(submission_files, tag_name: str) -> TestResult:
        """
        A convenience method to check for the existence of at least one instance of a specific HTML tag.
        This wraps `has_tag` with a required count of 1, useful for verifying basic document structure.
        """
        result = WebDevLibrary.has_tag(submission_files, tag_name, 1)
        result.parameters = {"tag_name": tag_name} # Override parameters for clarity
        return result

    @staticmethod
    def check_no_unclosed_tags(submission_files) -> TestResult:
        """
        Performs a basic check for a well-formed HTML document by verifying that
        BeautifulSoup can successfully parse the `<html>`, `<head>`, and `<body>` tags.
        This serves as a proxy for detecting major structural issues.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        is_well_formed = soup.html and soup.body and soup.head
        score = 100 if is_well_formed else 20
        report = (
            "Você possui uma boa estrutura HTML sem tags abertas." if is_well_formed
            else "Foram identificadas tags HTML abertas ou estrutura incorreta no seu arquivo."
        )
        return TestResult("check_no_unclosed_tags", score, report)

    @staticmethod
    def check_no_inline_styles(submission_files) -> TestResult:
        """
        Ensures that no inline styles are used in `index.html`. It searches for any
        tag with a `style` attribute and gives a score of 0 if any are found.
        """
        html_content = submission_files.get("index.html", "")
        found_count = len(BeautifulSoup(html_content, 'html.parser').find_all(style=True))
        score = 0 if found_count > 0 else 100
        report = (
            f"Foi encontrado {found_count} inline styles (`style='...'`). Move all style rules to your `.css` file." if found_count > 0
            else "Excellent! No inline styles found."
        )
        return TestResult("check_no_inline_styles", score, report)


    @staticmethod
    def uses_semantic_tags(submission_files) -> TestResult:
        """
        Checks if the HTML uses at least one common semantic tag to encourage
        proper document structure over generic `<div>` elements. It looks for
        `<article>`, `<section>`, `<nav>`, `<aside>`, or `<figure>`.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find(("article", "section", "nav", "aside", "figure")) is not None
        score = 100 if found else 40
        report = (
            "Utilizou tags semânticas" if found
            else "Não usou nenhuma tag do tipo (`<article>`, `<section>`, `<nav>`) na estrutura do HTML."
        )
        return TestResult("uses_semantic_tags", score, report)

    @staticmethod
    def check_css_linked(submission_files) -> TestResult:
        """
        Verifies that an external CSS stylesheet is linked in `index.html`.
        It specifically looks for a `<link>` tag with the `rel='stylesheet'` attribute.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", rel="stylesheet") is not None
        score = 100 if found else 0
        report = (
            "Arquivo CSS está corretamente linkado com o HTML" if found
            else "Não foi encontrada a tag `<link rel='stylesheet'>` no seu HTML."
        )
        return TestResult("check_css_linked", score, report)

    @staticmethod
    def css_uses_property(submission_files, prop: str, value: str) -> TestResult:
        """
        Checks if a specific CSS property and value pair exists in `style.css`.
        It uses a case-insensitive regular expression for a flexible match.
        """
        css_content = submission_files.get("style.css", "")
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        report = (
            f"A propriedade`{prop}: {value};` foi encontrada." if found
            else f"A propriedade CSS `{prop}: {value};` não foi encontrada."
        )
        return TestResult("css_uses_property", score, report, parameters={"prop": prop, "value": value})

    @staticmethod
    def count_over_usage(submission_files, text: str, max_allowed: int) -> TestResult:
        """
        Penalizes the use of a specific text string in `style.css` if it exceeds a
        maximum allowed count. Useful for disallowing `!important` or specific selectors.
        """
        css_content = submission_files.get("style.css", "")
        found_count = css_content.count(text)
        score = 100 if found_count >= max_allowed else 0
        report = (
            f"Uso exagerado de `{text}` detectado {found_count} vezes (máximo permitido: {max_allowed})." if score > 0
            else f"Uso exagerado de `{text}` não detectado."
        )
        return TestResult("count_usage", score, report, parameters={"text": text, "max_allowed": max_allowed})

    @staticmethod
    def js_uses_feature(submission_files, feature: str) -> TestResult:
        """
        Performs a simple string search to check if a specific feature (e.g., a
        function name, keyword like 'async') is present in `script.js`.
        """
        js_content = submission_files.get("script.js", "")
        found = feature in js_content
        score = 100 if found else 0
        report = (
            f"The feature `{feature}` was implemented." if found
            else f"The JavaScript feature `{feature}` was not found in your code."
        )
        return TestResult("js_uses_feature", score, report, parameters={"feature": feature})

    @staticmethod
    def uses_forbidden_method(submission_files, method: str) -> TestResult:
        """
        Checks for and penalizes the use of a forbidden method or keyword in `script.js`.
        The score is 0 if the forbidden string is found.
        """
        js_content = submission_files.get("script.js", "")
        found = method in js_content
        score = 0 if found else 100  # Corrected logic: score is 0 if found
        report = (
            f"Penalty: Forbidden method `{method}()` detected." if found
            else f"Great! Forbidden method `{method}()` was not used."
        )
        return TestResult("uses_forbidden_method", score, report, parameters={"method": method})

    @staticmethod
    def count_global_vars(submission_files, max_allowed: int) -> TestResult:
        """
        Counts the number of variables declared in the global scope of `script.js`.
        It penalizes the submission if the count exceeds the maximum allowed.
        """
        js_content = submission_files.get("script.js", "")
        # This regex looks for var, let, or const at the beginning of a line
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        report = (
            f"Attention: {found_count} global variables detected (max allowed: {max_allowed})." if score == 0
            else "Good job keeping the global scope clean."
        )
        return TestResult("count_global_vars", score, report, parameters={"max_allowed": max_allowed})

    @staticmethod
    def check_headings_sequential(submission_files) -> TestResult:
        """
        Checks if heading levels (`<h1>`, `<h2>`, etc.) are sequential and do not skip
        levels (e.g., an `<h3>` following an `<h1>`), which is important for accessibility.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        headings = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        # Check if each heading is at most one level greater than the previous one
        is_sequential = all(headings[i] <= headings[i + 1] for i in range(len(headings) - 1))
        score = 100 if is_sequential else 30
        report = (
            "Heading hierarchy is well structured." if is_sequential
            else "Heading order (`<h1>`, `<h2>`, etc.) is not sequential. Avoid skipping levels."
        )
        return TestResult("check_headings_sequential", score, report)

    @staticmethod
    def check_all_images_have_alt(submission_files) -> TestResult:
        """
        Verifies that all `<img>` tags in `index.html` have a non-empty `alt` attribute.
        The score is proportional to the percentage of images meeting this accessibility rule.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all("img")
        if not images:
            return TestResult("check_all_images_have_alt", 100, "No images found to check.")
        with_alt = sum(1 for img in images if img.has_attr('alt') and img['alt'].strip())
        score = int((with_alt / len(images)) * 100)
        report = f"{with_alt} de {len(images)} imagens tem o atributo `alt` preenchido."
        return TestResult("check_all_images_have_alt", score, report)

    @staticmethod
    def check_html_direct_children(submission_files) -> TestResult:
        """
        Ensures the only direct children of the `<html>` tag are `<head>` and `<body>`,
        enforcing the fundamental and correct structure of an HTML document.
        """
        html_content = submission_files.get("index.html", "") # Standardized to index.html
        soup = BeautifulSoup(html_content, 'html.parser')

        html_tag = soup.find('html')
        if not html_tag:
            return TestResult("check_html_direct_children", 0, "Tag <html> não encontrada.")

        children_names = [child.name for child in html_tag.findChildren(recursive=False) if child.name]

        is_valid = all(name in ['head', 'body'] for name in
                       children_names) and 'head' in children_names and 'body' in children_names

        if is_valid:
            return TestResult("check_html_direct_children", 100, "Estrutura da tag <html> está correta.")

        return TestResult("check_html_direct_children", 0,
                          " A tag <html> deve conter apenas as tags <head> e <body> como filhos diretos.")

    @staticmethod
    def check_tag_not_inside(submission_files, child_tag: str, parent_tag: str) -> TestResult:
        """
        Checks that a specific tag (`child_tag`) is not nested anywhere inside another
        specific tag (`parent_tag`). Useful for enforcing structural rules.
        """
        html_content = submission_files.get("index.html", "") # Standardized to index.html
        soup = BeautifulSoup(html_content, 'html.parser')

        parent = soup.find(parent_tag)
        if parent and parent.find(child_tag):
            report = f"A tag `<{child_tag}>` não deve ser usada dentro da tag `<{parent_tag}>`."
            return TestResult("check_tag_not_inside", 0, report,
                              parameters={"child_tag": child_tag, "parent_tag": parent_tag})

        report = f"A tag `<{child_tag}>` não foi encontrada dentro da tag `<{parent_tag}>`."
        return TestResult("check_tag_not_inside", 100, report, parameters={"child_tag": child_tag, "parent_tag": parent_tag})

    @staticmethod
    def check_internal_links_to_article(submission_files, required_count: int) -> TestResult:
        """
        Checks for a minimum number of internal anchor links pointing to IDs
        that exist exclusively on <article> tags.
        """
        html_content = submission_files.get("home.html", "")
        if not html_content:
            return TestResult("check_internal_links", 0, "Arquivo home.html não encontrado.",
                              parameters={"required_count": required_count})

        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.select('a[href^="#"]')

        valid_links = 0
        for link in links:
            target_id = link['href'][1:]
            if not target_id:
                continue

            target_element = soup.find(id=target_id)
            if target_element and target_element.name == 'article':
                valid_links += 1

        score = min(100, int((valid_links / required_count) * 100))
        report = (f"Encontrados {valid_links} de {required_count} links internos válidos para tags <article>."
                  if score >= 100
                  else f"Encontrados {valid_links} de {required_count} links internos válidos. Links devem apontar para IDs em tags <article>.")
        return TestResult("check_internal_links", score, report, parameters={"required_count": required_count})

    @staticmethod
    def has_style(submission_files: dict, style: str, count: int) -> TestResult:
        """
        Checks if a specific css style rule appears a minimum number of times in `style.css`.
        ex: font-size, font-family, color, background-color
        """
        css_content = submission_files.get("style.css", "")
        found_count = len(re.findall(rf"{re.escape(style)}\s*:\s*[^;]+;", css_content, re.IGNORECASE))
        score = min(100, int((found_count / count) * 100)) if count > 0 else 100
        report = (
            f"Encontrados {found_count} de {count} `{style}` regras de estilização determinadas." if score >= 100
            else f"Encontradas{found_count} de {count} `{style}` regras de estilização determinadas."
        )
        return TestResult("has_style", score, report, parameters={"style": style, "required_count": count})

    @staticmethod
    def check_head_details(submission_files,detail_tag: str) -> TestResult:
        """
        Checks if a specific detail tag exists within the <head> section of index.html.
        detail_tag: meta, title, link, script, style
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        head = soup.find('head')
        if not head:
            return TestResult("check_head_details", 0, "Tag <head> não encontrada.")

        found = head.find(detail_tag) is not None
        score = 100 if found else 0
        report = (
            f"A tag de detalhe `<{detail_tag}>` foi encontrada na seção `<head>`." if found
            else f"A tag de detalhe `<{detail_tag}>` não foi encontrada na seção `<head>`."
        )
        return TestResult("check_head_details", score, report, parameters={"detail_tag": detail_tag})

    @staticmethod
    def check_atribute_and_value(submission_files, tag: str, attribute: str, value: str) -> TestResult:
        """
        Checks if a specific HTML tag contains a specific attribute with a given value.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.find_all(tag, attrs={attribute: value})
        found_count = len(elements)
        score = 100 if found_count > 0 else 0
        report = (
            f"Encontradas {found_count} `<{tag}>` tags com `{attribute}='{value}'`." if score == 100
            else f"Não foram encontradas tags `<{tag}>` com `{attribute}='{value}'`"
        )
        return TestResult("check_attribute_and_value", score, report, parameters={"tag": tag, "attribute": attribute, "value": value})

    @staticmethod
    def check_dir_exists(submission_files, dir_path: str) -> TestResult:
        """
        Checks if a specific directory exists in the submission files.
        """
        exists = any(f.startswith(dir_path.rstrip('/') + '/') for f in submission_files.keys())
        score = 100 if exists else 0
        report = (
            f"O diretório'{dir_path}' existe." if exists
            else f"O diretório '{dir_path}' não existe."
        )
        return TestResult("check_dir_exists", score, report, parameters={"dir_path": dir_path})

    @staticmethod
    def check_project_structure(submission_files, expected_structure: str):
        """
        Check if the expected structure path exists in the submission files.
        ex: "app/index.html", "styles/main.css", "scripts/app.js"
        """
        exists = expected_structure in submission_files
        score = 100 if exists else 0
        report = (
            f"O arquivo'{expected_structure}' existe." if exists
            else f"O arquivo '{expected_structure}' não existe."
        )
        return TestResult("check_project_structure", score, report, parameters={"expected_structure": expected_structure})

    @staticmethod
    def check_id_selector_over_usage(submission_files, max_allowed: int) -> TestResult:
        """
        Counts the number of ID selectors used in style.css and penalizes if it exceeds max_allowed.
        """
        css_content = submission_files.get("style.css", "")
        found_count = len(re.findall(r"#\w+", css_content))
        score = 100 if found_count <= max_allowed else 0
        report = (
            f"{found_count}  seletores de ID detecados (limite: {max_allowed})." if score == 0
            else "Uso controlado de seletores de id."
        )
        return TestResult("check_id_selector_over_usage", score, report, parameters={"max_allowed": max_allowed})

    @staticmethod
    def uses_relative_units(submission_files):
        """Check is the css file uses relative units like em, rem, %, vh, vw"""
        css_content = submission_files.get("style.css", "")
        found = re.search(r"\b(em|rem|%|vh|vw)\b", css_content) is not None
        score = 100 if found else 0
        report = (
            "Estão sendo utilizadas medidas relativas no CSS" if found
            else "Não foram utilizadas medidas relativas como (em, rem, %, vh, vw) no seu CSS."
        )
        return TestResult("uses_relative_units", score, report)

    @staticmethod
    def check_media_queries(submission_files) -> TestResult:
        """
        Checks if there are any media queries in the CSS file.
        """
        css_content = submission_files.get("style.css", "")
        found = re.search(r"@media\s+[^{]+\{", css_content) is not None
        score = 100 if found else 0
        report = (
            "Media queries estão sendo utilizadas no CSS." if found
            else "Não foi encontrado o uso de media queries no seu CSS."
        )
        return TestResult("check_media_queries", score, report)

    @staticmethod
    def check_flexbox_usage(submission_files) -> TestResult:
        """
        Checks if Flexbox properties are used in the CSS file.
        """
        css_content = submission_files.get("style.css", "")
        found = re.search(r"\b(display\s*:\s*flex|flex-)", css_content) is not None
        score = 100 if found else 0
        report = (
            "Propriedades `flexbox` estão sendo utilizadas no CSS" if found
            else "Propriedades `flexbox` não foram encontradas no seu CSS."
        )
        return TestResult("check_flexbox_usage", score, report)

    @staticmethod
    def check_bootstrap_usage(submission_files) -> TestResult:
        """
        Checks if Bootstrap is linked in the HTML file.
        """
        html_content = submission_files.get("index.html", "")
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find("link", href=re.compile(r"bootstrap", re.IGNORECASE)) is not None or \
                soup.find("script", src=re.compile(r"bootstrap", re.IGNORECASE)) is not None
        score = 0 if found else 100
        report = (
            "Você está usando bootstrap no seu CSS" if found
            else "Você não está usando bootstrap no seu CSS."
        )
        return TestResult("check_bootstrap_usage", score, report)


if __name__ == "__main__":
    test = WebDevLibrary.has_style({"style.css":".header { background-color: #333; }"}, "background-color", 1)
    print(test.report)
    test = WebDevLibrary.check_head_details({"index.html":"<html><head><meta charset='UTF-8'><title>Test</title></head><body></body></html>"}, "meta")
    print(test.report)
    test = WebDevLibrary.check_atribute_and_value({"index.html":"<html><head><meta charset='UTF-8'><title>Test</title></head><body></body></html>"}, "meta", "charset", "UTF-8")
    print(test.report)
    test = WebDevLibrary.check_dir_exists({"app/index.html":"<html></html>"}, "app/")
    print(test.report)
    test = WebDevLibrary.check_project_structure({"app/index.html":"<html></html>", "styles/main.css":"body {}"}, "styles/mains.css")
    print(test.report)
    test = WebDevLibrary.check_id_selector_over_usage({"style.css":"#header { color: red !important; } #footer { color: blue !important; }"},  1)
    print(test.report, test.score)
    test = WebDevLibrary.check_bootstrap_usage({"index.html":"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Catalago de filmes e series</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <header class="header">
        <h1>Catálogo de Filmes e Séries</h1>
        <p>Descubra novas aventuras em um só lugar</p>
        <p2>Saiba onde estão suas series e filmes favoritos e onde assisti-los!</p2>
    </header>

    <nav class="menu">
         <div class="menu-item"><a href="">Filmes</a></div>   
         <div class="menu-item"><a href="">Séries</a></div>
         <div class="menu-item"><a href="">Melhores avaliações</a></div>
         <div class="menu-item"><a href="">Lançamentos</a></div>
         <div class="menu-item"><a href="">Em alta</a></div>

    </nav>

    <main class="main">

        <section class="search">
          <form action="#" method="get">
            <input type="text" placeholder="Pesquisar títulos..." name="search" required>
            <button type="submit">Buscar</button>
          </form>
        </section>
    
    
        <section class="catalogo">
    
          <article class="item">
            <img src="https://picsum.photos/id/11/900/500" alt="">
            <h2>Filme 1</h2>
            <p>Descricao do filme q sera escolhido</p>
          </article>
    
          <article class="item">
            <img src="https://picsum.photos/id/8/200/300" alt="">
            <h2>Filme 2</h2>
            <p>Descricao do filme q sera escolhido.</p>
          </article>
    
        </section>
      </main>
    
    
      <footer class="footer">
        <p> Catalogo de filmes e series.Por Lucca Maximo.</p>
      </footer>
    </body>
    </html>"""})
    print(test.report, test.score)

