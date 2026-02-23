from sandbox_manager.models.sandbox_models import ResponseCategory, Language


def classify_output(stdout: str, stderr: str, exit_code: int, language: Language) -> ResponseCategory:
    if exit_code == 0:
        return ResponseCategory.SUCCESS

    if exit_code == 137:  # Common Docker OOM/Killed exit code
        return ResponseCategory.TIMEOUT

    # Detect compilation errors (assuming your pipeline separates build/run)
    # or detect them via stderr keywords
    compilation_keywords = ["error:", "javac", "g++"]
    if any(k in stderr.lower() for k in compilation_keywords) and exit_code != 0:
        return ResponseCategory.COMPILATION_ERROR

    # Detect Runtime Errors
    runtime_indicators = {
        Language.PYTHON: ["Traceback (most recent call last):", "Error:"],
        Language.JAVA: ["Exception in thread", "java.lang."],
        Language.NODE: ["ReferenceError:", "TypeError:", "Uncaught"],
        Language.CPP: ["segmentation fault", "core dumped"]
    }

    indicators = runtime_indicators.get(language, [])
    if any(ind in stderr for ind in indicators):
        return ResponseCategory.RUNTIME_ERROR

    return ResponseCategory.SYSTEM_ERROR