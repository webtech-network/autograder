from autograder.builder.execution_helpers.AI_Executor import AiExecutor, ai_executor
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult

# ===============================================================
# region: Original TestFunction Implementations
# ===============================================================

class ClarityAndCohesionTest(TestFunction):
    @property
    def name(self): return "clarity_and_cohesion"
    @property
    def description(self): return "Evaluates the overall clarity and flow of the essay."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale from 0 to 100, how clear and well-structured is the essay? Assess the logical flow of arguments, the transitions between paragraphs, and the overall readability."
        return ai_executor.add_test(self.name,  prompt)

class GrammarAndSpellingTest(TestFunction):
    @property
    def name(self): return "grammar_and_spelling"
    @property
    def description(self): return "Checks the essay for grammatical errors, spelling mistakes, and punctuation."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale from 0 to 100, evaluate the essay for grammatical accuracy. Consider spelling, punctuation, sentence structure, and subject-verb agreement."
        return ai_executor.add_test(self.name,  prompt)

class ArgumentStrengthTest(TestFunction):
    @property
    def name(self): return "argument_strength"
    @property
    def description(self): return "Assesses the strength and support of the arguments presented."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Evaluate the strength of the arguments in the essay on a scale from 0 to 100. Are the claims well-supported with evidence and examples? Is the reasoning sound and persuasive?"
        return ai_executor.add_test(self.name,  prompt)

class ThesisStatementTest(TestFunction):
    @property
    def name(self): return "thesis_statement"
    @property
    def description(self): return "Evaluates the clarity and effectiveness of the thesis statement."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, how strong and clear is the essay's thesis statement? Does it present a clear, arguable position that is maintained throughout the text?"
        return ai_executor.add_test(self.name,  prompt)

class AdherenceToPromptTest(TestFunction):
    @property
    def name(self): return "adherence_to_prompt"
    @property
    def description(self): return "Checks how well the essay addresses the specific requirements of the prompt."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze.", "prompt_requirements": "The specific prompt the essay should be addressing."}
    def execute(self,  prompt_requirements: str) -> TestResult:
        prompt = f"Given the essay prompt '{prompt_requirements}', how well does the submitted essay address all parts of the question? Rate on a scale of 0 to 100."
        return ai_executor.add_test(self.name,  prompt)

class OriginalityAndPlagiarismTest(TestFunction):
    @property
    def name(self): return "originality_and_plagiarism"
    @property
    def description(self): return "A simplified check for originality by looking for common phrases or copied content."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, assess the originality of this essay. While you cannot perform a web search, evaluate the text for signs of unoriginal content, such as generic phrasing or overly common arguments that might suggest plagiarism."
        return ai_executor.add_test(self.name,  prompt)

# ===============================================================
# endregion
# ===============================================================

# ===============================================================
# region: 10 New Advanced TestFunction Implementations
# ===============================================================

class TopicConnectionTest(TestFunction):
    @property
    def name(self): return "topic_connection"
    @property
    def description(self): return "Checks if the essay successfully makes a connection between two specified topics."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay.", "topic1": "The first topic.", "topic2": "The second topic." }
    def execute(self,  topic1: str, topic2: str) -> TestResult:
        prompt = f"On a scale of 0 to 100, how effectively does the essay establish a meaningful connection between the concepts of '{topic1}' and '{topic2}'? Evaluate the depth and clarity of the linkage."
        return ai_executor.add_test(self.name,  prompt)

class CounterargumentHandlingTest(TestFunction):
    @property
    def name(self): return "counterargument_handling"
    @property
    def description(self): return "Assesses how well the essay acknowledges and refutes potential counterarguments."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, evaluate how well the essay addresses potential counterarguments. Does it anticipate opposing viewpoints and provide thoughtful refutations?"
        return ai_executor.add_test(self.name,  prompt)

class IntroductionAndConclusionTest(TestFunction):
    @property
    def name(self): return "introduction_and_conclusion"
    @property
    def description(self): return "Evaluates the effectiveness of the essay's introduction and conclusion."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, assess the quality of the introduction and conclusion. Does the introduction effectively engage the reader and present the thesis? Does the conclusion provide a strong summary and offer final insights?"
        return ai_executor.add_test(self.name,  prompt)

class EvidenceQualityTest(TestFunction):
    @property
    def name(self): return "evidence_quality"
    @property
    def description(self): return "Assesses the relevance and quality of the evidence used to support claims."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, evaluate the quality of the evidence used in the essay. Is the evidence relevant, credible, and sufficient to support the main arguments?"
        return ai_executor.add_test(self.name,  prompt)

class ToneAndStyleTest(TestFunction):
    @property
    def name(self): return "tone_and_style"
    @property
    def description(self): return "Evaluates if the essay's tone and writing style are appropriate for the topic and audience."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay.", "expected_tone": "The expected tone (e.g., formal, persuasive, objective)." }
    def execute(self,  expected_tone: str) -> TestResult:
        prompt = f"On a scale of 0 to 100, does the essay maintain an appropriate '{expected_tone}' tone and style throughout? Evaluate the author's voice, word choice, and overall professionalism."
        return ai_executor.add_test(self.name,  prompt)

class VocabularyAndDictionTest(TestFunction):
    @property
    def name(self): return "vocabulary_and_diction"
    @property
    def description(self): return "Assesses the sophistication and variety of the vocabulary used."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale from 0 to 100, evaluate the author's use of vocabulary. Is the language precise, varied, and appropriately sophisticated for the topic?"
        return ai_executor.add_test(self.name,  prompt)

class SentenceStructureVarietyTest(TestFunction):
    @property
    def name(self): return "sentence_structure_variety"
    @property
    def description(self): return "Checks for varied and complex sentence structures."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, assess the variety of sentence structures in the essay. Does the author use a mix of simple, compound, and complex sentences to create a more engaging rhythm?"
        return ai_executor.add_test(self.name,  prompt)

class BiasDetectionTest(TestFunction):
    @property
    def name(self): return "bias_detection"
    @property
    def description(self): return "Identifies potential bias or unsupported opinions in the essay."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale from 0 to 100, evaluate the essay for objectivity and bias. Does the author present a balanced view, or does the text rely on unsupported opinions and emotionally charged language?"
        return ai_executor.add_test(self.name,  prompt)

class ExampleClarityTest(TestFunction):
    @property
    def name(self): return "example_clarity"
    @property
    def description(self): return "Evaluates how clear and illustrative the examples are."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, how clear and effective are the examples used in the essay? Do they genuinely illustrate the points the author is trying to make?"
        return ai_executor.add_test(self.name,  prompt)

class LogicalFallacyCheckTest(TestFunction):
    @property
    def name(self): return "logical_fallacy_check"
    @property
    def description(self): return "Checks for common logical fallacies in the arguments."
    @property
    def parameter_description(self):
        return { "essay_content": "The text of the essay to analyze." }
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "On a scale of 0 to 100, evaluate the essay for logical fallacies (e.g., ad hominem, straw man, false dilemma). How sound is the reasoning throughout the text?"
        return ai_executor.add_test(self.name,  prompt)


# ===============================================================
# endregion
# ===============================================================


class EssayGraderTemplate(Template):

    def __init__(self):
        super().__init__()
        self.executor = ai_executor
        self.tests = {
            # Original Tests
            "clarity_and_cohesion": ClarityAndCohesionTest(),
            "grammar_and_spelling": GrammarAndSpellingTest(),
            "argument_strength": ArgumentStrengthTest(),
            "thesis_statement": ThesisStatementTest(),
            "adherence_to_prompt": AdherenceToPromptTest(),
            "originality_and_plagiarism": OriginalityAndPlagiarismTest(),

            # 10 New Advanced Tests
            "topic_connection": TopicConnectionTest(),
            "counterargument_handling": CounterargumentHandlingTest(),
            "introduction_and_conclusion": IntroductionAndConclusionTest(),
            "evidence_quality": EvidenceQualityTest(),
            "tone_and_style": ToneAndStyleTest(),
            "vocabulary_and_diction": VocabularyAndDictionTest(),
            "sentence_structure_variety": SentenceStructureVarietyTest(),
            "bias_detection": BiasDetectionTest(),
            "example_clarity": ExampleClarityTest(),
            "logical_fallacy_check": LogicalFallacyCheckTest(),
        }

    @property
    def template_name(self):
        return "Essay AI Grader"

    @property
    def template_description(self) -> str:
        return "A template for grading essays using AI."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return True

    @property
    def requires_execution_helper(self) -> bool:
        return True

    @property
    def execution_helper(self):
        return self.executor

    def get_test(self, name: str) -> TestFunction:
        """
        Retrieves a specific test function instance from the template.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function