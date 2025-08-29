# Assuming the data structure classes (TestResult, Criteria, etc.)
# and the test library are defined in other files as previously discussed.
from autograder.builder.models.criteria_tree import TestCategory
from autograder.builder.tree_builder import *
from autograder.builder.template_library.templates.web_dev import WebDevLibrary
from autograder.builder.tree_builder import custom_tree
from autograder.core.models.result import Result
from autograder.core.models.test_result import TestResult


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

    def _run(self, submission_files: Dict) -> float:
        """
        Runs the entire grading process and returns the final calculated score.
        """
        print("\n--- STARTING GRADING PROCESS ---")
        # Step 1: Recursively grade each category to get their weighted scores (0-100)
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results)
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results)
        penalty_score = self._grade_subject_or_category(self.criteria.penalty, submission_files, self.penalty_results)
        penalty_score = 100 - penalty_score
        # Step 2: Apply the final scoring logic based on category outcomes
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_score)

        print("\n--- GRADING COMPLETE ---")
        print(f"Aggregated Base Score: {base_score:.2f}")
        print(f"Aggregated Bonus Score: {bonus_score:.2f}")
        print(f"Aggregated Penalty Score: {penalty_score:.2f}")
        print("-" * 25)
        print(f"Final Calculated Score: {final_score:.2f}")
        print("-" * 25)


        return final_score

    def run(self, submission_files: Dict, author_name) -> 'Result':
        final_score = self._run(submission_files)
        return Result(final_score, author_name, submission_files, self.base_results, self.bonus_results, self.penalty_results)

    def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict,
                                   results_list: List['TestResult'], depth=0) -> float:
        """
        Recursively grades a subject or a category, calculating a weighted score.
        """
        prefix = "    " * depth
        print(f"\n{prefix}📘 Grading {current_node.name}...")

        # --- Base Case: This is a leaf-subject containing tests ---
        if hasattr(current_node, 'tests') and current_node.tests is not None:
            subject_test_results = []
            for test in current_node.tests:
                test_results = test.execute(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)

            results_list.extend(subject_test_results)

            if not subject_test_results:
                print(f"{prefix}  -> No tests found. Score: 100.00")
                return 100.0

            # --- Pretty Print Test Score Averaging ---
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores)
            calculation_str = " + ".join(map(str, scores))
            print(f"{prefix}  -> Calculating average of test scores:")
            print(f"{prefix}     ({calculation_str}) / {len(scores)} = {average_score:.2f}")
            return average_score

        # --- Recursive Step: This is a branch with sub-subjects ---
        child_subjects = current_node.subjects.values()
        if not child_subjects:
            print(f"{prefix}  -> No sub-subjects found. Score: 100.00")
            return 100.0

        total_weight = sum(sub.weight for sub in child_subjects)

        child_scores_map = {sub.name: self._grade_subject_or_category(sub, submission_files, results_list, depth + 1)
                            for sub in child_subjects}

        if total_weight == 0:
            # --- Pretty Print Simple Average for Unweighted Subjects ---
            scores = list(child_scores_map.values())
            average_score = sum(scores) / len(scores)
            calculation_str = " + ".join([f"{score:.2f}" for score in scores])
            print(f"\n{prefix}  -> Calculating simple average for unweighted subjects in '{current_node.name}':")
            print(f"{prefix}     ({calculation_str}) / {len(scores)} = {average_score:.2f}")
            return average_score

        # --- Pretty Print Weighted Score Calculation ---
        weighted_score = 0
        calculation_steps = []
        for sub in child_subjects:
            child_score = child_scores_map[sub.name]
            contribution = child_score * (sub.weight / total_weight)
            weighted_score += contribution
            calculation_steps.append(f"({child_score:.2f} * {sub.weight}/{total_weight})")

        calculation_str = " + ".join(calculation_steps)
        print(f"\n{prefix}  -> Calculating weighted score for '{current_node.name}':")
        print(f"{prefix}     {calculation_str} = {weighted_score:.2f}")
        return weighted_score

    def _calculate_final_score(self, base_score: float, bonus_score: float, penalty_score: float) -> float:
        """
        Applies the final scoring logic, mirroring your Scorer class.
        """
        bonus_weight = self.criteria.bonus.max_score
        penalty_weight = self.criteria.penalty.max_score

        final_score = base_score

        if final_score < 100:
            bonus_points_earned = (bonus_score / 100) * bonus_weight
            final_score += bonus_points_earned
            print(f"\nApplying Bonus: {base_score:.2f} + ({bonus_score:.2f}/100 * {bonus_weight}) = {final_score:.2f}")

        final_score = min(100.0, final_score)
        if final_score >= 100:
            print(f"Score capped at 100.00")
        penalty_points_to_subtract = (penalty_score / 100) * penalty_weight
        final_score -= penalty_points_to_subtract
        print(
            f"Applying Penalty: {min(100.0, base_score + (bonus_score / 100) * bonus_weight):.2f} - ({penalty_score:.2f}/100 * {penalty_weight}) = {final_score:.2f}")

        return max(0.0, final_score)


if __name__ == '__main__':
    root = custom_tree()
    grader = Grader(root, WebDevLibrary)
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
    root.print_tree()
    final_score = grader.run(submission_files,"Arthur")

    print("\n--- DETAILED TEST RESULTS ---")
    for result in grader.base_results + grader.bonus_results + grader.penalty_results:
        print(f"[{result.subject_name}] {result.test_name}: Score {result.score} > Report: {result.report}")