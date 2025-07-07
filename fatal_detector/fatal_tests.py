import os
import json
import pytest

# --- Configuration ---
PROJECT_ROOT = os.path.join(os.getenv("GITHUB_WORKSPACE", ""), "submission")


# --- Pytest Fixture ---
@pytest.fixture(scope="module")
def package_json_data():
    """
    A fixture that loads package.json data. It handles file existence and
    JSON validity checks, making it available to other tests.
    'scope="module"' means it runs only once for all tests in this file.
    """
    path = os.path.join(PROJECT_ROOT, 'package.json')
    if not os.path.isfile(path):
        pytest.fail("FATAL: `package.json` is missing. This file is required.")

    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            pytest.fail("FATAL: `package.json` contains invalid JSON and cannot be parsed.")


# --- Test Functions ---

# 1. Critical File Existence
def test_server_js_exists():
    path = os.path.join(PROJECT_ROOT, 'server.js')
    assert os.path.isfile(path)


def test_package_json_exists():
    path = os.path.join(PROJECT_ROOT, 'package.json')
    assert os.path.isfile(path)


# 2. package.json Configuration (uses the fixture)
def test_package_json_has_main_key(package_json_data):
    assert 'main' in package_json_data


def test_package_json_main_is_correct(package_json_data):
    # This test will be skipped if the 'main' key is missing, avoiding an error
    if 'main' in package_json_data:
        assert package_json_data['main'] == 'server.js'


# 3. Directory Structure
def test_dir_public_exists():
    assert os.path.isdir(os.path.join(PROJECT_ROOT, 'public'))


def test_dir_views_exists():
    assert os.path.isdir(os.path.join(PROJECT_ROOT, 'views'))


def test_dir_public_css_exists():
    assert os.path.isdir(os.path.join(PROJECT_ROOT, 'public', 'css'))


def test_dir_public_data_exists():
    assert os.path.isdir(os.path.join(PROJECT_ROOT, 'public', 'data'))


# 4. Required File Existence
def test_file_style_css_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, 'public', 'css', 'style.css'))


def test_file_lanches_json_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, 'public', 'data', 'lanches.json'))


def test_file_index_html_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, 'views', 'index.html'))


def test_file_contato_html_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, 'views', 'contato.html'))


def test_file_gitignore_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, '.gitignore'))


def test_file_readme_exists():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, 'README.md'))


# 5. Data File Validity
def test_lanches_json_is_valid():
    path = os.path.join(PROJECT_ROOT, 'public', 'data', 'lanches.json')
    if not os.path.isfile(path):
        pytest.skip("Skipping lanches.json validity test because the file is missing.")

    with open(path, 'r', encoding='utf-8') as f:
        try:
            json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"FATAL: `public/data/lanches.json` is not a valid JSON file. Error: {e}")