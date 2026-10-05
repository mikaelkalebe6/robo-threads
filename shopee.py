# -*- coding: utf-8 -*-
"""
Conexao com a API de Afiliados da Shopee (Open API, GraphQL). Modulo separado do robo:
- So funciona com os Secrets SHOPEE_APP_ID e SHOPEE_SECRET; sem eles, fica desligado e nao faz nada.
- Nunca grava nem mostra o Secret: ele so entra no calculo da assinatura de cada pedido.
- Qualquer falha vira excecao com mensagem curta; quem chama decide (o robo nunca para por causa da Shopee).
"""
import os, json, time, hashlib, urllib.request, urllib.error

URL = "https://open-api.affiliate.shopee.com.br/graphql"
APP_ID = os.environ.get("SHOPEE_APP_ID", "").strip()
SECRET = os.environ.get("SHOPEE_SECRET", "").strip()


def configurada():
    return bool(APP_ID and SECRET)


def _assinatura(corpo, ts):
    """Regra da Shopee: SHA256(AppId + Timestamp + corpo exato do pedido + Secret)."""
    return hashlib.sha256(f"{APP_ID}{ts}{corpo}{SECRET}".encode("utf-8")).hexdigest()


def _limpo(texto):
    """Garante que nada do Secret escape em mensagem de erro ou log."""
    t = str(texto)
    return t.replace(SECRET, "***") if SECRET else t


def consulta(query, variaveis=None, timeout=20):
    """Manda uma consulta GraphQL assinada e devolve o campo data. Erro da Shopee vira RuntimeError."""
    if not configurada():
        raise RuntimeError("Shopee sem credencial (faltam os Secrets SHOPEE_APP_ID e SHOPEE_SECRET)")
    corpo = json.dumps({"query": query, "variables": variaveis or {}}, ensure_ascii=False, separators=(",", ":"))
    ts = str(int(time.time()))
    req = urllib.request.Request(URL, data=corpo.encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={APP_ID}, Timestamp={ts}, Signature={_assinatura(corpo, ts)}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(_limpo(f"Shopee HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"))
    except Exception as e:
        raise RuntimeError(_limpo(f"Shopee fora do ar: {str(e)[:200]}"))
    if resp.get("errors"):
        e = resp["errors"][0]
        cod = (e.get("extensions") or {}).get("code", "")
        raise RuntimeError(_limpo(f"Shopee recusou ({cod}): {str(e.get('message', ''))[:200]}"))
    return resp.get("data") or {}


def buscar_produtos(palavra, limite=5, ordem=2):
    """Produtos com link de afiliado pronto. ordem segue a tabela da Shopee (ex.: mais vendidos, maior comissao)."""
    q = """query($k:String,$l:Int,$o:Int){productOfferV2(keyword:$k,limit:$l,sortType:$o,page:1){
      nodes{itemId productName offerLink imageUrl priceMin priceMax priceDiscountRate sales ratingStar commissionRate shopName}
      pageInfo{hasNextPage}}}"""
    return (consulta(q, {"k": palavra, "l": limite, "o": ordem}).get("productOfferV2") or {}).get("nodes") or []


def link_afiliado(url, marcadores=None):
    """Link curto de afiliado para qualquer link da Shopee. Marcadores (ate 5) mostram depois qual post vendeu."""
    q = """mutation($u:String!,$s:[String]){generateShortLink(input:{originUrl:$u,subIds:$s}){shortLink}}"""
    sub = [str(m)[:50] for m in (marcadores or [])][:5]
    return ((consulta(q, {"u": url, "s": sub}).get("generateShortLink") or {}).get("shortLink") or "")


def testar_conexao():
    """Pedido pequeno, so de leitura: confirma credencial e assinatura. Nao publica nada."""
    nos = buscar_produtos("garrafa termica", limite=1)
    return f"conectado OK ({len(nos)} produto de teste lido)"
