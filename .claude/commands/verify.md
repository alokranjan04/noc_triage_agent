Verify the project against its specs. Do not change any code.

1. Run `uv run pytest -q` and `uv run ruff check .` and show results.
2. For every REQ id in specs/01-requirements.md, find the test(s) or eval case(s) that cover it (search tests/ and evals/cases.yaml). Print a table: REQ id | covered by | status.
3. List REQs with no coverage.
4. Check that specs/03-tasks.md ticks match reality (e.g. a ticked task whose "Done when" check now fails).
5. Summarize: what is done, what is missing, what to do next.
