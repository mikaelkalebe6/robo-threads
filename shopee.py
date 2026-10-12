# -*- coding: utf-8 -*-
"""
Conexao com a API de Afiliados da Shopee (Open API, GraphQL). Modulo separado do robo:
- So funciona com os Secrets SHOPEE_APP_ID e SHOPEE_SECRET; sem eles, fica desligado e nao faz nada.
- Nunca grava nem mostra o Secret: ele so entra no calculo da assinatura de cada pedido.
- Qualquer falha vira excecao com mensagem curta; quem chama decide (o robo nunca para por causa da Shopee).
"""
import os, re, json, time, hashlib, urllib.request, urllib.error, urllib.parse

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


CAMPANHAS_ARQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campanhas", "campanhas.json")


def campanhas_api(limite=15):
    """Campanhas da Shopee Afiliados no ar (shopeeOfferV2, maior comissao primeiro). Erro vira excecao curta."""
    q = """query($l:Int){shopeeOfferV2(sortType:2,page:1,limit:$l){
      nodes{offerName commissionRate periodStartTime periodEndTime offerType}}}"""
    nos = (consulta(q, {"l": limite}).get("shopeeOfferV2") or {}).get("nodes") or []
    agora = time.time()
    saida = []
    for n in nos:
        try:
            ini, fim = int(n.get("periodStartTime") or 0), int(n.get("periodEndTime") or 0)
        except Exception:
            ini, fim = 0, 0
        if (ini and ini > agora) or (fim and fim < agora):
            continue
        saida.append({"nome": str(n.get("offerName") or "")[:80], "comissao": n.get("commissionRate"),
                      "fim": fim, "tipo": n.get("offerType")})
    return saida


def _quando(v, fim_do_dia=False):
    """'AAAA-MM-DD' ou 'AAAA-MM-DDTHH:MM' (horario de Manaus) em timestamp."""
    v = str(v or "").strip()
    if not v:
        return None
    import datetime as dt
    try:
        d = dt.datetime.fromisoformat(v) if "T" in v else dt.datetime.fromisoformat(v + ("T23:59" if fim_do_dia else "T00:00"))
        return d.replace(tzinfo=dt.timezone(dt.timedelta(hours=-4))).timestamp()
    except Exception:
        return None


def campanhas_arquivo():
    """Campanhas escolhidas pelo Claude (campanhas/campanhas.json): so as com "usar": true e no periodo."""
    try:
        dados = json.load(open(CAMPANHAS_ARQ, encoding="utf-8"))
    except Exception:
        return [], ""
    bruto = json.dumps(dados, sort_keys=True)
    agora = time.time()
    ativas = []
    for c in dados.get("campanhas", []) if isinstance(dados, dict) else []:
        ini, fim = _quando(c.get("inicio")), _quando(c.get("fim"), True)
        if c.get("usar") and (ini is None or ini <= agora) and (fim is None or agora <= fim):
            ativas.append({"nome": str(c.get("nome") or "")[:30], "palavras": [p.strip() for p in c.get("palavras", []) if str(p).strip()][:6],
                           "peso": float(c.get("peso") or 1.3)})
    return ativas, hashlib.md5(bruto.encode()).hexdigest()[:10]


def sub_id(valor):
    """A Shopee so aceita letras e numeros no subId: limpa e corta em 50."""
    import re
    return re.sub(r"[^A-Za-z0-9]", "", str(valor))[:50] or "x"


def link_afiliado(url, marcadores=None):
    """Link curto de afiliado para qualquer link da Shopee. Marcadores (ate 5) mostram depois qual post vendeu."""
    q = """mutation($u:String!,$s:[String]){generateShortLink(input:{originUrl:$u,subIds:$s}){shortLink}}"""
    sub = [sub_id(m) for m in (marcadores or [])][:5]
    return ((consulta(q, {"u": url, "s": sub}).get("generateShortLink") or {}).get("shortLink") or "")


_IDS = [re.compile(r"-i\.(\d+)\.(\d+)"), re.compile(r"/product/(\d+)/(\d+)")]


def _ids_da_url(url):
    """(shopId, itemId, palavras do nome) de uma URL de produto da Shopee. Nada achado = None."""
    import urllib.parse
    u = urllib.parse.unquote(urllib.parse.unquote(str(url or "")))
    for rx in _IDS:
        m = rx.search(u)
        if m:
            slug = ""
            ms = re.search(r"shopee\.com\.br/([^/?#]+)-i\.\d+\.\d+", u)
            if ms:
                slug = re.sub(r"[-_]+", " ", ms.group(1)).strip()[:80]
            return m.group(1), m.group(2), slug
    return None


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


motivo_link = ""  # por que o ultimo link nao abriu (vai para o log do robo)


def _ids_no_texto(txt):
    """Procura numeros de produto em qualquer lugar de um texto (pagina ou endereco, ate com %2F e \\/)."""
    import urllib.parse
    t = urllib.parse.unquote(urllib.parse.unquote(str(txt or ""))).replace("\\/", "/")
    for rx in _IDS:
        m = rx.search(t)
        if m:
            return _ids_da_url(m.group(0)) or (m.group(1), m.group(2), "")
    return None


def resolver_link(url, passos=6):
    """Abre um link da Shopee (inclusive link curto de afiliado de OUTRA pessoa) so para descobrir qual e o produto.
    Segue os redirecionamentos um a um. Devolve (shopId, itemId, palavras do nome) ou None (motivo em motivo_link).
    O link de outra pessoa NUNCA e usado: o robo gera o link do dono pela API a partir dos numeros do produto."""
    global motivo_link
    motivo_link = ""
    abre = urllib.request.build_opener(_SemRedirecionar)
    atual = str(url or "").strip()
    for _ in range(passos):
        achado = _ids_da_url(atual) or _ids_no_texto(atual)  # inclui a pagina de verificacao (?next=.../product/..)
        if achado:
            return achado
        try:
            req = urllib.request.Request(atual, method="GET", headers={"User-Agent": "Mozilla/5.0"})
            with abre.open(req, timeout=15) as r:
                prox = r.headers.get("Location") or ""
                if not prox:
                    corpo = r.read(300_000).decode("utf-8", "replace")
                    achado = _ids_no_texto(corpo)
                    if not achado:
                        motivo_link = f"HTTP {r.status} sem produto na pagina ({urllib.parse.urlsplit(atual).path[:40]})"
                    return achado
        except urllib.error.HTTPError as e:
            prox = e.headers.get("Location") or ""
            if not prox:
                motivo_link = f"HTTP {e.code} em {urllib.parse.urlsplit(atual).netloc}{urllib.parse.urlsplit(atual).path[:40]}"
                return None
        except Exception as e:
            motivo_link = str(e)[:100]
            return None
        atual = urllib.parse.urljoin(atual, prox)
    achado = _ids_da_url(atual) or _ids_no_texto(atual)
    if not achado:
        motivo_link = f"muitos redirecionamentos ({urllib.parse.urlsplit(atual).path[:40]})"
    return achado


def produto_por_id(shop_id, item_id):
    """O mesmo produto pela API de afiliados (offerLink ja e o link do dono). Fora do programa = None."""
    shop_id, item_id = int(shop_id), int(item_id)  # so numeros entram na consulta
    q = f"""query{{productOfferV2(shopId:{shop_id},itemId:{item_id},limit:1,page:1){{
      nodes{{itemId productName offerLink imageUrl priceMin priceMax priceDiscountRate sales ratingStar commissionRate shopName}}}}}}"""
    nos = (consulta(q).get("productOfferV2") or {}).get("nodes") or []
    return nos[0] if nos else None


def normalizar(node):
    """No da API -> produto no formato do robo."""
    def num(v, tipo=float):
        try:
            return tipo(v or 0)
        except Exception:
            return tipo(0)
    return {"itemId": str(node.get("itemId") or ""), "nome": str(node.get("productName") or ""),
            "preco": num(node.get("priceMin")), "nota": num(node.get("ratingStar")), "vendas": num(node.get("sales"), int),
            "comissao": num(node.get("commissionRate")), "imageUrl": str(node.get("imageUrl") or ""),
            "offerLink": str(node.get("offerLink") or ""), "campanha": ""}


def testar_conexao():
    """Pedido pequeno, so de leitura: confirma credencial e assinatura. Nao publica nada."""
    nos = buscar_produtos("garrafa termica", limite=1)
    return f"conectado OK ({len(nos)} produto de teste lido)"


def escolher_produtos(s, cfg, log, hoje):
    """Buscador diario de produtos da Shopee com cache em s['shopee_produtos'] (1 busca por dia).
    cfg e log vem do bot; hoje = 'AAAA-MM-DD' no fuso do robo. Nunca levanta erro."""
    import datetime as dt

    ativas, marca = campanhas_arquivo()
    if s.get("shopee_produtos_data") == hoje and s.get("shopee_campanhas_marca", "") == marca:
        return s.get("shopee_produtos") or []
    s["shopee_campanhas_marca"] = marca  # campanha nova do Claude no meio do dia: refaz a busca

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

        # campanhas: as do Claude (arquivo) entram na busca e ganham peso; as da API ficam registradas para o Claude pensar
        if cfg("CAMPANHAS_LIGADO") != "1":
            ativas = []
        if ativas and s.get("shopee_campanhas_api_data") != hoje:
            try:
                s["shopee_campanhas_api"] = campanhas_api()
            except Exception as e:
                s["shopee_campanhas_api"] = [{"erro": str(e)[:200]}]
            s["shopee_campanhas_api_data"] = hoje
        s["shopee_campanhas"] = [c["nome"] for c in ativas]
        palavra_campanha = {}
        for c in ativas:
            for p in c["palavras"]:
                palavra_campanha.setdefault(p, c)
        if ativas:
            log("Shopee: campanhas ativas:", ", ".join(c["nome"] for c in ativas))

        encontrados, falhas = {}, 0
        for kw in palavras + [p for p in palavra_campanha if p not in palavras]:
            try:
                nos = buscar_produtos(kw, limite=10, ordem=2)
                falhas = 0
            except Exception as e:
                log(f"Shopee erro ao buscar '{kw}':", str(e)[:150])
                falhas += 1
                if falhas >= 2:  # Shopee fora: para logo (nao gasta minutos do GitHub esperando)
                    log("Shopee: 2 falhas seguidas, busca de produtos parada por hoje.")
                    break
                continue

            for node in nos:
                iid = str(node.get("itemId") or "")
                if not iid or iid in encontrados or usado_recente(iid):
                    continue

                try:
                    nota = float(node.get("ratingStar") or 0)
                    preco = float(node.get("priceMin") or 0)
                    vendas = int(node.get("sales") or 0)
                    comissao = float(node.get("commissionRate") or 0)
                except Exception:
                    continue

                if nota < nota_min or not preco or preco > preco_max or vendas < vendas_min:
                    continue

                camp = palavra_campanha.get(kw)
                try:
                    desconto = float(node.get("priceDiscountRate") or 0)
                except Exception:
                    desconto = 0
                encontrados[iid] = {
                    "campanha": camp["nome"] if camp else (ativas[0]["nome"] if ativas and desconto >= 20 else ""),
                    "peso_campanha": camp["peso"] if camp else 1.0,
                    "desconto": desconto,
                    "data": hoje,
                    "itemId": iid,
                    "nome": str(node.get("productName") or ""),
                    "preco": preco,
                    "nota": nota,
                    "vendas": vendas,
                    "comissao": comissao,
                    "imageUrl": str(node.get("imageUrl") or ""),
                    "offerLink": str(node.get("offerLink") or ""),
                }

        lista = list(encontrados.values())
        # ordem: comissao esperada por venda (preco x %) pesada pela procura (log das vendas)
        import math
        for x in lista:
            x["nota_rank"] = round(x["preco"] * x["comissao"] * math.log10(x["vendas"] + 1)
                                   * x.get("peso_campanha", 1.0) * (1 + min(x.get("desconto", 0), 60) / 200), 3)
        lista.sort(key=lambda x: x["nota_rank"], reverse=True)
        s["shopee_produtos"] = lista
        s["shopee_produtos_data"] = hoje
        return lista
    except Exception as e:
        log("Shopee erro em escolher_produtos:", str(e)[:150])
        s["shopee_produtos"] = s.get("shopee_produtos") or []
        s["shopee_produtos_data"] = hoje
        return s["shopee_produtos"]


def relatorio_vendas(dias=7, max_paginas=5):
    """Vendas dos ultimos `dias` (conversionReport), agrupadas pelo 1o subId (a estrategia).
    So leitura. Devolve {"por_estrategia": {...}, "por_subid": {...}, "total": {...}}. Erro vira excecao curta."""
    fim = int(time.time())
    ini = fim - dias * 86400
    por_estr, por_sub, vistos = {}, {}, set()
    total = {"pedidos": 0, "comissao": 0.0, "cancelados": 0}
    scroll = ""
    for _ in range(max_paginas):
        extra = f',scrollId:"{scroll}"' if scroll else ""
        q = ("query{conversionReport(purchaseTimeStart:%d,purchaseTimeEnd:%d,limit:500%s){"
             "nodes{conversionId purchaseTime totalCommission utmContent orders{orderId orderStatus}}"
             "pageInfo{hasNextPage scrollId}}}") % (ini, fim, extra)
        rel = consulta(q).get("conversionReport") or {}
        for n in rel.get("nodes") or []:
            conv = str(n.get("conversionId") or "")
            if conv and conv in vistos:
                continue
            vistos.add(conv)
            subs = [x for x in str(n.get("utmContent") or "").split("-") if x]
            estr = subs[0] if subs else "sem_subid"
            chave = "-".join(subs) or "sem_subid"
            try:
                com = float(n.get("totalCommission") or 0)
            except Exception:
                com = 0.0
            pedidos = n.get("orders") or []
            canc = sum(1 for o in pedidos if "CANCEL" in str(o.get("orderStatus") or "").upper())
            qtd = len(pedidos) or 1
            for alvo in (por_estr.setdefault(estr, {"pedidos": 0, "comissao": 0.0, "cancelados": 0}),
                         por_sub.setdefault(chave, {"pedidos": 0, "comissao": 0.0, "cancelados": 0}), total):
                alvo["pedidos"] += qtd
                alvo["comissao"] = round(alvo["comissao"] + com, 2)
                alvo["cancelados"] += canc
        info = rel.get("pageInfo") or {}
        scroll = str(info.get("scrollId") or "")
        if not info.get("hasNextPage") or not scroll:
            break
    top = dict(sorted(por_sub.items(), key=lambda kv: kv[1]["comissao"], reverse=True)[:40])
    return {"por_estrategia": por_estr, "por_subid": top, "total": total}
