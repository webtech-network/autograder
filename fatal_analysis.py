import sys
import pytest
import argparse
import os
from core.report.default_reporter import DefaultReporter

# --- Mapeamento de Feedback ---
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


class FatalErrorReporter:
    """
    Plugin Pytest para coletar falhas e reportar erros fatais de forma consolidada.
    """

    def __init__(self, token):
        self.failed_nodeids = []
        self.reporter = DefaultReporter.create(0, token)

    def pytest_runtest_logreport(self, report):
        """Coleta os resultados de cada teste executado."""
        if report.when == "call" and report.failed:
            self.failed_nodeids.append(report.nodeid)

    def pytest_sessionfinish(self, session):
        """
        Executado após todos os testes terminarem.
        Aqui é o lugar certo para a lógica de feedback.
        """
        if self.failed_nodeids:
            error_messages = []
            print("THERE WERE FATAL ERRORS DETECTED IN YOUR PROJECT!")

            for nodeid in self.failed_nodeids:
                test_name = nodeid.split('::')[-1]
                feedback = FEEDBACK_MAPPING.get(test_name, f"Ocorreu um erro fatal não especificado em {test_name}.")
                error_messages.append(f"❌ {feedback}")

            final_feedback = "\n--- ☠️ ERROS FATAIS ENCONTRADOS ☠️ ---\n"
            final_feedback += "Seu projeto não pode ser testado devido aos seguintes problemas críticos:\n\n"
            final_feedback += "\n".join(error_messages)
            final_feedback += "\n\nPor favor, corrija esses problemas e tente novamente."

            print(final_feedback)
            # self.reporter.overwrite_report_in_repo(new_content=final_feedback) # Descomente quando o reporter estiver pronto

            # O pytest se encarregará de sair com um código de erro apropriado
            # por causa dos testes que falharam. Não precisamos de sys.exit(1) manual aqui.

        else:
            print("\n✅ Todas as verificações de erros fatais passaram com sucesso.")


def main():
    """
    Ponto de entrada principal do script.
    """
    parser = argparse.ArgumentParser(description="Executa a análise de erros fatais.")
    parser.add_argument("--token", type=str, required=True, help="GitHub token")
    args = parser.parse_args()

    # Cria a instância do nosso plugin
    reporter_plugin = FatalErrorReporter(token=args.token)

    # Executa o pytest, passando o plugin.
    # O pytest retornará um código de saída (0 para sucesso, >0 para falhas)
    exit_code = pytest.main(
        ["--tb=short", "--no-header", "fatal_detector/fatal_tests.py"],
        plugins=[reporter_plugin]
    )

    # Encerra o script com o mesmo código de saída do pytest.
    sys.exit(exit_code)


if __name__ == '__main__':
    main()