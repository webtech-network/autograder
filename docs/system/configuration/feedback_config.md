# Feedback Configuration

## Overview

The **feedback.json** file controls how feedback is presented to students after grading. It customizes the appearance, tone, and content of the feedback report based on your preferences and the chosen feedback mode.

The autograder supports two distinct feedback modes:
- **Default Mode**: Structured, report-based feedback
- **AI Mode**: Context-aware, personalized feedback powered by OpenAI

---

## Feedback Modes

### Default Feedback Mode

The default mode generates feedback by:
1. Collecting all `TestResult` objects from the grading process
2. Extracting the report string from each test (explains pass/fail)
3. Formatting them in a structured, readable format
4. Displaying failed tests prominently

**Characteristics:**
- ✅ Fast and deterministic
- ✅ No external API calls required
- ✅ Consistent formatting
- ✅ Shows exactly what tests passed/failed

### AI Feedback Mode

The AI mode generates enhanced feedback by:
1. Reading the test report and submission files
2. Analyzing the student's code in context
3. Creating feedback with **cause and consequence** analysis
4. Providing personalized, natural language explanations

**Characteristics:**
- ✅ Context-aware and personalized
- ✅ Explains *why* tests failed and *what* the impact is
- ✅ Can provide hints or solutions
- ⚠️ Requires OpenAI API key
- ⚠️ Slightly slower due to API calls

---

## Configuration Structure

The feedback configuration has three main sections:

```json
{
  "general": { ... },    // Common settings for both modes
  "ai": { ... },         // AI-specific settings
  "default": { ... }     // Default mode-specific settings
}
```

---

## General Configuration

The `general` section contains preferences that apply to **both feedback modes**.

### Available Options

| Option | Type | Description |
|--------|------|-------------|
| `report_title` | string | The title displayed at the top of the feedback report |
| `show_score` | boolean | Whether to display the final score in the feedback |
| `show_passed_tests` | boolean | Whether to include tests that passed (not just failures) |
| `add_report_summary` | boolean | Whether to include a summary section at the end |
| `online_content` | array | List of learning resources linked to specific tests |

### Online Content

The `online_content` array allows you to recommend learning resources when specific tests fail. Each entry contains:

- **`url`**: Link to the learning resource
- **`description`**: Brief explanation of what the resource teaches
- **`linked_tests`**: Array of test names that trigger this recommendation

**Example:**
```json
"online_content": [
  {
    "url": "https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model",
    "description": "Guide on DOM manipulation for creating dynamic content.",
    "linked_tests": [
      "js_uses_dom_manipulation",
      "check_dynamic_content"
    ]
  }
]
```

When any of the linked tests fail, the resource will be recommended in the feedback.

---

## AI Configuration

The `ai` section contains settings specific to AI-powered feedback generation.

### Available Options

| Option | Type | Description |
|--------|------|-------------|
| `provide_solutions` | string | How much help to provide: `"none"`, `"hint"`, or `"full"` |
| `feedback_tone` | string | The tone of the AI's feedback (e.g., "friendly", "professional") |
| `feedback_persona` | string | The character/role the AI should adopt |
| `assignment_context` | string | Full description of the assignment's goals and requirements |
| `extra_orientations` | string | Additional guidance for the AI on what to focus on |
| `submission_files_to_read` | array | List of student files the AI should analyze |

### Detailed Explanation

#### `provide_solutions`
Controls how much help the AI gives for failed tests:
- **`"none"`**: Only describes the problem
- **`"hint"`**: Provides guidance without giving away the answer
- **`"full"`**: Shows complete solutions or fixes

#### `feedback_tone`
Shapes the AI's communication style:
- Examples: `"friendly and encouraging"`, `"professional and concise"`, `"casual and supportive"`
- Can include multiple attributes: `"amigável, encorajador e direto ao ponto"`

#### `feedback_persona`
Defines who the AI is pretending to be:
- Examples:
  - `"A helpful teaching assistant"`
  - `"Code Buddy, an experienced programmer helping you improve"`
  - `"A supportive mentor reviewing your work"`

#### `assignment_context`
A comprehensive description of the assignment that the AI uses to understand the bigger picture:
- What is the assignment about?
- What are the main learning objectives?
- What technologies should be used?
- What is prohibited?

**Example:**
```json
"assignment_context": "The goal of this activity is to create a news portal with two pages: a home page (index.html) displaying a list of news as cards, and a details page (detalhes.html) showing the full content. All content must be loaded dynamically from a data structure in app.js. Frameworks like React, Vue, or Angular are prohibited."
```

#### `extra_orientations`
Specific instructions for what the AI should focus on during analysis:
- Key implementation details
- Common mistakes to look for
- Critical requirements to emphasize

**Example:**
```json
"extra_orientations": "Please focus on: 1. Correct data structure implementation in app.js with id fields. 2. Dynamic card rendering using DOM manipulation. 3. Links pointing to detalhes.html with id in query string. 4. The details page reading the id from URL and displaying the correct item. 5. Verify no JavaScript frameworks were used."
```

#### `submission_files_to_read`
Array of file paths the AI should analyze to provide context-aware feedback:
```json
"submission_files_to_read": [
  "index.html",
  "detalhes.html",
  "css/styles.css",
  "app.js"
]
```

---

## Default Configuration

The `default` section contains settings specific to the default feedback mode.

### Available Options

| Option | Type | Description |
|--------|------|-------------|
| `category_headers` | object | Custom headers for each criteria category (base, bonus, penalty) |

### Category Headers

Customize the section headers for each category in the feedback report:

```json
"category_headers": {
  "base": "✅ Essential Requirements",
  "bonus": "⭐ Extra Points and Best Practices",
  "penalty": "🚨 Points of Attention and Bad Practices"
}
```

Use emojis and descriptive text to make the feedback more engaging and clear.

---

## Complete Example

Here's a full feedback configuration for a dynamic news portal assignment:

```json
{
  "general": {
    "report_title": "Performance Report - Dynamic News Portal",
    "show_score": true,
    "show_passed_tests": true,
    "add_report_summary": true,
    "online_content": [
      {
        "url": "https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model/Introduction",
        "description": "Guide on DOM manipulation for creating dynamic content.",
        "linked_tests": [
          "js_uses_dom_manipulation"
        ]
      },
      {
        "url": "https://developer.mozilla.org/en-US/docs/Web/API/URLSearchParams",
        "description": "Tutorial on using URLSearchParams to read query string parameters from URLs.",
        "linked_tests": [
          "js_uses_query_string_parsing",
          "link_points_to_page_with_query_param"
        ]
      },
      {
        "url": "https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON",
        "description": "Learn how to work with JSON data structures in JavaScript.",
        "linked_tests": [
          "js_has_json_array_with_id"
        ]
      },
      {
        "url": "https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img",
        "description": "Complete guide on using the 'alt' attribute in images for accessibility.",
        "linked_tests": [
          "check_all_images_have_alt"
        ]
      }
    ]
  },
  "ai": {
    "provide_solutions": "hint",
    "feedback_tone": "friendly, encouraging, and straight to the point",
    "feedback_persona": "Code Buddy, a more experienced programmer colleague helping me improve",
    "assignment_context": "The goal of this activity is to create a news portal with two pages: a home page (index.html) that displays a list of news items as cards, and a details page (detalhes.html) that shows the full content of a news article. All content must be loaded dynamically from a data structure (array of objects) in the app.js file. The use of frameworks like React, Vue, or Angular is prohibited.",
    "extra_orientations": "Please focus the analysis on the following points: 1. The correct implementation of the data structure in app.js, ensuring each item has an 'id'. 2. Dynamic rendering of cards in index.html using DOM manipulation. 3. Creating links in each card that point to detalhes.html with the item's 'id' in the query string (e.g., detalhes.html?id=1). 4. The ability of the detalhes.html page to read the 'id' from the URL, find the corresponding item in the data structure, and display its information. 5. Verify that no JavaScript frameworks were used.",
    "submission_files_to_read": [
      "index.html",
      "detalhes.html",
      "css/styles.css",
      "app.js"
    ]
  },
  "default": {
    "category_headers": {
      "base": "✅ Essential Requirements",
      "bonus": "⭐ Extra Points and Best Practices",
      "penalty": "🚨 Points of Attention and Bad Practices"
    }
  }
}
```

---

## Feedback Output Comparison

### Default Mode Output Example
```
=== Performance Report - Dynamic News Portal ===

Final Score: 78/100

✅ Essential Requirements (78/100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ PASSED: js_uses_dom_manipulation
  DOM manipulation methods were found in app.js

✗ FAILED: js_uses_query_string_parsing (0/10 points)
  No URLSearchParams usage detected in the code.

⭐ Extra Points and Best Practices (0/20)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ FAILED: check_all_images_have_alt
  2 images are missing 'alt' attributes.

📚 Recommended Resources:
• URLSearchParams Tutorial: https://developer.mozilla.org/...
  (Related to failed tests: js_uses_query_string_parsing)
```

### AI Mode Output Example
```
=== Performance Report - Dynamic News Portal ===

Final Score: 78/100

Hey there! 👋 You've made solid progress on this news portal project. Let me walk you through what's working and where we can improve.

✅ What's Working Well:
You've successfully implemented DOM manipulation in your app.js file! I can see you're using document.createElement() and appendChild() to dynamically build the news cards. This is exactly the right approach for this assignment.

⚠️ Areas for Improvement:

1. Query String Parsing (Lost 10 points)

   **What happened:** Your detalhes.html page isn't reading the 'id' parameter from the URL.

   **Why it matters:** Without this, users clicking on a news card won't see the correct article details - they'll always see the same content or nothing at all.

   **Hint:** Look into the URLSearchParams API. You can use it like this:
   const urlParams = new URLSearchParams(window.location.search);
   const id = urlParams.get('id');

   Then use that id to find the right article in your data array.

2. Image Accessibility (Bonus opportunity missed)

   **What happened:** Two of your images don't have 'alt' attributes.

   **Why it matters:** Screen readers can't describe these images to visually impaired users. It's both an accessibility and SEO best practice.

   **Hint:** Add descriptive alt text to all <img> tags, like: alt="Breaking news headline photo"

📚 Resources to Help You:
• URLSearchParams Tutorial - This will help you read parameters from URLs
• Image Accessibility Guide - Learn about proper alt text usage

Keep up the great work! You're very close to a complete solution. 💪
```

---

## Best Practices

### 1. **Craft Clear Assignment Context (AI Mode)**
- Provide comprehensive background on the assignment
- Include learning objectives
- Mention what is/isn't allowed
- The more context, the better the AI feedback

### 2. **Use Specific Extra Orientations (AI Mode)**
- List the key points you want the AI to focus on
- Mention common mistakes students make
- Number your points for clarity

### 3. **Choose Appropriate Solution Level (AI Mode)**
- Use `"hint"` for learning-focused feedback
- Use `"none"` if you want students to struggle productively
- Use `"full"` only for final submissions or when time is limited

### 4. **Link Relevant Resources**
- Attach online content to specific tests
- Use official documentation (MDN, official tutorials)
- Provide descriptions that explain what the resource teaches

### 5. **Customize Category Headers (Default Mode)**
- Use emojis to make sections visually distinct
- Use language that resonates with your students
- Keep headers concise but descriptive

### 6. **Balance Information Display**
- Consider if showing passed tests is helpful or overwhelming
- Always show score unless you have a specific pedagogical reason not to
- Use report summaries for longer assignments

### 7. **Limit Files to Read (AI Mode)**
- Only include files relevant to the grading
- More files = longer processing time and higher API costs
- Focus on files where failures occurred

---

## Configuration Tips by Use Case

### For Beginners
```json
{
  "general": {
    "show_score": true,
    "show_passed_tests": true  // Encourages by showing successes
  },
  "ai": {
    "provide_solutions": "hint",
    "feedback_tone": "encouraging, patient, and supportive",
    "feedback_persona": "A friendly tutor who celebrates progress"
  }
}
```

### For Advanced Students
```json
{
  "general": {
    "show_score": true,
    "show_passed_tests": false  // Focus on what needs improvement
  },
  "ai": {
    "provide_solutions": "none",
    "feedback_tone": "direct, technical, and challenging",
    "feedback_persona": "A code reviewer at a tech company"
  }
}
```

### For Quick Feedback (Default Mode)
```json
{
  "general": {
    "show_score": true,
    "show_passed_tests": false,
    "add_report_summary": false
  },
  "default": {
    "category_headers": {
      "base": "❌ Failed Requirements",
      "bonus": "⭐ Bonus",
      "penalty": "⚠️ Penalties"
    }
  }
}
```

---

## Related Documentation

- **[Criteria Configuration](./criteria_config.md)** - Define what to test
- **[Setup Configuration](./setup_config.md)** - Configure the grading environment
- **[Getting Started](../getting_started.md)** - Overview of the autograder system

---

## Summary

The feedback configuration:
- ✅ Controls how feedback is presented to students
- ✅ Supports two modes: Default (fast, structured) and AI (personalized, context-aware)
- ✅ Allows customization of tone, persona, and solution detail (AI mode)
- ✅ Links learning resources to specific failed tests
- ✅ Customizes report structure and visibility (both modes)
- ✅ Helps create feedback that matches your teaching style and student needs

Well-configured feedback transforms grading from just a score into a powerful learning tool! 🎓
