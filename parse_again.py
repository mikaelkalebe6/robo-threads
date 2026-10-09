import re

with open('inspiracoes_lidas.md', 'r', encoding='utf-8') as f:
    text = f.read()

items = re.split(r'\n## ', '\n' + text)[1:]
for item in items:
    print(item.split('|')[1].strip())
