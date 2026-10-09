with open('jules/2026-10-09-melhorias.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the parts based on the new requirements:
# 1. Update the 'Não aplicar' to 'Já aplicado em parte' for 'Auditoria de Segurança' and 'Requisitos Básicos de Segurança'
# and list what is missing for a GitHub actions bot (workflow permissions, pinned actions by SHA, leak protection in logs, call limits)

text = text.replace(
    '**Recomendação:** Não aplicar (O projeto já trata credenciais via variáveis e o restante não se aplica (não há formulários web).)',
    '**Recomendação:** Já aplicado em parte (O projeto já trata credenciais, mas para um robô no GitHub Actions ainda falta configurar: permissões restritas do workflow, actions fixadas por SHA, proteção contra vazamento de chave nos logs e limites de chamadas de API.)'
)
text = text.replace(
    '| Auditoria de Segurança | Não aplicar |',
    '| Auditoria de Segurança | Já aplicado em parte |'
)

text = text.replace(
    '**Recomendação:** Não aplicar (A maioria dos itens não é aplicável a um script isolado, exceto as variáveis de ambiente que já estão sendo usadas.)',
    '**Recomendação:** Já aplicado em parte (Credenciais fora do código já existem, mas ainda falta implementar no GitHub Actions: permissões do workflow, actions fixadas por SHA, proteção contra vazamento de chave nos logs e limites de chamadas.)'
)
text = text.replace(
    '| Requisitos Básicos de Segurança | Não aplicar |',
    '| Requisitos Básicos de Segurança | Já aplicado em parte |'
)

# Fix Parte 2
# Add the explicit actions requested by the user
parte2 = """Nenhuma inspiração exigiu ação (como baixar, pesquisar, analisar ou estudar perfil)."""
parte2_new = """Link: https://www.instagram.com/p/DdvV4u6EXfg/ (Avô no WhatsApp)
Ação pedida: Pesquisar a técnica de contar história em fios.
Situação: Pendente. Falta pesquisar a técnica.

Link: https://www.instagram.com/p/Dd1gcz1u8aE/ (Cabo de dois plugues)
Ação pedida: Baixar o meme do cabo de dois plugues.
Situação: Pendente. Falta baixar a imagem.

Link: https://vt.tiktok.com/ZSbMk8jMp/ (Celular BlackBerry touch)
Ação pedida: Baixar um vídeo do TikTok para postar.
Situação: Pendente. Falta baixar o vídeo e programar o post."""

text = text.replace(parte2, parte2_new)

# Fix Parte 3
# Add the 3 profiles
parte3 = """Perfil: https://www.threads.com/@isabelanunesantos
Análise: O resumo avaliou apenas a bio e a foto da criadora. Não há posts reais analisados."""
parte3_new = """Perfil: https://www.threads.com/@isabelanunesantos
Análise: O resumo avaliou apenas a bio e a foto da criadora. Não há posts reais analisados.

Perfil: https://www.threads.com/@nalu.pri
Análise: O resumo avaliou apenas a bio e a foto. Não há posts reais analisados.

Perfil: https://www.threads.com/@futurizando
Análise: O resumo focou na imagem de perfil (Olho da Providência) e na descrição da bio. Nenhum post real foi analisado."""

text = text.replace(parte3, parte3_new)

with open('jules/2026-10-09-melhorias.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
