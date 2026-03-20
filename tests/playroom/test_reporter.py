import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import MagicMock
from autograder.services.report.default_reporter import DefaultReporter
from autograder.models.dataclass.feedback_preferences import FeedbackPreferences, GeneralPreferences, DefaultReporterPreferences, LearningResource, AiReporterPreferences
from autograder.models.dataclass.focus import Focus, FocusedTest
from autograder.models.result_tree import TestResultNode, ResultTree, RootResultNode, CategoryResultNode

def create_mock_test(name, score, report, file_targets=None):
    test_node = MagicMock(spec=TestResultNode)
    test_node.name = name
    test_node.score = score
    test_node.report = report
    test_node.parameters = {"stdin": "input_val"}
    test_node.test_node = MagicMock()
    test_node.test_node.file_target = file_targets or ["main.py"]
    return test_node

def run_playroom():
    reporter = DefaultReporter()
    
    # 1. Setup Mock Results
    test_pass = create_mock_test("Soma de Inteiros", 100.0, "Passou em todos os casos.")
    test_fail = create_mock_test("Subtração de Inteiros", 0.0, "Erro: 5 - 3 deveria ser 2, mas foi 8.")
    test_penalty = create_mock_test("Padrão de Nomenclatura", 50.0, "Variáveis 'A' e 'B' não seguem snake_case.")
    test_bonus = create_mock_test("Algoritmo O(n)", 100.0, "Excelente performance!")
    
    focus = Focus(
        base=[
            FocusedTest(test_result=test_pass, diff_score=0.0),
            FocusedTest(test_result=test_fail, diff_score=20.0)
        ],
        penalty=[
            FocusedTest(test_result=test_penalty, diff_score=5.0)
        ],
        bonus=[
            FocusedTest(test_result=test_bonus, diff_score=10.0)
        ]
    )
    
    root = MagicMock(spec=RootResultNode)
    root.score = 85.0
    result_tree = MagicMock(spec=ResultTree)
    result_tree.root = root
    result_tree.template_name = "projeto_final_python"
    result_tree.get_all_test_results.return_value = [test_pass, test_fail, test_penalty, test_bonus]
    result_tree.get_passed_tests.return_value = [test_pass, test_bonus]
    result_tree.get_failed_tests.return_value = [test_fail, test_penalty]

    # 2. Setup Preferences
    preferences = FeedbackPreferences(
        general=GeneralPreferences(
            report_title="🚀 Relatório de Desempenho do Aluno",
            show_score=True,
            show_passed_tests=True, # Vamos mostrar os que passaram para o teste
            add_report_summary=True,
            online_content=[
                LearningResource(
                    url="https://docs.python.org/3/tutorial/controlflow.html",
                    description="Tutorial de Controle de Fluxo",
                    linked_tests=["Soma de Inteiros"]
                )
            ]
        ),
        default=DefaultReporterPreferences(
            category_headers={
                "base": "📑 Requisitos do Exercício",
                "penalty": "⚠️ Penalidades Aplicadas",
                "bonus": "✨ Pontos de Bônus"
            }
        ),
        ai=AiReporterPreferences()
    )

    # 3. Generate Report
    print("\n" + "="*80)
    print(" PLAYROOM: DEFAULT REPORTER TEST ")
    print("="*80 + "\n")
    
    report = reporter.generate_report(focus, result_tree, preferences)
    
    print(report)
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    run_playroom()
