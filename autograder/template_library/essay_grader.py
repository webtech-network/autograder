from autograder.utils.executors.ai_executor import ai_executor
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult

# ===============================================================
# region: TestFunction Implementations
# ===============================================================

class ClarityAndCohesionTest(TestFunction):
    @property
    def name(self): return "clarity_and_cohesion"
    @property
    def description(self): return "Avalia a clareza geral e o fluxo da redação."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, quão claro e bem estruturado é a redação? Avalie o fluxo lógico dos argumentos, as transições entre parágrafos e a legibilidade geral."
        return ai_executor.add_test(self.name,  prompt)

class GrammarAndSpellingTest(TestFunction):
    @property
    def name(self): return "grammar_and_spelling"
    @property
    def description(self): return "Verifica a redação em busca de erros gramaticais, de ortografia e de pontuação."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a precisão gramatical da redação. Considere ortografia, pontuação, estrutura das frases e concordância verbal."
        return ai_executor.add_test(self.name,  prompt)

class ArgumentStrengthTest(TestFunction):
    @property
    def name(self): return "argument_strength"
    @property
    def description(self): return "Avalia a força e o suporte dos argumentos apresentados."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Avalie a força dos argumentos na redação em uma escala de 0 a 100. As alegações são bem apoiadas com evidências e exemplos? O raciocínio é sólido e persuasivo?"
        return ai_executor.add_test(self.name,  prompt)

class ThesisStatementTest(TestFunction):
    @property
    def name(self): return "thesis_statement"
    @property
    def description(self): return "Avalia a clareza e a eficácia da declaração de tese."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, quão forte e clara é a declaração de tese da redação? Ela apresenta uma posição clara e defensável que é mantida ao longo do texto?"
        return ai_executor.add_test(self.name,  prompt)

class AdherenceToPromptTest(TestFunction):
    @property
    def name(self): return "adherence_to_prompt"
    @property
    def description(self): return "Verifica quão bem a redação aborda os requisitos específicos do tema proposto."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return [
            ParamDescription("prompt_requirements", "O tema específico que a redação deveria abordar.", "string")
        ]
    def execute(self,  prompt_requirements: str) -> TestResult:
        prompt = f"Dado o tema da redação '{prompt_requirements}', quão bem a redação enviada aborda todas as partes da questão? Avalie em uma escala de 0 a 100."
        return ai_executor.add_test(self.name,  prompt)

class OriginalityAndPlagiarismTest(TestFunction):
    @property
    def name(self): return "originality_and_plagiarism"
    @property
    def description(self): return "Uma verificação simplificada de originalidade procurando por frases comuns ou conteúdo copiado."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a originalidade da redação. Embora você não possa realizar uma pesquisa na web, avalie o texto em busca de sinais de conteúdo não original, como frases genéricas ou argumentos excessivamente comuns que possam sugerir plágio."
        return ai_executor.add_test(self.name,  prompt)

class TopicConnectionTest(TestFunction):
    @property
    def name(self): return "topic_connection"
    @property
    def description(self): return "Verifica se a redação estabelece com sucesso uma conexão entre dois tópicos especificados."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return [
            ParamDescription("topic1", "O primeiro tópico.", "string"),
            ParamDescription("topic2", "O segundo tópico.", "string")
        ]
    def execute(self,  topic1: str, topic2: str) -> TestResult:
        prompt = f"Em uma escala de 0 a 100, quão eficazmente a redação estabelece uma conexão significativa entre os conceitos de '{topic1}' e '{topic2}'? Avalie a profundidade e a clareza da ligação."
        return ai_executor.add_test(self.name,  prompt)

class CounterargumentHandlingTest(TestFunction):
    @property
    def name(self): return "counterargument_handling"
    @property
    def description(self): return "Avalia quão bem a redação reconhece e refuta potenciais contra-argumentos."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie quão bem a redação aborda potenciais contra-argumentos. Ele antecipa pontos de vista opostos e fornece refutações bem pensadas?"
        return ai_executor.add_test(self.name,  prompt)

class IntroductionAndConclusionTest(TestFunction):
    @property
    def name(self): return "introduction_and_conclusion"
    @property
    def description(self): return "Avalia a eficácia da introdução e da conclusão da redação."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a qualidade da introdução e da conclusão. A introdução consegue engajar o leitor e apresentar a tese de forma eficaz? A conclusão fornece um resumo sólido e oferece percepções finais?"
        return ai_executor.add_test(self.name,  prompt)

class EvidenceQualityTest(TestFunction):
    @property
    def name(self): return "evidence_quality"
    @property
    def description(self): return "Avalia a relevância e a qualidade das evidências usadas para apoiar as alegações."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a qualidade das evidências usadas na redação. As evidências são relevantes, críveis e suficientes para apoiar os argumentos principais?"
        return ai_executor.add_test(self.name,  prompt)

class ToneAndStyleTest(TestFunction):
    @property
    def name(self): return "tone_and_style"
    @property
    def description(self): return "Avalia se o tom e o estilo de escrita da redação são apropriados para o tópico e o público."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return [
            ParamDescription("expected_tone", "O tom esperado (ex: formal, persuasivo, objetivo).", "string")
        ]
    def execute(self,  expected_tone: str) -> TestResult:
        prompt = f"Em uma escala de 0 a 100, a redação mantém um tom e estilo '{expected_tone}' apropriados? Avalie a voz do autor, a escolha de palavras e o profissionalismo geral."
        return ai_executor.add_test(self.name,  prompt)

class VocabularyAndDictionTest(TestFunction):
    @property
    def name(self): return "vocabulary_and_diction"
    @property
    def description(self): return "Avalia a sofisticação e a variedade do vocabulário utilizado."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie o uso de vocabulário pelo autor. A linguagem é precisa, variada e apropriadamente sofisticada para o tópico?"
        return ai_executor.add_test(self.name,  prompt)

class SentenceStructureVarietyTest(TestFunction):
    @property
    def name(self): return "sentence_structure_variety"
    @property
    def description(self): return "Verifica a presença de estruturas de frase variadas e complexas."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a variedade das estruturas de frase na redação. O autor usa uma mistura de frases simples, compostas e complexas para criar um ritmo mais envolvente?"
        return ai_executor.add_test(self.name,  prompt)

class BiasDetectionTest(TestFunction):
    @property
    def name(self): return "bias_detection"
    @property
    def description(self): return "Identifica potencial viés ou opiniões não suportadas na redação."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a objetividade e o viés da redação. O autor apresenta uma visão equilibrada, ou o texto se baseia em opiniões não suportadas e linguagem emocionalmente carregada?"
        return ai_executor.add_test(self.name,  prompt)

class ExampleClarityTest(TestFunction):
    @property
    def name(self): return "example_clarity"
    @property
    def description(self): return "Avalia quão claros e ilustrativos são os exemplos."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, quão claros e eficazes são os exemplos usados na redação? Eles realmente ilustram os pontos que o autor está tentando defender?"
        return ai_executor.add_test(self.name,  prompt)

class LogicalFallacyCheckTest(TestFunction):
    @property
    def name(self): return "logical_fallacy_check"
    @property
    def description(self): return "Verifica a presença de falácias lógicas comuns nos argumentos."
    @property
    def required_file(self): return "Essay"
    @property
    def parameter_description(self):
        return []
    def execute(self,  *args, **kwargs) -> TestResult:
        prompt = "Em uma escala de 0 a 100, avalie a redação em busca de falácias lógicas (ex: ad hominem, espantalho, falso dilema). Quão sólido é o raciocínio ao longo do texto?"
        return ai_executor.add_test(self.name,  prompt)


# ===============================================================
# endregion
# ===============================================================


class EssayGraderTemplate(Template):

    def __init__(self, clean=False):
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
        return "Corretor de Redações com IA"

    @property
    def template_description(self) -> str:
        return "Um modelo para corrigir redações usando IA."

    @property
    def requires_pre_executed_tree(self) -> bool:
        return True

    @property
    def requires_execution_helper(self) -> bool:
        return True

    @property
    def execution_helper(self):
        return self.executor

    def stop(self):
        self.executor.stop()

    def get_test(self, name: str) -> TestFunction:
        """
        Recupera uma instância de função de teste específica do modelo.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Teste '{name}' não encontrado no modelo '{self.template_name}'.")
        return test_function
