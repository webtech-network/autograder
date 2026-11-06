"""A correct submission for definition.json: sum the teacher's data file.

The host mounts fixtures under /tmp/app; student files are under /app.
"""
with open("/tmp/app/numbers.txt", encoding="utf-8") as data:
    print(sum(int(line) for line in data if line.strip()))
