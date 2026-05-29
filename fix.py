# Сохрани как fix.py и запусти: python fix.py

with open("jinada_server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Добавляем импорт pandas в админскую функцию
old = "    with tab1:\n        if clients_list:\n            data = []"
new = "    with tab1:\n        if clients_list:\n            import pandas as pd\n            data = []"

content = content.replace(old, new)

with open("jinada_server.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed!")