import sys
import argparse
import os
import json
from core.report.default_reporter import DefaultReporter

FEEDBACK_MAPPING = {
    # ... (same as before)
}

BASE_DIR = os.path.join(os.environ.get('GITHUB_WORKSPACE', ''), 'submission')

def check_project_structure():
    errors = []

    def p(*paths):
        return os.path.join(BASE_DIR, *paths)

    if not os.path.isfile(p('server.js')):
        errors.append('server_js_exists')
    if not os.path.isfile(p('package.json')):
        errors.append('package_json_exists')
    else:
        try:
            with open(p('package.json'), encoding='utf-8') as f:
                pkg = json.load(f)
            if 'main' not in pkg:
                errors.append('package_json_has_main_key')
            elif pkg['main'] != 'server.js':
                errors.append('package_json_main_is_correct')
        except Exception:
            errors.append('package_json_has_main_key')
    if not os.path.isdir(p('public')):
        errors.append('dir_public_exists')
    if not os.path.isdir(p('views')):
        errors.append('dir_views_exists')
    if not os.path.isdir(p('public', 'css')):
        errors.append('dir_public_css_exists')
    if not os.path.isdir(p('public', 'data')):
        errors.append('dir_public_data_exists')
    if not os.path.isfile(p('public', 'css', 'style.css')):
        errors.append('file_style_css_exists')
    if not os.path.isfile(p('public', 'data', 'lanches.json')):
        errors.append('file_lanches_json_exists')
    else:
        try:
            with open(p('public', 'data', 'lanches.json'), encoding='utf-8') as f:
                json.load(f)
        except Exception:
            errors.append('lanches_json_is_valid')
    if not os.path.isfile(p('views', 'index.html')):
        errors.append('file_index_html_exists')
    if not os.path.isfile(p('views', 'contato.html')):
        errors.append('file_contato_html_exists')
    if not os.path.isfile(p('.gitignore')):
        errors.append('file_gitignore_exists')
    if not os.path.isfile(p('README.md')):
        errors.append('file_readme_exists')

    return errors

def main():
    parser = argparse.ArgumentParser(description="Executa a análise de erros fatais.")
    parser.add_argument("--token", type=str, required=True, help="GitHub token")
    args = parser.parse_args()

    errors = check_project_structure()

    if errors:
        reporter = DefaultReporter.create(0, args.token)
        error_messages = [f"❌ {FEEDBACK_MAPPING[e]}" for e in errors]
        final_feedback = "\n--- ☠️ ERROS FATAIS ENCONTRADOS ☠️ ---\n"
        final_feedback += "Seu projeto não pode ser testado devido aos seguintes problemas críticos:\n\n"
        final_feedback += "\n".join(error_messages)
        final_feedback += "\n\nPor favor, corrija esses problemas e tente novamente."
        print(final_feedback)
        reporter.overwrite_report_in_repo(new_content=final_feedback)
        sys.exit(1)
    else:
        print("\n✅ Todas as verificações de erros fatais passaram com sucesso.")
        sys.exit(0)

if __name__ == '__main__':
    main()