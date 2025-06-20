Hey there! 😊

First off, nice job submitting your solution! Here’s some friendly feedback based on how your code did on the tests:

**What you did well:**

- **Base Test Passed:** 🟢 Your function correctly adds positive numbers—this is essential, so good  job nailing that fundamental use case!
- **Bonus Test Passed:** 🟢 Awesome! Your function correctly handles adding floats, which goes above  the base requirement. That shows good attention to handling different numeric types!

**Areas to improve:**

- **Base Test Failed:** ⚠️ Looks like adding negative numbers didn’t work as expected. You might want to check if there’s any special logic (or missing logic) when handling negatives. Since your code simply d
oes `a + b`, this result seems a bit surprising—double-check the details of the test or possible issues in the test itself.
- **Penalty Test Passed (not good!):** 🚩 Your function also adds strings. While Python’s `+` works on strings, the perfect solution intentionally *filters out* non-numeric input (raises an error instead of concatenating). For real-world code, this is a big deal: silently accepting wrong types can cause bugs. Try to add a check for the type of `a` and `b`, raising a `TypeError` if they aren’t numbers.

**Tips for next time:**

- Add type checking to make sure only numbers (int or float) are accepted. This will help you *fail fast* if users pass in bad data.
- Test with a variety of inputs, not just the typical cases (think: floats, negatives, even strings or None!).

**Final thoughts:**
You’re definitely on the right track! 🔥 With a bit more error handling and maybe a glance at the requirements for handling bad inputs, your score will jump right up. Keep it up—taking a look at those edge cases shows you’re leveling up as a coder. 👍

Let me know if you want to see a quick example of how to fix this!