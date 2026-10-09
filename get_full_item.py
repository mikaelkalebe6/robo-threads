import re

for filename in ['melhorias_lidas.md', 'inspiracoes_lidas.md']:
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()

    items = re.split(r'\n## ', '\n' + text)[1:]
    for item in items:
        url = item.split('|', 1)[1].split('\n')[0].strip()

        # let's look for action verbs in the entire item for inspiracoes
        # the user says there are observations asking to download meme, tiktok, research...
        # But wait, maybe the user added comments at the end of some items that don't literally say "Observacao"?

        # Let's just print the last 300 chars of EVERY item to see if there is any Kalebe comment attached to the end.
        print(f"[{filename}] END of {url}:\n{item[-300:]}\n---\n")
