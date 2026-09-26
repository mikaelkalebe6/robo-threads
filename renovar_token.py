# -*- coding: utf-8 -*-
"""Troca o token curto por um de 60 dias (se precisar) e renova o token. Grava em novo_token.txt."""
import os, json, sys, urllib.request, urllib.parse, urllib.error

tok = os.environ.get("THREADS_TOKEN", "").strip()
secret = os.environ.get("THREADS_APP_SECRET", "").strip()
if not tok:
    sys.exit("Falta THREADS_TOKEN")


def get(url, params):
    try:
        with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print("Aviso:", e.code, e.read().decode()[:300])
        return {}


novo = None
if secret:  # token curto (1 hora) -> longo (60 dias)
    novo = get("https://graph.threads.net/access_token",
               {"grant_type": "th_exchange_token", "client_secret": secret, "access_token": tok}).get("access_token")
    if novo:
        print("Token trocado por um de 60 dias.")
if not novo:  # token longo -> renova por mais 60 dias
    novo = get("https://graph.threads.net/refresh_access_token",
               {"grant_type": "th_refresh_token", "access_token": tok}).get("access_token")
    if novo:
        print("Token renovado por mais 60 dias.")
if not novo:
    sys.exit("Nao consegui renovar. Gere um token novo no painel da Meta e cole no segredo THREADS_TOKEN.")
print(f"::add-mask::{novo}")
open("novo_token.txt", "w").write(novo)
