from autograder.services.template_library_service import TemplateLibraryService


def test_template_info_exposes_stable_identifier_and_display_name():
    TemplateLibraryService.reset_instance()
    service = TemplateLibraryService.get_instance()

    info = service.get_template_info("static_analysis")

    assert info["identifier"] == "static_analysis"
    assert isinstance(info["name"], str)
    assert info["name"]
