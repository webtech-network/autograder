import sys
import pytest
from pycparser.c_ast import Default

from utils.collector import TestCollector  # Assumindo que este é o seu plugin customizado
import argparse
from core.report.default_reporter import DefaultReporter
# --- Mapeamento de Feedback ---
# Mapeia o nome de cada função de teste para uma mensagem de feedback específica e amigável.
parser = argparse.ArgumentParser(description="Process token argument.")
parser.add_argument("--token", type=str, required=True, help="GitHub token")

FEEDBACK_MAPPING = {
    'test_server_js_exists': '👨‍💻 Seu arquivo `server.js` não foi encontrado na raiz do projeto. Ele é o ponto de entrada principal da aplicação e é essencial.',
    'test_package_json_exists': '📦 Seu arquivo `package.json` não foi encontrado. Ele é necessário para gerenciar as dependências e os scripts do projeto.',
    'test_package_json_has_main_key': '🔑 A chave `"main"` está faltando no seu `package.json`. Ela é necessária para indicar ao Node.js qual arquivo executar.',
    'test_package_json_main_is_correct': '🎯 O script `"main"` no seu `package.json` está incorreto. Ele deve ser `"server.js"`.',
    'test_dir_public_exists': '📁 O diretório `public` não foi encontrado. Ele é necessário para armazenar arquivos estáticos.',
    'test_dir_views_exists': '📁 O diretório `views` não foi encontrado. É onde seus arquivos HTML devem ficar.',
    'test_dir_public_css_exists': '📁 O diretório `public/css` não foi encontrado.',
    'test_dir_public_data_exists': '📁 O diretório `public/data` não foi encontrado.',
    'test_file_style_css_exists': '📄 O arquivo de estilos em `public/css/style.css` não foi encontrado.',
    'test_file_lanches_json_exists': '📄 O arquivo de dados em `public/data/lanches.json` não foi encontrado. A rota da API depende dele.',
    'test_file_index_html_exists': '📄 O template da página principal em `views/index.html` não foi encontrado.',
    'test_file_contato_html_exists': '📄 O template da página de contato em `views/contato.html` não foi encontrado.',
    'test_file_gitignore_exists': '📄 O arquivo `.gitignore` não foi encontrado na raiz do projeto.',
    'test_file_readme_exists': '📄 O arquivo `README.md` não foi encontrado na raiz do projeto.',
    'test_lanches_json_is_valid': '☠️ Seu arquivo `public/data/lanches.json` tem um erro de sintaxe. O servidor não consegue lê-lo.'
}



"""
Executa o pytest com o TestCollector, constrói uma mensagem de feedback consolidada
para todas as falhas e encerra com código 1 se algum teste falhar.
"""
args = parser.parse_args()
reporter = DefaultReporter.create(0,args.token)
collector = TestCollector()
# Assumindo que seu arquivo de teste se chama 'fatal_tests.py'
pytest.main(["--tb=short", "--no-header", "fatal_tests.py"], plugins=[collector])

if collector.failed:
    error_messages = []

    # Constrói a lista de mensagens de feedback a partir do mapeamento
    for failed_test_nodeid in collector.failed:
        # Extrai o nome da função de teste do node ID
        test_name = failed_test_nodeid.split('::')[-1]

        # Busca a mensagem de feedback, fornecendo uma padrão caso não encontre
        feedback = FEEDBACK_MAPPING.get(test_name, f"Ocorreu um erro fatal não especificado em {test_name}.")
        error_messages.append(f"❌ {feedback}")

    # Constrói o relatório final de feedback para o usuário
    final_feedback = "\n--- ☠️ ERROS FATAIS ENCONTRADOS ☠️ ---\n"
    final_feedback += "Seu projeto não pode ser testado devido aos seguintes problemas críticos:\n\n"
    final_feedback += "\n".join(error_messages)
    final_feedback += "\n\nPor favor, corrija esses problemas e tente novamente."

    reporter.overwrite_report_in_repo(new_content=final_feedback)
    sys.exit(1)
else:
    print("\n✅ Todas as verificações de erros fatais passaram com sucesso.")


