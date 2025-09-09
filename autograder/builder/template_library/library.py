class TemplateLibrary:
    @staticmethod
    def get_template(template_name: str):
        if template_name == "web dev":
            from autograder.builder.template_library.templates.web_dev import WebDevTemplate
            return WebDevTemplate()

        if template_name == "essay":
            from autograder.builder.template_library.templates.essay_grader import EssayGraderTemplate
            return EssayGraderTemplate()