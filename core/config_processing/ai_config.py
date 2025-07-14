import json
from typing import List


class AiConfig:
    def __init__(self,system_prompt: str, user_prompt: str, files: list[str],learning_resources = None):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.files = files
        self.learning_resources = learning_resources

    @classmethod
    def parse_config(cls):
        with open("ai-feedback.json", "r", encoding="utf-8") as file:
            config = json.load(file)
            prompts = config["prompts"]
            system_prompt = prompts.get("system_prompt", "")
            user_prompt = prompts.get("user_prompt", "")
            files = config.get("submission_files", [])
            learning_resources = []
            resources = config.get("learning_resources")
            for subject in resources:
                learning_resources.append(LearningResource.parse_resource(resources.get(subject), subject))
            return cls(system_prompt, user_prompt, files, learning_resources)



class LearningResource:
    def __init__(self, subject, resources):
        self.subject = subject
        self.resources = resources
    @classmethod
    def parse_resource(cls,contents, subject):
        resources = []
        for resource in contents:
            resources.append(resource)
        return cls(subject,resources)

    def __str__(self):
        return f"LearningResource(subject={self.subject}, resources={self.resources})"

