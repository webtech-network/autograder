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
    'db_container_running': '- 🐳 Ocorreu um problema ao iniciar o contêiner do banco de dados. Por favor, contate o time de desenvolvimento do autograder.\n',
    'db_connectivity': '- 🔌 Não foi possível estabelecer uma conexão com o banco de dados. Por favor, contate o time de desenvolvimento do autograder.\n',
    'migration_application': '-  migrating... ERROR. Falha ao criar o aplicar as migrations. Cheque se houveram problemas de conexão com o BD ou erros lógicos.\n',
    'seeds_running': '- seeding... RUNNING... ERROR. Falha ao executar as seeds. Verifique seus arquivos de seed em busca de erros de sintaxe SQL ou se as tabelas foram criadas corretamente pelas migrations.\n',
    'knexfile_exists': '👨‍💻 Seu arquivo `knexfile.js` não foi encontrado na raiz do projeto.\n',
    'migrations_exist': '👨‍💻 Seu arquivo de migrations não foi encontrado na pasta db/migrations.\n',
    'seeds_exist': '👨‍💻 Seus arquivos de seeds não foram encontrados na pasta db/migrations.\n'
}

BASE_DIR = os.path.join(os.environ.get('GITHUB_WORKSPACE', ''), 'submission')
def check_server_status(errors):
    server_status = os.environ.get('SERVER_STATUS', '0')
    if server_status == "1":
        errors.append('server_js_invalid')

def check_db_container_status(errors):
    db_container_status = os.environ.get('DATABASE_CONTAINER_STATUS', '0')
    if db_container_status == "1":
        errors.append('db_container_running')

def check_db_status(errors):
    db_conn_status = os.environ.get('DATABASE_STATUS', '0')
    if db_conn_status == "1":
        errors.append('db_connectivity')

def check_migration_application_status(errors):
    migration_application_status = os.environ.get('MIGRATIONS_APPLICATION_STATUS', '0')
    if migration_application_status == "1":
        errors.append('migration_application')

def check_seeds_running_status(errors):
    seeds_running_status = os.environ.get('SEEDS_RUN_STATUS', '0')
    if seeds_running_status == "1":
        errors.append('seeds_running')

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

def check_knexfile_exists(errors):
    path = os.path.join(BASE_DIR, 'knexfile.js')
    if not os.path.isfile(path):
        errors.append('knexfile_exists')

def check_migrations_exists(errors):
    path = os.path.join(BASE_DIR, 'db', 'migrations', 'solution_migrations.js')
    if not os.path.isfile(path):
        errors.append('migrations_exist')

def check_seeds_exist(errors):
    agentes_seed_path = os.path.join(BASE_DIR, 'db', 'seeds', 'agentes.js')
    casos_seed_path = os.path.join(BASE_DIR, 'db', 'seeds', 'casos.js')
    if not os.path.isfile(agentes_seed_path) or not os.path.isfile(casos_seed_path):
        errors.append('seeds_exist')

def main():

    errors = []
    check_server_status(errors)
    # Check for server.js
    check_server_js_exists(errors)

    # Check for package.json and its content
    package_json = check_package_json_exists(errors)
    if package_json:
        check_package_json_content(package_json, errors)
    
    #Checks if the container started and the database connection
    check_db_container_status(errors)
    check_db_status(errors)

    #Checks if the knexfile exists
    check_knexfile_exists(errors)

    #Checks if the migrations exist
    check_migrations_exists(errors)

    #Checks if the seeds exist
    check_seeds_exist(errors)

    #Checks for the Migration application status
    check_migration_application_status(errors)

    #Checks for seeds running status
    check_seeds_running_status(errors)

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