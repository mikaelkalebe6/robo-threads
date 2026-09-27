# -*- coding: utf-8 -*-
"""
Robo do Threads (API oficial da Meta).
- Posta de 3 a 8 vezes por dia em horarios sorteados (8h as 22h, horario de Manaus)
- Alterna texto e foto de forma aleatoria
- Responde comentarios nos seus posts (com o link quando a pessoa demonstra interesse)
- Le as inspiracoes de uma Planilha Google
Nao precisa mexer aqui. Tudo que voce ajusta fica nas "Variables" e "Secrets" do GitHub.
"""
import os, re, json, time, random, hashlib, csv, io, unicodedata, sys
import urllib.request, urllib.parse, urllib.error
import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Manaus")
API = "https://graph.threads.net/v1.0"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def env(nome, padrao=""):
    v = os.environ.get(nome, "")
    return v.strip() if v and v.strip() else padrao


TOKEN = env("THREADS_TOKEN")
GEMINI_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")
PLANILHA = env("PLANILHA_URL")
MODO_TESTE = env("MODO_TESTE", "0") == "1"
PAUSADO = env("PAUSADO", "0") == "1"
MIN_POSTS = int(env("POSTS_MIN", "3"))
MAX_POSTS = int(env("POSTS_MAX", "8"))
HORA_INI = int(env("HORA_INICIO", "8"))
HORA_FIM = int(env("HORA_FIM", "22"))
INTERVALO_MIN = int(env("INTERVALO_MINIMO_MIN", "40"))
RESP_POR_RODADA = int(env("RESPOSTAS_POR_RODADA", "6"))
RESP_POR_DIA = int(env("RESPOSTAS_POR_DIA", "60"))
CHANCE_FOTO = float(env("CHANCE_FOTO", "0.5"))
CHANCE_TREND = float(env("CHANCE_TENDENCIA", "0.3"))
EXEMPLOS = env("EXEMPLOS_RESPOSTAS", "")
PERSONA = env("PERSONA", (
    "Voce escreve como um brasileiro comum que garimpa achados bons e baratos na Shopee. "
    "Tom leve, direto, de amigo indicando coisa boa. Linguagem simples do dia a dia, "
    "sem parecer propaganda, sem exagero, sem prometer o que o produto nao faz."
))


def log(*a):
    print(dt.datetime.now(TZ).strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- estado
def carregar_estado():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def salvar_estado(s):
    # corta historicos para o arquivo nao crescer para sempre
    s["posts"] = s.get("posts", [])[-60:]
    s["respondidos"] = s.get("respondidos", [])[-3000:]
    s["hashes"] = s.get("hashes", [])[-200:]
    s["uso"] = dict(sorted(s.get("uso", {}).items(), key=lambda kv: kv[1])[-500:])
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- http
def http(method, url, params=None, body=None, headers=None, tentativas=3):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = None
    h = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            ultimo = RuntimeError(f"HTTP {e.code}: {msg[:500]}")
            if e.code < 500 and e.code != 429:
                raise ultimo
        except Exception as e:
            ultimo = e
        time.sleep(5 * (i + 1))
    raise ultimo


def threads(method, caminho, **params):
    params["access_token"] = TOKEN
    if method == "GET":
        return http("GET", f"{API}/{caminho}", params=params)
    return http("POST", f"{API}/{caminho}", params=params)


# ---------------------------------------------------------------- planilha
def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower().strip()


def url_csv(url):
    if "format=csv" in url or "output=csv" in url:
        return url
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise SystemExit("PLANILHA_URL invalida. Cole o link da Planilha Google.")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid.group(1) if gid else '0'}"


APPSHEET_APP = env("APPSHEET_APP", "PainelThreads-485832426")
APPSHEET_TABELA = env("APPSHEET_TABELA", "Untitled")
EXT_VIDEO = (".mp4", ".mov", ".m4v", ".webm")


def url_midia(v):
    # arquivo enviado pelo app (AppSheet) vira um link publico do AppSheet
    v = (v or "").strip()
    if not v or v.lower().startswith("http"):
        return v
    return ("https://www.appsheet.com/template/gettablefileurl?appName=" + urllib.parse.quote(APPSHEET_APP)
            + "&tableName=" + urllib.parse.quote(APPSHEET_TABELA) + "&fileName=" + urllib.parse.quote(v))


def eh_video(url):
    return urllib.parse.unquote(url or "").lower().split("?")[0].endswith(EXT_VIDEO) or \
        urllib.parse.unquote(url or "").lower().endswith(EXT_VIDEO)


def ler_planilha():
    req = urllib.request.Request(url_csv(PLANILHA), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode("utf-8-sig", "replace")
    if txt.lstrip().startswith("<"):
        raise SystemExit("Nao consegui ler a planilha. Compartilhe como 'Qualquer pessoa com o link: Leitor'.")
    itens = []
    for i, linha in enumerate(csv.DictReader(io.StringIO(txt))):
        l = {sem_acento(k): (v or "").strip() for k, v in linha.items() if k}
        ideia = l.get("ideia") or l.get("inspiracao") or l.get("texto") or ""
        if not ideia:
            continue
        if sem_acento(l.get("ativo", "sim")) in ("nao", "n", "0", "off"):
            continue
        itens.append({
            "id": hashlib.md5(ideia.encode()).hexdigest()[:10],
            "ideia": ideia,
            "produto": l.get("produto", ""),
            "link": l.get("link", ""),
            "foto": url_midia(l.get("foto", "") or l.get("foto_url", "") or l.get("imagem", "")),
            "obs": l.get("observacao", "") or l.get("obs", ""),
        })
    return itens


def escolher_inspiracao(itens, s):
    uso = s.get("uso", {})
    recentes = [p.get("insp") for p in s.get("posts", [])[-max(1, min(len(itens) - 1, 6)):]]
    candidatos = [i for i in itens if i["id"] not in recentes] or itens
    # quem foi usado ha mais tempo (ou nunca) tem mais chance
    agora = time.time()
    pesos = [1 + (agora - uso.get(i["id"], 0)) / 3600 for i in candidatos]
    return random.choices(candidatos, weights=pesos, k=1)[0]


# ---------------------------------------------------------------- gemini
def gemini(prompt, json_mode=False, busca=False):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    cfg = {"temperature": 1.0}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    corpo = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg}
    if busca:
        corpo["tools"] = [{"google_search": {}}]
    r, ultimo = None, None
    modelos = [GEMINI_MODEL] + [m for m in ("gemini-flash-lite-latest",) if m != GEMINI_MODEL]
    for modelo in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        for tentativa in range(2):
            try:
                r = http("POST", url, body=corpo, headers={"x-goog-api-key": GEMINI_KEY})
                break
            except Exception as e:
                ultimo, msg = e, str(e)
                if busca or not any(c in msg for c in ("HTTP 500", "HTTP 503", "HTTP 429", "timed out")):
                    raise
                log(f"Gemini instavel ({modelo}), tentando de novo...")
                time.sleep(6 * (tentativa + 1))
        if r is not None:
            break
    if r is None:
        raise ultimo
    try:
        return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]).strip()
    except Exception:
        log("Gemini sem resposta util:", str(r)[:300])
        return None


ESTILOS = [
    "pergunta direta que faz a pessoa querer opinar",
    "opiniao curta e um pouco polemica, sem ofender ninguem",
    "confissao leve do dia a dia seguida de uma pergunta",
    "enquete de duas opcoes (isso ou aquilo)",
    "mini historia de 2 frases com pergunta no final",
    "frase de identificacao, estilo 'quem mais...'",
    "humor do cotidiano, curto e direto",
]


def limpar(t):
    t = re.sub(r"https?://\S+", "", t or "").strip().strip('"').strip()
    return t


def gerar_post(insp, com_link):
    estilo = random.choice(ESTILOS)
    tamanho = random.choice(["bem curto (1 a 2 linhas)", "curto (2 a 4 linhas)", "medio (ate 5 linhas)"])
    prompt = f"""{PERSONA}

Escreva UM post para o Threads, em portugues do Brasil. Use a inspiracao como referencia de tema e de gancho, sem copiar literalmente, e siga a observacao.
Inspiracao: {insp['ideia']}
Produto: {insp['produto'] or 'nenhum (nao fale de produto, marca, empresa ou investimento)'}
Observacao: {insp['obs'] or '-'}
Estilo: {estilo}. Tamanho: {tamanho}.
Regras: nao coloque link nem @; no maximo 1 emoji (ou nenhum); nada de hashtags em excesso (0 ou 1);
nao use travessao; {'termine convidando a clicar no link abaixo de forma natural' if com_link else 'termine convidando a comentar (ex: pedir o link, dar opiniao)'}.
Responda so com o texto do post."""
    usar_trend = random.random() < CHANCE_TREND
    if usar_trend:
        prompt += ("\nAntes de escrever, pesquise o que esta sendo muito comentado HOJE no Brasil "
                   "(redes sociais e noticias) ligado ao tema da inspiracao e use esse assunto atual "
                   "como gancho, de forma natural. Evite tragedias, mortes e politica partidaria. "
                   "Nao cite fontes nem links.")
    try:
        txt = limpar(gemini(prompt, busca=usar_trend) or "")
        if usar_trend:
            log("Post usando tendencia do dia.")
    except Exception as e:
        log("Busca de tendencia falhou, seguindo sem:", e)
        txt = limpar(gemini(prompt.split("\nAntes de escrever, pesquise")[0]) or "")
    if not txt:
        txt = insp["ideia"]
    return txt[:440]


def gerar_resposta(post_txt, comentario, tem_link):
    exemplos = ("Exemplos reais de como a dona do perfil responde (imite o jeito, nao copie):\n" + EXEMPLOS) if EXEMPLOS else ""
    prompt = f"""{PERSONA}

Voce e a dona do perfil respondendo um comentario no seu proprio post do Threads, pelo celular.
Seu post: {post_txt}
Comentario da pessoa: {comentario}
{'Existe um link do produto que voce pode mandar.' if tem_link else 'Nao existe link para mandar.'}
{exemplos}

Como responder:
- Primeiro entenda a intencao: piada, ironia, sarcasmo, provocacao, desabafo, pergunta sincera ou so uma reacao. Responda a ESSA intencao. Se for piada ou ironia, entre na brincadeira; nunca responda ironia como se fosse literal.
- Escreva como gente de verdade digitando rapido: portugues do Brasil informal, frases curtas, pode usar kkkk, pois e, real, ne, minusculas as vezes. Nada de tom de empresa, nada de "obrigada pelo comentario", nada de "que otima pergunta".
- Tamanho: normalmente de 2 a 15 palavras. So escreva mais se a pessoa fez uma pergunta que pede mais.
- Nao termine sempre com pergunta; so quando for natural puxar papo.
- Emoji so de vez em quando e no maximo 1. Sem hashtag. Sem travessao.
- Se discordarem, responda com leveza e bom humor, sem brigar e sem aceitar ofensa.
- Nunca invente fatos pessoais especificos (profissao, cidade, valores, historias).

Responda em JSON: {{"responder": true/false, "texto": "...", "mandar_link": true/false}}
- responder=false se for spam, ofensa pesada, propaganda de outra pessoa ou algo que nao pede resposta.
- mandar_link=true so se a pessoa pediu o link ou demonstrou interesse claro em comprar."""
    r = gemini(prompt, json_mode=True)
    try:
        d = json.loads(r)
        d["texto"] = limpar(d.get("texto", ""))[:400]
        return d
    except Exception:
        if not GEMINI_KEY:
            return {"responder": True, "texto": random.choice(["Valeu pelo comentario!", "Tamo junto!", "Que bom que curtiu!"]),
                    "mandar_link": tem_link and bool(re.search(r"link|quero|onde|pre[cç]o|quanto", comentario or "", re.I))}
        return {"responder": False}


FRASES_LINK = ["Aqui o link 👉 {l}", "Link: {l}", "Tá aqui ó: {l}", "Link do achado: {l}", "Esse aqui 👉 {l}", "Pega aqui: {l}"]
FRASES_LINK_PROPRIO = ["Link aqui 👇 {l}", "Pra quem pediu o link: {l}", "Link do produto: {l}", "{l}"]


# ---------------------------------------------------------------- publicar
def publicar(texto, foto=None, responder_a=None):
    if MODO_TESTE:
        log("[MODO TESTE] publicaria:", {"texto": texto, "foto": foto, "reply_to": responder_a})
        return "teste_" + hashlib.md5((texto + str(time.time())).encode()).hexdigest()[:8]
    video = bool(foto) and eh_video(foto)
    p = {"media_type": ("VIDEO" if video else "IMAGE") if foto else "TEXT", "text": texto}
    if foto:
        p["video_url" if video else "image_url"] = foto
    if responder_a:
        p["reply_to_id"] = responder_a
    cid = threads("POST", "me/threads", **p)["id"]
    for _ in range(30 if foto else 12):  # espera a Meta processar (video demora mais)
        time.sleep(8 if foto else 3)
        st = threads("GET", cid, fields="status,error_message")
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Meta recusou o post: {st}")
    return threads("POST", "me/threads_publish", creation_id=cid)["id"]


# ---------------------------------------------------------------- plano do dia
def plano_do_dia(s, agora):
    hoje = agora.strftime("%Y-%m-%d")
    p = s.get("plano")
    if p and p.get("data") == hoje:
        return p
    qtd = random.randint(MIN_POSTS, MAX_POSTS)
    ini, fim = HORA_INI * 60, HORA_FIM * 60
    horarios = []
    for _ in range(2000):
        if len(horarios) == qtd:
            break
        m = random.randint(ini, fim)
        if all(abs(m - h) >= INTERVALO_MIN for h in horarios):
            horarios.append(m)
    horarios.sort()
    p = {"data": hoje, "horarios": [f"{h // 60:02d}:{h % 60:02d}" for h in horarios], "feitos": [], "respostas": 0}
    s["plano"] = p
    log(f"Plano de hoje: {len(horarios)} posts ->", ", ".join(p["horarios"]))
    return p


def tarefa_postar(s, agora):
    p = plano_do_dia(s, agora)
    agora_min = agora.hour * 60 + agora.minute
    pendentes = [h for h in p["horarios"] if h not in p["feitos"]]
    vencidos = [h for h in pendentes if int(h[:2]) * 60 + int(h[3:]) <= agora_min]
    if not vencidos:
        log("Nenhum post na hora agora. Proximo:", pendentes[0] if pendentes else "amanha")
        return
    # se varios venceram (atraso do GitHub), posta so 1 e descarta os muito antigos
    for h in vencidos[:-1]:
        if agora_min - (int(h[:2]) * 60 + int(h[3:])) > 90:
            p["feitos"].append(h)
            log("Horario perdido (atraso), pulando:", h)
    h = [x for x in vencidos if x not in p["feitos"]][0]
    if agora.hour > HORA_FIM:
        p["feitos"].append(h)
        return

    itens = ler_planilha()
    if not itens:
        log("Planilha vazia. Nada para postar.")
        return
    texto = None
    for _ in range(4):  # nunca repete um texto igual (repeticao e sinal de spam)
        insp = escolher_inspiracao(itens, s)
        tem_link = bool(insp["link"])
        link_no_post = tem_link and random.random() < 0.5
        t = gerar_post(insp, com_link=link_no_post)
        hs = hashlib.md5(sem_acento(t).encode()).hexdigest()
        if hs not in s.get("hashes", []):
            texto = t
            break
    if not texto:
        log("So sairiam textos repetidos. Adicione mais inspiracoes ou a chave do Gemini. Pulando.")
        p["feitos"].append(h)
        return
    usar_foto = bool(insp["foto"]) and random.random() < CHANCE_FOTO
    if link_no_post:
        texto = f"{texto}\n\n{insp['link']}"

    time.sleep(random.randint(0, 90))  # pequeno atraso aleatorio extra
    try:
        pid = publicar(texto, foto=insp["foto"] if usar_foto else None)
    except Exception as e:
        if not usar_foto:
            raise
        log("Midia recusada, postando so o texto:", str(e)[:150])
        usar_foto = False
        pid = publicar(texto)
    log(f"POSTADO ({'foto' if usar_foto else 'texto'}{', link no post' if link_no_post else ''}):", pid)

    if tem_link and not link_no_post:
        time.sleep(random.randint(20, 60))
        publicar(random.choice(FRASES_LINK_PROPRIO).format(l=insp["link"]), responder_a=pid)
        log("Link colocado no primeiro comentario.")

    p["feitos"].append(h)
    s.setdefault("hashes", []).append(hs)
    s.setdefault("uso", {})[insp["id"]] = time.time()
    s.setdefault("posts", []).append({"id": pid, "insp": insp["id"], "link": insp["link"],
                                      "texto": texto[:300], "quando": agora.isoformat()})
    salvar_estado(s)


# ---------------------------------------------------------------- responder
def tarefa_responder(s, agora):
    p = plano_do_dia(s, agora)
    if p.get("respostas", 0) >= RESP_POR_DIA:
        log("Limite diario de respostas atingido.")
        return
    if MODO_TESTE and not TOKEN:
        return
    eu = s.get("eu") or threads("GET", "me", fields="id,username").get("username", "")
    s["eu"] = eu
    respondidos = set(s.get("respondidos", []))
    limite = agora - dt.timedelta(days=4)
    posts = [x for x in s.get("posts", []) if not str(x["id"]).startswith("teste_")
             and dt.datetime.fromisoformat(x["quando"]) > limite][-15:]
    feitas = 0
    por_pessoa = s.setdefault("por_pessoa", {})
    if por_pessoa.get("_data") != p["data"]:
        por_pessoa.clear()
        por_pessoa["_data"] = p["data"]
    for post in reversed(posts):
        try:
            r = threads("GET", f"{post['id']}/replies", fields="id,text,username,timestamp")
        except Exception as e:
            log("Nao li comentarios de", post["id"], e)
            continue
        for c in r.get("data", []):
            if feitas >= RESP_POR_RODADA or p.get("respostas", 0) >= RESP_POR_DIA:
                break
            if c["id"] in respondidos or c.get("username") == eu:
                continue
            quem = c.get("username", "?")
            if por_pessoa.get(quem, 0) >= 2:  # no maximo 2 respostas por pessoa por dia
                continue
            try:
                d = gerar_resposta(post.get("texto", ""), c.get("text", ""), bool(post.get("link")))
            except Exception as e:
                log("Gemini fora do ar; o resto dos comentarios fica para a proxima rodada:", str(e)[:120])
                return
            s.setdefault("respondidos", []).append(c["id"])
            respondidos.add(c["id"])
            if not d.get("responder") or not d.get("texto"):
                log(f"Ignorado comentario de @{quem}")
                salvar_estado(s)
                continue
            txt = d["texto"]
            if d.get("mandar_link") and post.get("link"):
                txt = f"{txt}\n{random.choice(FRASES_LINK).format(l=post['link'])}"
            time.sleep(random.randint(8, 25))
            publicar(txt, responder_a=c["id"])
            feitas += 1
            p["respostas"] = p.get("respostas", 0) + 1
            por_pessoa[quem] = por_pessoa.get(quem, 0) + 1
            log(f"Respondi @{quem}{' (com link)' if 'http' in txt else ''}")
            salvar_estado(s)
    log(f"Respostas nesta rodada: {feitas}")


# ---------------------------------------------------------------- main
def main():
    if PAUSADO:
        log("Robo PAUSADO (variavel PAUSADO=1). Nada feito.")
        return
    if not TOKEN and not MODO_TESTE:
        raise SystemExit("Falta o segredo THREADS_TOKEN.")
    if not PLANILHA:
        raise SystemExit("Falta a variavel PLANILHA_URL.")
    s = carregar_estado()
    agora = dt.datetime.now(TZ)
    erros = 0
    for tarefa in (tarefa_postar, tarefa_responder):
        try:
            tarefa(s, agora)
        except Exception as e:
            erros += 1
            log(f"ERRO em {tarefa.__name__}:", e)
        salvar_estado(s)
    if erros == 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
