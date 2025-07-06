import json
try:
  with open('./test-results.json', 'r') as file:
    data = json.load(file)
    
  print("Here is the JSON data:", data)
  print("Theme:", data['theme'])

except FileNotFoundError:
  print("Error: The file was not found.")
except json.JSONDecodeError:
  print("Error: The file is not a valid JSON.")