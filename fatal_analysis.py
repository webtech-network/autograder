import os
import json
import sys
import time
from core.report.default_reporter import DefaultReporter
import argparse
parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")

FEEDBACK_MAPPING = {
    'server_js_invalid': '- ⚠️ Não conseguimos rodar o seu servidor. Por favor, verifique seu código ou busque suporte nas guildas.\n',
    'server_js_exists': '- 👨‍💻 Seu arquivo `server.js` não foi encontrado na raiz do projeto. Ele é o ponto de entrada principal da aplicação e é essencial.\n',
    'package_json_exists': '- 📦 Seu arquivo `package.json` não foi encontrado. Ele é necessário para gerenciar as dependências e os scripts do projeto.\n',
    'package_json_has_main_key': '- 🔑 A chave `"main"` está faltando no seu `package.json`. Ela é necessária para indicar ao Node.js qual arquivo executar.\n',
    'package_json_main_is_correct': '- 🎯 O script `"main"` no seu `package.json` está incorreto. Ele deve ser `"server.js"`.\n',
    'package_json_has_express_dependency': '- 🚀 O pacote `express` não foi encontrado nas dependências do seu `package.json`. Ele é essencial para o servidor.\n',
}

BASE_DIR = os.path.join(os.environ.get('GITHUB_WORKSPACE', ''), 'submission')
def check_server_status(errors):
    server_status = os.environ.get('SERVER_STATUS', '0')
    if server_status == "1":
        errors.append('server_js_invalid')
def check_server_js_exists(errors):
    path = os.path.join(BASE_DIR, 'server.js')
    if not os.path.isfile(path):
        errors.append('server_js_exists')

def check_package_json_exists(errors):
    path = os.path.join(BASE_DIR, 'package.json')
    if not os.path.isfile(path):
        errors.append('package_json_exists')
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        errors.append('package_json_invalid')
        return None

def check_package_json_content(package_json, errors):
    if 'main' not in package_json:
        errors.append('package_json_has_main_key')

    dependencies = package_json.get('dependencies', {})
    if 'express' not in dependencies:
        errors.append('package_json_has_express_dependency')

def main():

    errors = []
    check_server_status(errors)
    # Check for server.js
    check_server_js_exists(errors)

    # Check for package.json and its content
    package_json = check_package_json_exists(errors)
    if package_json:
        check_package_json_content(package_json, errors)

    # Handle errors
    if errors:
        token = parser.parse_args().token
        reporter = DefaultReporter.create(0, token )
        error_messages = [f"❌ {FEEDBACK_MAPPING[e]}" for e in errors]
        final_feedback = "\n--- ☠️ ERROS FATAIS ENCONTRADOS ☠️ ---\n"
        final_feedback += "Seu projeto não pode ser testado devido aos seguintes problemas críticos:\n\n"
        final_feedback += "\n".join(error_messages)
        final_feedback += "\n\nPor favor, corrija esses problemas e tente novamente."
        reporter.overwrite_report_in_repo(new_content=final_feedback)
        time.sleep(3)
        sys.exit(1)
    else:
        print("\n✅ Todas as verificações de erros fatais passaram com sucesso.")
        sys.exit(0)

if __name__ == '__main__':
    main()