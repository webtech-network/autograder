import sys
import argparse
import os
import json
from core.report.default_reporter import DefaultReporter

FEEDBACK_MAPPING = {
    'server_js_exists': '👨‍💻 Seu arquivo `server.js` não foi encontrado na raiz do projeto. Ele é o ponto de entrada principal da aplicação e é essencial.',
    'package_json_exists': '📦 Seu arquivo `package.json` não foi encontrado. Ele é necessário para gerenciar as dependências e os scripts do projeto.',
    'package_json_has_main_key': '🔑 A chave `"main"` está faltando no seu `package.json`. Ela é necessária para indicar ao Node.js qual arquivo executar.',
    'package_json_main_is_correct': '🎯 O script `"main"` no seu `package.json` está incorreto. Ele deve ser `"server.js"`.',
    'dir_public_exists': '📁 O diretório `public` não foi encontrado. Ele é necessário para armazenar arquivos estáticos.',
    'dir_views_exists': '📁 O diretório `views` não foi encontrado. É onde seus arquivos HTML devem ficar.',
    'dir_public_css_exists': '📁 O diretório `public/css` não foi encontrado.',
    'dir_public_data_exists': '📁 O diretório `public/data` não foi encontrado.',
    'file_style_css_exists': '📄 O arquivo de estilos em `public/css/style.css` não foi encontrado.',
    'file_lanches_json_exists': '📄 O arquivo de dados em `public/data/lanches.json` não foi encontrado. A rota da API depende dele.',
    'file_index_html_exists': '📄 O template da página principal em `views/index.html` não foi encontrado.',
    'file_contato_html_exists': '📄 O template da página de contato em `views/contato.html` não foi encontrado.',
    'file_gitignore_exists': '📄 O arquivo `.gitignore` não foi encontrado na raiz do projeto.',
    'file_readme_exists': '📄 O arquivo `README.md` não foi encontrado na raiz do projeto.',
    'lanches_json_is_valid': '☠️ Seu arquivo `public/data/lanches.json` tem um erro de sintaxe. O servidor não consegue lê-lo.'
}

def check_project_structure():
    errors = []

    # Check files and directories
    if not os.path.isfile('server.js'):
        errors.append('server_js_exists')
    if not os.path.isfile('package.json'):
        errors.append('package_json_exists')
    else:
        # Check package.json content
        try:
            with open('package.json', encoding='utf-8') as f:
                pkg = json.load(f)
            if 'main' not in pkg:
                errors.append('package_json_has_main_key')
            elif pkg['main'] != 'server.js':
                errors.append('package_json_main_is_correct')
        except Exception:
            errors.append('package_json_has_main_key')
    if not os.path.isdir('public'):
        errors.append('dir_public_exists')
    if not os.path.isdir('views'):
        errors.append('dir_views_exists')
    if not os.path.isdir(os.path.join('public', 'css')):
        errors.append('dir_public_css_exists')
    if not os.path.isdir(os.path.join('public', 'data')):
        errors.append('dir_public_data_exists')
    if not os.path.isfile(os.path.join('public', 'css', 'style.css')):
        errors.append('file_style_css_exists')
    if not os.path.isfile(os.path.join('public', 'data', 'lanches.json')):
        errors.append('file_lanches_json_exists')
    else:
        # Validate lanches.json syntax
        try:
            with open(os.path.join('public', 'data', 'lanches.json'), encoding='utf-8') as f:
                json.load(f)
        except Exception:
            errors.append('lanches_json_is_valid')
    if not os.path.isfile(os.path.join('views', 'index.html')):
        errors.append('file_index_html_exists')
    if not os.path.isfile(os.path.join('views', 'contato.html')):
        errors.append('file_contato_html_exists')
    if not os.path.isfile('.gitignore'):
        errors.append('file_gitignore_exists')
    if not os.path.isfile('README.md'):
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