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


def escolher_produtos(s):
    """Buscador diario de produtos da Shopee com cache em s['shopee_produtos']."""
    from bot import cfg, log, TZ
    import datetime as dt

    hoje = dt.datetime.now(TZ).strftime("%Y-%m-%d")
    if s.get("shopee_produtos_data") == hoje:
        return s.get("shopee_produtos") or []

    if not configurada():
        s["shopee_produtos"] = []
        return []

    try:
        palavras_raw = cfg("SHOPEE_PALAVRAS")
        palavras = [p.strip() for p in palavras_raw.split(",") if p.strip()]
        nota_min = float(cfg("SHOPEE_NOTA_MIN"))
        preco_max = float(cfg("SHOPEE_PRECO_MAX"))
        vendas_min = int(cfg("SHOPEE_VENDAS_MIN"))
        repetir_dias = int(cfg("SHOPEE_REPETIR_DIAS"))

        usados = s.get("shopee_usados", {})
        dt_hoje = dt.datetime.strptime(hoje, "%Y-%m-%d")

        def usado_recente(iid):
            u = usados.get(str(iid))
            if not u:
                return False
            try:
                dt_u = dt.datetime.fromisoformat(str(u)[:10])
                return (dt_hoje - dt_u).days < repetir_dias
            except Exception:
                return False

        encontrados = {}
        for kw in palavras:
            try:
                nos = buscar_produtos(kw, limite=10, ordem=2)
            except Exception as e:
                log(f"Shopee erro ao buscar '{kw}':", str(e)[:150])
                continue

            for node in nos:
                iid = str(node.get("itemId") or "")
                if not iid or iid in encontrados or usado_recente(iid):
                    continue

                try:
                    nota = float(node.get("ratingStar") or 0)
                    preco = float(node.get("priceMin") or node.get("priceDiscountRate") or 0)
                    vendas = int(node.get("sales") or 0)
                    comissao = float(node.get("commissionRate") or 0)
                except Exception:
                    continue

                if nota < nota_min or preco > preco_max or vendas < vendas_min:
                    continue

                encontrados[iid] = {
                    "data": hoje,
                    "itemId": iid,
                    "nome": str(node.get("productName") or ""),
                    "preco": preco,
                    "preço": preco,
                    "nota": nota,
                    "vendas": vendas,
                    "comissao": comissao,
                    "comissão": comissao,
                    "imageUrl": str(node.get("imageUrl") or ""),
                    "offerLink": str(node.get("offerLink") or ""),
                }

        lista = list(encontrados.values())
        lista.sort(key=lambda x: (x["vendas"], x["comissao"]), reverse=True)
        s["shopee_produtos"] = lista
        s["shopee_produtos_data"] = hoje
        return lista
    except Exception as e:
        log("Shopee erro em escolher_produtos:", str(e)[:150])
        s["shopee_produtos"] = s.get("shopee_produtos") or []
        s["shopee_produtos_data"] = hoje
        return s["shopee_produtos"]
