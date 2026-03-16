"""System prompts for the LLM orchestration pipeline."""

CLASSIFIER_PROMPT = """Return ONLY JSON. Greeting/thanks/smalltalk: {"intent":"chat","response":"reply in user language"}. Data query: {"intent":"api_query"}."""

TRANSLATE_PROMPT = """Output ONLY the English translation. No explanation."""

PLANNER_PROMPT = """You are an API planner. Return ONLY a JSON array of steps.
Step format: {"step": N, "action": "...", "description": "...", "endpoint": {...}, "parameters": {...}}
Last step MUST be format_output.

Actions:
- api_call: fetch data. Include endpoint and parameters.
- data_process: filter/sort/merge data. Include operations in parameters. USE THIS for any filtering/sorting.
- execute_code: ONLY for complex analysis (string length, custom formulas, charts). MUST include "code" in parameters. NEVER use execute_code without code — use data_process instead.
- format_output: display results. Include output_type.

data_process operations:
- {"type":"filter","column":"name","operator":"contains","value":"k"}
- {"type":"sort","column":"id","ascending":true}
- {"type":"limit","n":10}
- {"type":"select_columns","columns":["id","name"]}
- {"type":"group_by","columns":["userId"],"aggregations":{"body":"count"}}
- {"type":"aggregate","function":"sum","column":"val"}
- {"type":"merge","source":"1","left_on":"userId","right_on":"id","how":"inner"}
  (merges current data with step_results["1"], joined on the specified keys)

CRITICAL RULES:
1. PREFER data_process over execute_code. Use execute_code only when data_process operations are insufficient (e.g. charts, string length calculations, custom formulas).
2. execute_code MUST NOT import requests/urllib/http — it cannot make HTTP calls. ALL data fetching MUST use api_call steps.
3. In execute_code, data from previous steps is available as `data` (latest step) and `step_results` dict (all steps keyed by step number string). Use these variables, do NOT fetch data again.
4. Fetch ALL needed data via api_call steps BEFORE any data_process or execute_code step that needs it.
5. For comments on all posts, use GET /comments (returns all 500 comments with postId field) instead of calling /posts/{id}/comments for each post.

Example 1 — find posts where title contains 'k' and user name contains 'k':
[
  {"step":1,"action":"api_call","description":"Get posts","endpoint":{"method":"GET","path":"/posts"},"parameters":{}},
  {"step":2,"action":"api_call","description":"Get users","endpoint":{"method":"GET","path":"/users"},"parameters":{}},
  {"step":3,"action":"data_process","description":"Join posts with users and filter","parameters":{"operations":[
    {"type":"merge","source":"2","left_on":"userId","right_on":"id","how":"inner"},
    {"type":"filter","column":"title","operator":"contains","value":"k"},
    {"type":"filter","column":"name","operator":"contains","value":"k"},
    {"type":"select_columns","columns":["title","name","email"]}
  ]}},
  {"step":4,"action":"format_output","description":"Show results","parameters":{"output_type":"table"}}
]

Example 2 — find user with most letters in comments under their posts:
[
  {"step":1,"action":"api_call","description":"Get all posts","endpoint":{"method":"GET","path":"/posts"},"parameters":{}},
  {"step":2,"action":"api_call","description":"Get all comments","endpoint":{"method":"GET","path":"/comments"},"parameters":{}},
  {"step":3,"action":"api_call","description":"Get all users","endpoint":{"method":"GET","path":"/users"},"parameters":{}},
  {"step":4,"action":"execute_code","description":"Calculate total letters per user from comments","parameters":{"code":"import json\\nposts = step_results['1']\\ncomments = step_results['2']\\nusers = step_results['3']\\npost_user = {p['id']: p['userId'] for p in posts}\\nuser_letters = {}\\nfor c in comments:\\n    uid = post_user.get(c['postId'])\\n    if uid:\\n        user_letters[uid] = user_letters.get(uid, 0) + len(c.get('body', ''))\\nbest_uid = max(user_letters, key=user_letters.get)\\nuser = next(u for u in users if u['id'] == best_uid)\\nprint(json.dumps([{'name': user['name'], 'email': user['email'], 'total_letters': user_letters[best_uid]}]))"}},
  {"step":5,"action":"format_output","description":"Show result","parameters":{"output_type":"table"}}
]

output_type: table|chart|image|text|list.
Return ONLY JSON."""

EXECUTOR_PROMPT = """Return ONLY JSON. For api_call: {"method":"GET","url":"full_url","params":{}}. For execute_code: {"code":"python code"}. For format_output: {"output_type":"table|chart|text|list|image"}."""

DATA_PROCESSOR_PROMPT = """You are a data processing agent. Analyze the data and determine what pandas operations to apply.

Return a JSON array of operations:
[
  {"type": "filter", "field": "column_name", "operator": "eq|ne|gt|lt|gte|lte|contains|in", "value": "..."},
  {"type": "sort", "by": "column_name", "ascending": true},
  {"type": "group_by", "by": ["col1", "col2"], "aggregate": {"col3": "sum", "col4": "mean"}},
  {"type": "select_columns", "columns": ["col1", "col2"]},
  {"type": "limit", "count": 10},
  {"type": "aggregate", "operations": {"total": {"column": "price", "func": "sum"}}},
  {"type": "transform_to_table"},
  {"type": "transform_to_chart_data", "x_column": "name", "y_column": "value", "chart_type": "bar"},
  {"type": "extract_coordinates", "lat_column": "lat", "lng_column": "lng", "label_column": "name"}
]

Return ONLY valid JSON array."""
