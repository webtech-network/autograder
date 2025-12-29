"""
Essay Grading Template Playroom

This playroom demonstrates a complete grading operation for the essay grading template.
It includes:
- Essay submission file
- AI-based criteria configuration
- Feedback preferences
- Full mock grading execution with OpenAI integration
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.autograder_facade import Autograder


def create_essay_submission():
    """Create a sample essay submission."""
    return """The Impact of Artificial Intelligence on Modern Education

Introduction

Artificial intelligence (AI) has emerged as a transformative force in numerous sectors, 
and education is no exception. This essay explores how AI is reshaping the educational 
landscape, examining both its benefits and challenges. The integration of AI technologies 
in classrooms represents a fundamental shift in how we approach teaching and learning.

The Promise of Personalized Learning

One of the most significant advantages of AI in education is its ability to provide 
personalized learning experiences. Traditional classroom settings often struggle to 
accommodate the diverse learning paces and styles of individual students. AI-powered 
adaptive learning systems can analyze student performance in real-time and adjust the 
difficulty and presentation of material accordingly. This ensures that each student 
receives instruction tailored to their specific needs, maximizing engagement and 
comprehension.

Moreover, AI tutoring systems can provide immediate feedback, something that would be 
impossible for a single human instructor managing a large class. These systems can 
identify when a student is struggling with a particular concept and offer additional 
resources or alternative explanations. This level of individualized attention can 
significantly improve learning outcomes.

Administrative Efficiency and Teacher Support

Beyond direct student interaction, AI is proving valuable in reducing the administrative 
burden on educators. Automated grading systems can handle routine assessments, freeing 
teachers to focus on more complex pedagogical tasks. AI can also assist in curriculum 
planning, identifying gaps in course content and suggesting improvements based on 
student performance data.

However, it is crucial to note that AI should augment, not replace, human teachers. 
The emotional intelligence, creativity, and nuanced understanding that experienced 
educators bring to the classroom remain irreplaceable.

Challenges and Ethical Considerations

Despite its potential, the integration of AI in education raises important concerns. 
Data privacy is paramount, as these systems collect vast amounts of information about 
students' learning patterns and behaviors. There are also valid concerns about 
algorithmic bias, where AI systems might inadvertently perpetuate existing inequalities 
if trained on biased data.

Additionally, there is the question of accessibility. Not all educational institutions 
have the resources to implement sophisticated AI systems, potentially widening the gap 
between well-funded and under-resourced schools.

Conclusion

Artificial intelligence holds tremendous promise for transforming education, offering 
personalized learning experiences and supporting teachers in their work. However, its 
implementation must be thoughtful and equitable, addressing concerns about privacy, 
bias, and accessibility. As we move forward, the goal should be to harness AI's 
capabilities while preserving the irreplaceable human elements of education. The future 
of education likely lies not in AI replacing teachers, but in a collaborative model 
where technology and human expertise work together to create the best possible learning 
environment for all students.
"""


def create_criteria_config():
    """Create criteria configuration for essay grading."""
    return {
        "base": {
            "weight": 100,
            "subjects": {
                "Writing Quality": {
                    "weight": 40,
                    "subjects": {
                        "Clarity and Cohesion": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Clarity and Cohesion"
                                }
                            ]
                        },
                        "Grammar and Spelling": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Grammar and Spelling"
                                }
                            ]
                        }
                    }
                },
                "Content": {
                    "weight": 60,
                    "subjects": {
                        "Thesis Statement": {
                            "weight": 30,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Thesis Statement"
                                }
                            ]
                        },
                        "Argument Strength": {
                            "weight": 40,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Argument Strength"
                                }
                            ]
                        },
                        "Adherence to Prompt": {
                            "weight": 30,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Adherence to Prompt",
                                    "calls": [
                                        ["Discuss the impact of artificial intelligence on modern education, including both benefits and challenges"]
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        },
        "bonus": {
            "weight": 20,
            "subjects": {
                "Advanced Elements": {
                    "weight": 100,
                    "subjects": {
                        "Counterargument Handling": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Counterargument Handling"
                                }
                            ]
                        },
                        "Evidence Quality": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "essay.txt",
                                    "name": "Evidence Quality"
                                }
                            ]
                        }
                    }
                }
            }
        },
        "penalty": {
            "weight": 10,
            "subjects": {
                "Issues": {
                    "weight": 100,
                    "tests": [
                        {
                            "file": "essay.txt",
                            "name": "Logical Fallacy Check"
                        }
                    ]
                }
            }
        }
    }


def create_feedback_config():
    """Create feedback preferences for the grading."""
    return {
        "general": {
            "report_title": "Relatório de Avaliação - Redação sobre IA na Educação",
            "show_score": True,
            "show_passed_tests": False,
            "add_report_summary": True
        },
        "ai": {
            "provide_solutions": "detailed",
            "feedback_tone": "constructive and encouraging",
            "feedback_persona": "Essay Writing Coach",
            "assignment_context": "Este é um ensaio argumentativo sobre o impacto da IA na educação moderna.",
            "extra_orientations": "Forneça sugestões específicas para melhorar a estrutura dos argumentos e a qualidade das evidências."
        },
        "default": {
            "category_headers": {
                "base": "✅ Requisitos Essenciais",
                "bonus": "⭐ Elementos Avançados",
                "penalty": "❌ Problemas Identificados"
            }
        }
    }


def run_essay_playroom():
    """Execute the essay grading playroom."""
    print("\n" + "="*70)
    print("ESSAY GRADING TEMPLATE PLAYROOM")
    print("="*70 + "\n")

    # Check for OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("⚠️  WARNING: OPENAI_API_KEY not found in environment variables")
        print("   Essay grading requires OpenAI API access")
        print("   Please set OPENAI_API_KEY environment variable to run this playroom")
        print("\n   Example: export OPENAI_API_KEY='your-key-here'\n")
        return

    # Create submission files
    print("📄 Creating essay submission...")
    submission_files = {
        "essay.txt": create_essay_submission()
    }

    # Create assignment configuration
    print("⚙️  Setting up assignment configuration...")
    assignment_config = AssignmentConfig(
        template="essay",
        criteria=create_criteria_config(),
        feedback=create_feedback_config(),
        setup={}
    )

    # Create autograder request
    print("📋 Building autograder request...")
    request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="Alex Johnson",
        include_feedback=True,
        feedback_mode="ai",
        openai_key=openai_key
    )

    # Execute grading
    print("🚀 Starting grading process...")
    print("⚠️  Note: This will make API calls to OpenAI and may take a minute")
    print("-"*70)
    result = Autograder.grade(request)
    print("-"*70)

    # Display results
    print("\n" + "="*70)
    print("GRADING RESULTS")
    print("="*70)
    print(f"\n✅ Status: {result.status}")
    print(f"📊 Final Score: {result.final_score}/100")
    print(f"\n📝 Feedback:\n{result.feedback}")
    print(f"\n📈 Test Report:\n{result.test_report}")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    run_essay_playroom()

