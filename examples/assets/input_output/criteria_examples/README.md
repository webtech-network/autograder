# Criteria Examples

Sample grading criteria configurations demonstrating various features of the Autograder criteria tree system.

## Files

### 1_base_only_simple.json
**Simple test suite with only base tests**
- No subjects, no bonus/penalty
- Straightforward pass/fail grading
- Good starting point for basic assignments

### 2_base_and_bonus.json
**Base tests with bonus points**
- Students can score >100% with extra credit
- Demonstrates bonus test categories
- Useful for assignments with optional challenges

### 3_base_bonus_penalty.json
**Full category support**
- Base tests (required functionality)
- Bonus tests (extra credit)
- Penalty tests (deductions for errors)
- Comprehensive grading strategy

### 4_with_subjects.json
**Tests organized into named subject groups**
- Subjects have individual weights
- Better organization for complex assignments
- Clear breakdown by topic or feature

### 5_nested_subjects.json
**Hierarchical structure with nested subjects**
- Complex rubrics with multiple levels
- Subjects within subjects
- Advanced grading scenarios

## Usage

Load these examples in the testing dashboard to see how different criteria structures work:

1. Open the dashboard at http://localhost:8080
2. Navigate to the Configuration Creator page
3. Click "Load Example"
4. Select one of these files
5. View the visual tree representation
6. Submit code to see how grading works

## Schema

All criteria files follow the standard criteria tree schema with:
- Root subject (optional)
- Tests (base, bonus, penalty)
- Points and weights
- Nested subjects (optional)

