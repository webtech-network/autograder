# Contributing to Autograder

Thank you for your interest in contributing to the Autograder project! We welcome contributions from developers of all skill levels.

## 🚀 Ways to Contribute

- **Bug Reports**: Found a bug? Please open an issue with detailed reproduction steps
- **Feature Requests**: Have an idea for a new feature? We'd love to hear it!
- **Code Contributions**: Submit pull requests for bug fixes, features, or improvements
- **Documentation**: Help improve our docs, examples, and tutorials
- **Testing**: Add test cases or help with testing new features
- **Templates**: Create new grading templates for different assignment types

## 🛠️ Development Setup

### Prerequisites

- Python 3.8 or higher
- Docker (for containerized testing)
- Git

### Local Development

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/autograder.git
   cd autograder
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

4. **Run tests to ensure everything works**
   ```bash
   pytest tests/
   ```

## 📝 Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, well-documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   pytest tests/
   flake8 .  # Code style check
   black .   # Code formatting
   ```

4. **Commit your changes**
   - Use clear, descriptive commit messages
   - Follow the format: `type(scope): description`
   - Examples:
     - `feat(templates): add Python unit testing template`
     - `fix(grader): resolve scoring calculation bug`
     - `docs(readme): update installation instructions`

5. **Submit a pull request**
   - Fill out the pull request template
   - Reference any related issues
   - Request reviews from maintainers

## 🏗️ Code Standards

### Python Style
- Follow PEP 8 style guidelines
- Use `black` for code formatting
- Use `flake8` for linting
- Maximum line length: 88 characters
- Use type hints where possible

### Testing
- Write unit tests for all new functionality
- Maintain test coverage above 80%
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern

### Documentation
- Document all public functions and classes
- Use Google-style docstrings
- Update README.md for significant changes
- Add examples for new features

## 🐛 Reporting Issues

When reporting issues, please include:

1. **Environment details**
   - Python version
   - Operating system
   - Autograder version

2. **Steps to reproduce**
   - Minimal code example
   - Expected vs actual behavior
   - Error messages/logs

3. **Additional context**
   - Screenshots if applicable
   - Related issues or discussions

## 🎯 Project Priorities

Currently, we're focusing on:

1. **Expanding template library** - More assignment types and languages
2. **Improving AI feedback** - Better context awareness and suggestions
3. **Performance optimization** - Faster grading for large classes
4. **Integration support** - More LMS and platform connectors
5. **Mobile experience** - Better responsive design for feedback viewing

## 📋 Code Review Guidelines

### For Contributors
- Keep pull requests focused and atomic
- Respond to feedback promptly
- Be open to suggestions and improvements

### For Reviewers
- Be constructive and respectful
- Focus on code quality, not personal preferences
- Suggest alternatives when requesting changes

## 🏷️ Issue Labels

We use labels to categorize issues:

- `good first issue` - Perfect for newcomers
- `help wanted` - We need community help
- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `documentation` - Docs need attention
- `template` - Related to grading templates

## 📞 Getting Help

- **Discord**: Join our [community Discord](https://discord.gg/autograder)
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers at maintainers@autograder.dev

## 🙏 Recognition

All contributors will be:
- Listed in our CONTRIBUTORS.md file
- Mentioned in release notes for significant contributions
- Invited to our contributor Discord channels

Thank you for helping make education technology more accessible! 🎓
