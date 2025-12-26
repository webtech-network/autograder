from autograder.models.abstract.template import Template
from autograder.models.criteria_tree import CriteriaTree
from autograder.parsers.criteria_tree import CriteriaTreeParser, PreExecutedTreeParser


class CriteriaTreeService:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build_pre_executed_tree(template: Template) -> CriteriaTree:
        """Builds a Criteria tree and pre-executes all tests, having leaves as TestResult objects."""
        request = request_context.get_request()
        config_dict = request.assignment_config.criteria
        submission_files = request.submission_files
        parser = PreExecutedTreeParser(template, submission_files)
        return parser.parse_tree(config_dict)

    @staticmethod
    def build_tree() -> CriteriaTree:
        """Builds the entire criteria tree, including balancing subject weights."""
        request = request_context.get_request()
        config_dict = request.assignment_config.criteria
        parser = CriteriaTreeParser()
        return parser.parse_tree(config_dict)


if __name__ == "__main__":
    criteria_json = {
        "test_library": "essay ai grader",
        "base": {
            "weight": 100,
            "subjects": {
                "foundations": {
                    "weight": 60,
                    "tests": [
                        {"file": "essay.txt", "name": "thesis_statement"},
                        {"file": "essay.txt", "name": "clarity_and_cohesion"},
                        {"file": "essay.txt", "name": "grammar_and_spelling"},
                    ],
                },
                "prompt_adherence": {
                    "weight": 40,
                    "tests": [
                        {
                            "file": "essay.txt",
                            "name": "adherence_to_prompt",
                            "calls": [
                                [
                                    "Analyze the primary causes of the Industrial Revolution and its impact on 19th-century society."
                                ]
                            ],
                        }
                    ],
                },
            },
        },
        "bonus": {
            "weight": 30,
            "subjects": {
                "rhetorical_skill": {
                    "weight": 70,
                    "tests": [
                        {"file": "essay.txt", "name": "counterargument_handling"},
                        {"file": "essay.txt", "name": "vocabulary_and_diction"},
                        {"file": "essay.txt", "name": "sentence_structure_variety"},
                    ],
                },
                "deeper_analysis": {
                    "weight": 30,
                    "tests": [
                        {
                            "file": "essay.txt",
                            "name": "topic_connection",
                            "calls": [
                                ["technological innovation", "social inequality"]
                            ],
                        }
                    ],
                },
            },
        },
        "penalty": {
            "weight": 25,
            "subjects": {
                "logical_integrity": {
                    "weight": 100,
                    "tests": [
                        {"file": "essay.txt", "name": "logical_fallacy_check"},
                        {"file": "essay.txt", "name": "bias_detection"},
                        {"file": "essay.txt", "name": "originality_and_plagiarism"},
                    ],
                }
            },
        },
    }
    submission_files = {
        "essay.txt": """Artificial intelligence (AI) is no longer a concept confined to science fiction; it is a transformative force actively reshaping industries and redefining the nature of work. Its integration into the modern workforce presents a profound duality: on one hand, it offers unprecedented opportunities for productivity and innovation, while on the other, it poses significant challenges related to job displacement and economic inequality. Navigating this transition successfully requires a proactive and nuanced approach from policymakers, businesses, and individuals alike.
The primary benefit of AI in the workplace is its capacity to augment human potential and drive efficiency. AI-powered systems can analyze vast datasets in seconds, automating routine cognitive and manual tasks, which frees human workers to focus on more complex, creative, and strategic endeavors. For instance, in medicine, AI algorithms assist radiologists in detecting tumors with greater accuracy, while in finance, they identify fraudulent transactions far more effectively than any human team. This collaboration between human and machine not only boosts output but also creates new roles centered around AI development, ethics, and system maintenance—jobs that did not exist a decade ago.
However, this technological advancement casts a significant shadow of disruption. The same automation that drives efficiency also leads to job displacement, particularly for roles characterized by repetitive tasks. Assembly line workers, data entry clerks, and even some paralegal roles face a high risk of obsolescence. This creates a widening skills gap, where demand for high-level technical skills soars while demand for traditional skills plummets. Without robust mechanisms for reskilling and upskilling the existing workforce, this gap threatens to exacerbate socio-economic inequality, creating a divide between those who can command AI and those who are displaced by it. There are many gramatical errors in this sentence, for testing purposes.
The most critical challenge, therefore, is not to halt technological progress but to manage its societal impact. A multi-pronged strategy is essential. Governments and educational institutions must collaborate to reform curricula, emphasizing critical thinking, digital literacy, and lifelong learning. Furthermore, corporations have a responsibility to invest in their employees through continuous training programs. Finally, strengthening social safety nets, perhaps through concepts like Universal Basic Income (UBI) or enhanced unemployment benefits, may be necessary to support individuals as they navigate this volatile transition period.
In conclusion, AI is a double-edged sword. Its potential to enhance productivity and create new avenues for growth is undeniable, but so are the risks of displacement and inequality. The future of work will not be a battle of humans versus machines, but rather a story of adaptation. By investing in education, promoting equitable policies, and fostering a culture of continuous learning, we can harness the power of AI to build a more prosperous and inclusive workforce for all."""
    }
    # tree = CriteriaTree.build_pre_executed_tree(criteria_json, WebDevLibrary(), submission_files)
    tree = CriteriaTreeService.build_tree()
    # tree.print_pre_executed_tree()
    tree.print_tree()
