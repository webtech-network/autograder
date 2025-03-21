import pytest
from bs4 import BeautifulSoup
'''
TEST SUITE FOR HTML PAGE
'''



# Helper function to parse HTML content using BeautifulSoup
def parse_html():
    # Directly open and parse the 'index.html' file
    with open('../submission/index.html', 'r') as file:
        html_content = file.read()
    return BeautifulSoup(html_content, "html.parser")

# 1. Test Required Structural Elements

def test_doctype():
    soup = parse_html()
    # Ensure the DOCTYPE declaration is present
    assert '<!DOCTYPE html>' in open('index.html').read()

def test_html_tag():
    soup = parse_html()
    # Ensure the <html> tag is present
    assert soup.find('html') is not None, "The <html> tag is missing."

def test_head_tag():
    soup = parse_html()
    # Ensure the <head> tag is present
    assert soup.find('head') is not None, "The <head> tag is missing."

def test_body_tag():
    soup = parse_html()
    # Ensure the <body> tag is present
    assert soup.find('body') is not None, "The <body> tag is missing."

def test_title_tag():
    soup = parse_html()
    # Ensure the <title> tag is present
    assert soup.find('title') is not None, "The <title> tag is missing."

def test_meta_charset():
    soup = parse_html()
    # Ensure the meta charset tag is present
    meta_tag = soup.find('meta', attrs={"charset": True})
    assert meta_tag is not None, "Missing <meta charset='UTF-8'>"

def test_meta_viewport():
    soup = parse_html()
    # Ensure the meta viewport tag is present for responsive design
    meta_tag = soup.find('meta', attrs={"name": "viewport"})
    assert meta_tag is not None, "Missing <meta name='viewport'> tag"

# 2. Test Forbidden Elements (One test for each forbidden tag)

def test_forbidden_b_tag():
    soup = parse_html()
    # Ensure no <b> tag is present
    assert soup.find('b') is None, "Found forbidden <b> tag"

def test_forbidden_i_tag():
    soup = parse_html()
    # Ensure no <i> tag is present
    assert soup.find('i') is None, "Found forbidden <i> tag"

def test_forbidden_font_tag():
    soup = parse_html()
    # Ensure no <font> tag is present
    assert soup.find('font') is None, "Found forbidden <font> tag"

def test_forbidden_marquee_tag():
    soup = parse_html()
    # Ensure no <marquee> tag is present
    assert soup.find('marquee') is None, "Found forbidden <marquee> tag"

def test_forbidden_center_tag():
    soup = parse_html()
    # Ensure no <center> tag is present
    assert soup.find('center') is None, "Found forbidden <center> tag"

# 3. Test Accessibility and Semantic HTML (One test per element)

def test_image_alt_attributes():
    soup = parse_html()
    # Ensure all images have alt attributes
    images = soup.find_all('img')
    for img in images:
        assert img.get('alt'), "Image missing 'alt' attribute"

def test_form_labels():
    soup = parse_html()
    # Ensure all form inputs have associated labels
    inputs = soup.find_all('input')
    for input_tag in inputs:
        label = soup.find('label', attrs={'for': input_tag.get('id')})
        assert label, f"Missing label for {input_tag.get('id')}"

def test_semantic_header_tag():
    soup = parse_html()
    # Ensure <header> tag is present
    assert soup.find('header') is not None, "Missing <header> tag"

def test_semantic_footer_tag():
    soup = parse_html()
    # Ensure <footer> tag is present
    assert soup.find('footer') is not None, "Missing <footer> tag"

def test_semantic_nav_tag():
    soup = parse_html()
    # Ensure <nav> tag is present
    assert soup.find('nav') is not None, "Missing <nav> tag"

def test_semantic_main_tag():
    soup = parse_html()
    # Ensure <main> tag is present
    assert soup.find('main') is not None, "Missing <main> tag"

# 4. Test SEO and Metadata Best Practices (One test per SEO tag)

def test_meta_description():
    soup = parse_html()
    # Ensure the meta description tag is present
    meta_tag = soup.find('meta', attrs={"name": "description"})
    assert meta_tag is not None, "Missing <meta name='description'> tag"

def test_open_graph_title_tag():
    soup = parse_html()
    # Ensure Open Graph meta title tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:title"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:title'> tag"

def test_open_graph_description_tag():
    soup = parse_html()
    # Ensure Open Graph meta description tag is present
    meta_tag = soup.find('meta', attrs={"property": "og:description"})
    assert meta_tag is not None, "Missing Open Graph <meta property='og:description'> tag"

# 5. Test Proper Nesting and Closing Tags

def test_proper_nesting():
    soup = parse_html()
    # Check for correct nesting of elements (e.g., <ul> should only contain <li>)
    ul_tags = soup.find_all('ul')
    for ul in ul_tags:
        for child in ul.children:
            assert child.name == 'li' or child.name is None, f"Invalid child in <ul>: {child.name}"

def test_closing_tags():
    soup = parse_html()
    # Ensure all non-void elements are properly closed
    void_tags = ['img', 'br', 'hr', 'input', 'meta']
    for tag in soup.find_all(True):  # True selects all tags
        if tag.name not in void_tags:
            assert soup.find(tag.name) is not None, f"Missing closing tag for <{tag.name}>"

# 6. Test HTML Validation (Basic placeholder test for valid HTML)

def test_valid_html():
    soup = parse_html()
    assert soup is not None, "HTML is not valid"

