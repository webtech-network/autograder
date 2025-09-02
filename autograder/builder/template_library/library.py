class TemplateLibrary:
    @staticmethod
    def get_template(template_name: str):
        if template_name == "web dev":
            from autograder.builder.template_library.templates.web_dev import WebDevLibrary
            return WebDevLibrary()
        return None
