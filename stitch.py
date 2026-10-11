# -*- coding: utf-8 -*-
"""
Imagens de IA para os carrosseis usando o Google Stitch (cota gratis da conta do dono).

Como funciona:
- Roda no workflow "Artes IA" (sozinho quando a fila de carrosseis muda, ou pelo botao Run workflow).
- Para cada slide em carrosseis/fila/car-*.json com "imagem_ia" (descricao da cena) e sem "imagem":
  pede ao Stitch uma tela que seja so a foto, pega a imagem gerada, corta em 1080x1350,
  hospeda no repositorio publico de imagens e grava o link em "imagem" no proprio JSON.
- Marca "ia_tentado": true no carrossel (deu certo ou nao), para o robo nao ficar esperando.
- Tudo o que acontece vai para carrosseis/stitch_log.json (o Claude le por ali, sem abrir o Actions).
- Sem a chave STITCH_API_KEY o script so avisa e sai. Falha do Stitch nunca quebra nada: o slide sai
  com a foto do produto, como antes.
- Modo teste: python3 stitch.py --teste "descricao" gera 1 imagem em carrosseis/stitch_teste.png.
"""
import os, sys, io, json, re, time, glob, urllib.request, urllib.error

HOST = os.environ.get("STITCH_HOST", "").strip() or "https://stitch.googleapis.com/mcp"
CHAVE = os.environ.get("STITCH_API_KEY", "").strip()
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carrosseis")
FILA = os.path.join(PASTA, "fila")
LOG = os.path.join(PASTA, "stitch_log.json")
PROJETO = os.path.join(PASTA, "stitch_projeto.txt")
MAX_IMAGENS = int(os.environ.get("STITCH_MAX_POR_RODADA", "12") or 12)  # trava da cota gratis
ESPERA_MAX = 330  # segundos por imagem (a geracao do Stitch pode levar minutos)

PROMPT_BASE = (
    "Create a single mobile screen that is ONLY one full-bleed photorealistic photograph, edge to edge, "
    "vertical 4:5 composition, natural light, real-life smartphone photo look, Brazilian everyday setting. "
    "Absolutely no UI elements, no text, no letters, no buttons, no navigation bar, no status bar, no logos, "
    "no watermark, no frames. The whole screen is the photo. Scene: ")
# onde o texto vai ficar no slide (layout + texto_pos do JSON): a foto deixa esse espaco livre, o resto e livre
ESPACO_TEXTO = {
    "baixo": " Composition: main subject in the upper two thirds; bottom third calm, simple and slightly dark.",
    "topo": " Composition: main subject in the lower two thirds; top third calm, simple (sky, wall or blurred background).",
    "split": " Composition: subject centered, filling the frame, nothing important near the edges.",
}

_log = {"rodada": time.strftime("%Y-%m-%d %H:%M:%S"), "eventos": []}
_sessao = {"id": None, "n": 0}


def registrar(*a):
    msg = " ".join(str(x) for x in a)
    print(msg)
    _log["eventos"].append(msg[:500])


def salvar_log():
    try:
        antigo = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []
        if not isinstance(antigo, list):
            antigo = []
    except Exception:
        antigo = []
    antigo.append(_log)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(antigo[-15:], f, ensure_ascii=False, indent=1)


def _ler_resposta(raw, tipo):
    """Resposta JSON direta ou em SSE (linhas 'data: {...}'): devolve o ultimo objeto JSON-RPC."""
    txt = raw.decode("utf-8", "replace")
    if "text/event-stream" in (tipo or "") or txt.lstrip().startswith(("event:", "data:")):
        ult = None
        for linha in txt.splitlines():
            if linha.startswith("data:"):
                try:
                    ult = json.loads(linha[5:].strip())
                except Exception:
                    pass
        return ult or {}
    return json.loads(txt) if txt.strip() else {}


def rpc(metodo, params=None, timeout=60, notificacao=False):
    _sessao["n"] += 1
    corpo = {"jsonrpc": "2.0", "method": metodo}
    if params is not None:
        corpo["params"] = params
    if not notificacao:
        corpo["id"] = _sessao["n"]
    hdr = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
           "X-Goog-Api-Key": CHAVE}
    if _sessao["id"]:
        hdr["Mcp-Session-Id"] = _sessao["id"]
    req = urllib.request.Request(HOST, data=json.dumps(corpo).encode(), method="POST", headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                _sessao["id"] = sid
            dado = _ler_resposta(r.read(), r.headers.get("Content-Type"))
    except urllib.error.HTTPError as e:
        corpo_erro = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Stitch HTTP {e.code} em {metodo}: {corpo_erro}")
    if notificacao:
        return {}
    if dado.get("error"):
        raise RuntimeError(f"Stitch recusou {metodo}: {json.dumps(dado['error'])[:300]}")
    return dado.get("result") or {}


def ferramenta(nome, args, timeout=90):
    res = rpc("tools/call", {"name": nome, "arguments": args}, timeout=timeout)
    if res.get("isError"):
        raise RuntimeError(f"{nome} deu erro: {json.dumps(res)[:300]}")
    return res


def _textos(obj):
    """Todo o conteudo da resposta como texto (para achar ids e links)."""
    return json.dumps(obj, ensure_ascii=False)


def conectar():
    try:
        rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                           "clientInfo": {"name": "robo-artes", "version": "1"}}, timeout=30)
        rpc("notifications/initialized", notificacao=True, timeout=15)
    except Exception as e:  # alguns servidores remotos dispensam o initialize
        registrar("initialize ignorado:", str(e)[:200])
    lista = rpc("tools/list", {}, timeout=30).get("tools", [])
    _log["ferramentas"] = [{"nome": t.get("name"), "args": list(((t.get("inputSchema") or {}).get("properties") or {}).keys())}
                           for t in lista]
    return {t.get("name"): t for t in lista}


def _arg(tools, nome, preferidos):
    props = ((tools.get(nome) or {}).get("inputSchema") or {}).get("properties") or {}
    for p in preferidos:
        if p in props:
            return p
    return preferidos[0]


def _enum(tools, nome, campo, quer):
    props = ((tools.get(nome) or {}).get("inputSchema") or {}).get("properties") or {}
    opcoes = (props.get(campo) or {}).get("enum") or []
    for o in opcoes:
        if quer.lower() in str(o).lower():
            return o
    return opcoes[0] if opcoes else quer


def projeto(tools):
    if os.path.exists(PROJETO):
        pid = open(PROJETO).read().strip()
        if pid:
            return pid
    res = ferramenta("create_project", {"title": "artes carrossel"})
    achados = re.findall(r"projects/(\d+)", _textos(res)) or re.findall(r'"(?:projectId|id)"\s*:\s*"?(\d{6,})', _textos(res))
    if not achados:
        raise RuntimeError("Nao achei o id do projeto na resposta do create_project: " + _textos(res)[:300])
    with open(PROJETO, "w") as f:
        f.write(achados[0])
    registrar("Projeto Stitch criado:", achados[0])
    return achados[0]


def _links_imagem(texto):
    links = re.findall(r'https://[^\s"\'\\<>)]+', texto)
    return [l for l in links if "googleusercontent" in l or "/download" in l or re.search(r"\.(png|jpe?g|webp)", l)]


def _baixar(url, timeout=40):
    cab = {"User-Agent": "Mozilla/5.0"}
    if (urllib.parse.urlparse(url).hostname or "").endswith(".googleapis.com"):
        cab["X-Goog-Api-Key"] = CHAVE  # a chave so vai para a API do Google, nunca para link de terceiros
    req = urllib.request.Request(url, headers=cab)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def _melhor_imagem(res):
    """Prefere a foto gerada que esta dentro do HTML da tela (maior resolucao); se nao der, o print da tela."""
    texto = _textos(res)
    candidatos = []
    for l in _links_imagem(texto):
        try:
            dado, tipo = _baixar(l)
        except Exception:
            continue
        if "html" in tipo or dado[:15].lower().startswith((b"<!doctype", b"<html")):
            html = dado.decode("utf-8", "replace")
            for src in re.findall(r'src="(https://[^"]+)"', html) + re.findall(r"url\(['\"]?(https://[^'\")]+)", html):
                try:
                    img, t2 = _baixar(src)
                    if t2.startswith("image") and len(img) > 30000:
                        candidatos.append(("html", img))
                except Exception:
                    pass
        elif tipo.startswith("image") or dado[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"RIFF"):
            candidatos.append(("print", dado))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0] == "html", len(c[1])), reverse=True)
    registrar("Imagem escolhida:", candidatos[0][0], len(candidatos[0][1]), "bytes")
    return candidatos[0][1]


def gerar(tools, pid, cena, espaco=""):
    nome_proj = _arg(tools, "generate_screen_from_text", ["projectId", "project_id", "project"])
    args = {nome_proj: pid, "prompt": PROMPT_BASE + cena + espaco}
    props = ((tools.get("generate_screen_from_text") or {}).get("inputSchema") or {}).get("properties") or {}
    if "deviceType" in props:
        args["deviceType"] = _enum(tools, "generate_screen_from_text", "deviceType", "MOBILE")
    inicio = time.time()
    try:
        res = ferramenta("generate_screen_from_text", args, timeout=ESPERA_MAX)
        img = _melhor_imagem(res)
        if img:
            return img
        registrar("Geracao sem link direto; procurando a tela no projeto.")
    except Exception as e:
        registrar("generate_screen_from_text:", str(e)[:300])
        if "HTTP 4" in str(e):
            raise
    # a geracao pode terminar depois do tempo limite: procura a tela mais nova no projeto
    while time.time() - inicio < ESPERA_MAX + 120:
        try:
            lista = ferramenta("list_screens", {_arg(tools, "list_screens", ["projectId", "project_id"]): pid}, timeout=60)
            ids = re.findall(r"screens/([A-Za-z0-9_-]+)", _textos(lista))
            if ids:
                tela = ferramenta("get_screen", {_arg(tools, "get_screen", ["projectId", "project_id"]): pid,
                                                 _arg(tools, "get_screen", ["screenId", "screen_id"]): ids[-1]}, timeout=60)
                img = _melhor_imagem(tela)
                if img:
                    return img
        except Exception as e:
            registrar("procurando tela:", str(e)[:200])
        time.sleep(30)
    return None


def cortar(img_bytes):
    """Corta no centro para 4:5 e deixa em 1080x1350 (JPEG leve)."""
    import carrossel
    Image, _, _ = carrossel._pil()
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    alvo = 1080 / 1350
    w, h = im.size
    if w / h > alvo:
        nw = int(h * alvo)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / alvo)
        topo = max(0, (h - nh) // 3)  # puxa um pouco para cima (cabeca e produto costumam estar no alto)
        im = im.crop((0, topo, w, topo + nh))
    im = im.resize((1080, 1350))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue(), im.size


def processar_fila(tools, pid):
    import carrossel
    feitas = 0
    for caminho in sorted(glob.glob(os.path.join(FILA, "car-*.json"))):
        try:
            car = json.load(open(caminho, encoding="utf-8"))
        except Exception as e:
            registrar("JSON ilegivel:", os.path.basename(caminho), str(e)[:100])
            continue
        pendentes = [s for s in car.get("slides", []) if s.get("imagem_ia") and not s.get("imagem")]
        if not pendentes or car.get("ia_tentado"):
            continue
        for i, sl in enumerate(car.get("slides", []), 1):
            if not sl.get("imagem_ia") or sl.get("imagem"):
                continue
            if feitas >= MAX_IMAGENS:
                registrar("Limite de imagens por rodada atingido; o resto fica para a proxima.")
                break
            try:
                espaco = ESPACO_TEXTO["split"] if sl.get("layout") == "split" else (
                    ESPACO_TEXTO.get(sl.get("texto_pos", "baixo"), "") if sl.get("layout") == "fundo" else "")
                img = gerar(tools, pid, sl["imagem_ia"], espaco)
                if not img:
                    raise RuntimeError("Stitch nao devolveu imagem")
                jpg, tam = cortar(img)
                url = carrossel.hospedar(f"ia/{car.get('id', 'car')}-s{i}.jpg", jpg)
                sl["imagem"] = url
                feitas += 1
                registrar("OK", car.get("id"), f"slide {i}", url)
            except Exception as e:
                registrar("FALHOU", car.get("id"), f"slide {i}:", str(e)[:250])
        else:
            car["ia_tentado"] = True
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(car, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return feitas


def main():
    if not CHAVE:
        print("Artes IA desligadas: falta o Secret STITCH_API_KEY.")
        return
    try:
        tools = conectar()
        registrar("Ferramentas do Stitch:", ", ".join(sorted(tools)))
        pid = projeto(tools)
        if len(sys.argv) > 2 and sys.argv[1] == "--teste":
            img = gerar(tools, pid, sys.argv[2])
            if img:
                jpg, tam = cortar(img)
                with open(os.path.join(PASTA, "stitch_teste.jpg"), "wb") as f:
                    f.write(jpg)
                registrar("Teste OK: carrosseis/stitch_teste.jpg", tam)
            else:
                registrar("Teste: Stitch nao devolveu imagem")
        else:
            registrar("Imagens novas:", processar_fila(tools, pid))
    except Exception as e:
        registrar("ERRO geral:", str(e)[:400])
    finally:
        salvar_log()


if __name__ == "__main__":
    main()
