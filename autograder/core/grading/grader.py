from typing import List, Dict

# Assuming the data structure classes (TestResult, Criteria, etc.)
# and the test library are defined in other files as previously discussed.
from autograder.builder.tree_builder import *
from template_library.web_dev import WebDevLibrary
from autograder.builder.tree_builder import custom_tree
class Grader:
    """
    Traverses a Criteria tree, executes tests, and calculates a weighted score.
    """
    def __init__(self, criteria_tree: 'Criteria', test_library: object):
        self.criteria = criteria_tree
        self.test_library = test_library
        # These lists will be populated with all individual test results
        self.base_results: List['TestResult'] = []
        self.bonus_results: List['TestResult'] = []
        self.penalty_results: List['TestResult'] = []

    def run(self, submission_files: Dict) -> float:
        """
        Runs the entire grading process and returns the final calculated score.
        """
        # Step 1: Recursively grade each category to get their weighted scores (0-100)
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results)
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results)
        penalty_score = self._grade_subject_or_category(self.criteria.penalty, submission_files, self.penalty_results)

        # Step 2: Apply the final scoring logic based on category outcomes
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_score)

        print("\n--- GRADING COMPLETE ---")
        print(f"Aggregated Base Score: {base_score:.2f}")
        print(f"Aggregated Bonus Score: {bonus_score:.2f}")
        print(f"Aggregated Penalty Score: {penalty_score:.2f}")
        print("-" * 25)
        print(f"Final Calculated Score: {final_score:.2f}")

        return final_score

    def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict, results_list: List['TestResult']) -> float:
        """
        Recursively grades a subject or a category, calculating a weighted score.
        """
        # --- Base Case: This is a leaf-subject containing tests ---
        if hasattr(current_node, 'tests') and current_node.tests is not None:
            subject_test_results = []
            for test in current_node.tests:
                # Execute test and get a list of TestResult objects
                test_results = test.execute(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)

            # Store all raw results in the category's master list
            results_list.extend(subject_test_results)

            # Return the simple average score for this leaf subject's tests
            if not subject_test_results:
                return 100.0
            return sum(res.score for res in subject_test_results) / len(subject_test_results)

        # --- Recursive Step: This is a branch with sub-subjects ---
        child_subjects = current_node.subjects.values()
        if not child_subjects:
            return 100.0  # An empty branch gets a perfect score

        total_weight = sum(sub.weight for sub in child_subjects)
        if total_weight == 0:
            # If no weights are defined, fall back to a simple average
            child_scores = [self._grade_subject_or_category(sub, submission_files, results_list) for sub in child_subjects]
            return sum(child_scores) / len(child_scores)

        # Calculate the weighted score for the branch
        weighted_score = 0
        for sub in child_subjects:
            child_score = self._grade_subject_or_category(sub, submission_files, results_list)
            # The score contribution of the child is its score scaled by its weight percentage
            weighted_score += child_score * (sub.weight / total_weight)

        return weighted_score

    def _calculate_final_score(self, base_score: float, bonus_score: float, penalty_score: float) -> float:
        """
        Applies the final scoring logic, mirroring your Scorer class.
        """
        # For this example, we'll assume the bonus/penalty weights from your config
        # represent the maximum points they can affect.
        bonus_weight = self.criteria.bonus.subjects.get("bonus", {"weight": 40})["weight"]
        penalty_weight = self.criteria.penalty.subjects.get("penalty", {"weight": 100})["weight"]


        final_score = base_score

        # Add bonus points if the base score is not perfect
        if final_score < 100:
            # Calculate how many bonus points were actually earned
            bonus_points_earned = (bonus_score / 100) * bonus_weight
            final_score += bonus_points_earned

        # Cap score at 100 after applying bonus
        final_score = min(100.0, final_score)

        # Apply penalty
        penalty_points_to_subtract = (penalty_score / 100) * penalty_weight
        final_score -= penalty_points_to_subtract

        # Ensure the final score is not below 0
        return max(0.0, final_score)


if __name__ == '__main__':
    root = custom_tree()
    grader = Grader(root,WebDevLibrary)
    submission_files = {
        "index.html": """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Página de Teste</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>

        <header>
            <h1>Bem-vindo à Página de Teste</h1>
            <h3>Sub-cabeçalho H3</h3> </header>

        <main id="main-content">
            <p class="intro">Este é um parágrafo de introdução para testar o sistema.</p>

            <img src="image1.jpg" alt="Descrição da imagem 1">
            <img src="image2.jpg"> <div>
                <p>Este é um div com um <font color="red">texto antigo</font> dentro.</p> </div>

            <a href="#">Este é um link de teste.</a>
        </main>

        <footer>
            <p>&copy; 2024 Autograder Test Page</p>
        </footer>

        <script src="script.js"></script>
    </body>
    </html>
    """,

        "style.css": """
    /* Arquivo CSS para Teste */

    body {
        font-family: sans-serif;
        color: #333; /* Passa no teste 'css_uses_property' */
    }

    #main-content {
        display: flex; /* Passa no teste 'css_uses_property' */
        width: 80%;
    }

    .intro {
        font-size: 16px;
        /* Penalidade: Uso de !important */
        color: navy !important; 
    }

    /* Penalidade: Regra de CSS vazia */
    .empty-rule {

    }
    """,

        "script.js": """
    // Arquivo JavaScript para Teste

    document.addEventListener('DOMContentLoaded', () => {
        const header = document.getElementById('main-content');
        console.log('Página carregada e script executado.');
    });

    // Penalidade: Uso do método proibido 'document.write'
    document.write("<p>Este texto foi adicionado com document.write</p>");

    // Teste de feature: usa arrow function
    const simpleFunction = () => {
        return true;
    };
    """
    }
    final_score = grader.run(submission_files)
