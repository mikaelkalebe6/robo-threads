# -*- coding: utf-8 -*-
"""Leitor de inspiracoes: le links/videos novos da planilha de Inspiracoes e pede ao Gemini
(transcricao + analise). Resultado vai para inspiracoes_lidas.md, que o Claude le no domingo."""
import os, re, sys, json, base64, hashlib, csv, io, html, urllib.request, urllib.parse
import datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Manaus")
AQUI = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(AQUI, "inspiracoes_estado.json")
SAIDA = os.path.join(AQUI, "inspiracoes_lidas.md")
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODELO = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-flash-latest"
PLANILHA = os.environ.get("INSPIRACOES_URL", "").strip() or \
    "https://docs.google.com/spreadsheets/d/1KTkNtlksA4sWBh5Usfwc9EsRELcoGaBXXVOEEo9Km-k/export?format=csv&gid=1716591096"
APP = os.environ.get("APPSHEET_APP", "").strip() or "PainelThreads-485832426"
TABELA = os.environ.get("APPSHEET_TABELA_INSP", "").strip() or "Untitled 2"
POR_RODADA = 3
MAX_MB = 18
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
MIME = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4", ".webm": "video/webm",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".mp3": "audio/mp3", ".m4a": "audio/mp4"}


def log(*a):
    print(dt.datetime.now(TZ).strftime("%H:%M:%S"), "[inspiracoes]", *a, flush=True)


def baixar(url, limite=None, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = r.read(limite + 1 if limite else -1)
        return dados, r.headers.get("Content-Type", "")


def gemini(partes):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
    corpo = json.dumps({"contents": [{"parts": partes}], "generationConfig": {"temperature": 0.4}}).encode()
    req = urllib.request.Request(url, data=corpo, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    with urllib.request.urlopen(req, timeout=240) as r:
        j = json.loads(r.read())
    return "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"]).strip()


PEDIDO = """Voce analisa conteudo de inspiracao para o perfil @lorenafleck_ no Threads (posts de engajamento em portugues do Brasil, tom leve e direto; nunca falar de investimento).
Responda em portugues do Brasil, sem travessoes, curto, neste formato:
**Tipo:** (video, foto, texto, carrossel) | **Idioma original:** ...
**Transcricao/Conteudo:** (se for video ou audio: transcreva a fala traduzida para portugues, no maximo 250 palavras; se for texto: resuma)
**Gancho:** (como prende a atencao no inicio)
**Estrutura:** (passos do conteudo em 1 linha)
**Por que funciona:** (1 ou 2 frases)
**3 ganchos para o perfil:** (3 frases prontas, originais, sem copiar o conteudo)
Observacao do Kalebe sobre esta inspiracao: {obs}
{extra}"""


CRAWLERS = [{"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"},
            {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}, UA]


def _meta(h, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % re.escape(prop), h, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop), h, re.I)
    return html.unescape(m.group(1).strip()) if m and m.group(1).strip() else ""


def meta_da_pagina(link):
    """Legenda e midia publicas do post, sem login: oEmbed do TikTok, embed do Instagram ou meta tags
    lidas como o robo de preview de links (o mesmo que o WhatsApp usa)."""
    textos, midia = [], {"video": "", "imagem": ""}
    try:
        if "tiktok.com" in link:
            d, _ = baixar("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(link, safe=""))
            j = json.loads(d)
            textos.append(f"Autor: {j.get('author_name', '')}. Legenda: {j.get('title', '')}")
            midia["imagem"] = j.get("thumbnail_url", "")
        else:
            urls = [link]
            m = re.search(r"instagram\.com/(?:[^/]+/)?(p|reel|reels|tv)/([^/?#]+)", link)
            if m:
                urls.insert(0, f"https://www.instagram.com/p/{m.group(2)}/embed/captioned/")
            for u in urls:
                for hdr in CRAWLERS:
                    try:
                        d, _ = baixar(u, limite=800000, headers=hdr)
                    except Exception:
                        continue
                    h = d.decode("utf-8", "replace")
                    if "/embed/captioned" in u:
                        c = re.search(r'class="Caption"[^>]*>(.*?)</div>', h, re.S)
                        if c:
                            textos.append(html.unescape(re.sub(r"<[^>]+>", " ", c.group(1))).strip())
                        im = re.search(r'class="EmbeddedMediaImage"[^>]+src="([^"]+)"', h)
                        if im and not midia["imagem"]:
                            midia["imagem"] = html.unescape(im.group(1))
                    for prop in ("og:title", "og:description", "description", "twitter:description"):
                        t = _meta(h, prop)
                        if t:
                            textos.append(t)
                    midia["video"] = midia["video"] or _meta(h, "og:video") or _meta(h, "og:video:secure_url")
                    midia["imagem"] = midia["imagem"] or _meta(h, "og:image")
                    if textos or midia["video"]:
                        break
                if textos or midia["video"]:
                    break
    except Exception as e:
        log("Nao consegui ler a pagina:", str(e)[:120])
    vistos, final = set(), []
    for t in textos:
        t = re.sub(r"\s+", " ", t).strip()
        if t and t not in vistos:
            vistos.add(t); final.append(t)
    return "\n".join(final)[:3000], midia


def baixar_video(link):
    """Baixa o video publico do link (TikTok, Instagram, Threads, Facebook...) sem login, com yt-dlp."""
    import subprocess, glob, tempfile
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "yt-dlp"],
                       check=True, timeout=120, capture_output=True)
        pasta = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-playlist", "--no-warnings",
                            "--max-filesize", "%dM" % MAX_MB,
                            "-f", "best[ext=mp4][filesize<%dM]/best[ext=mp4]/best" % MAX_MB,
                            "-o", os.path.join(pasta, "v.%(ext)s"), link],
                           timeout=150, capture_output=True, text=True)
        arqs = [a for a in glob.glob(os.path.join(pasta, "v.*")) if not a.endswith(".part")]
        if arqs and os.path.getsize(arqs[0]) <= MAX_MB * 1024 * 1024:
            log("Video baixado:", link)
            return arqs[0]
        log("Sem video para baixar (ou post de foto/texto):", (r.stderr or "")[:150].replace("\n", " "))
    except Exception as e:
        log("Download do video falhou:", str(e)[:150])
    return None


def analisar(link, video, obs):
    obs = obs or "(nenhuma)"
    if video:
        url = video if video.lower().startswith("http") else (
            "https://www.appsheet.com/template/gettablefileurl?appName=" + urllib.parse.quote(APP)
            + "&tableName=" + urllib.parse.quote(TABELA) + "&fileName=" + urllib.parse.quote(video))
        dados, ctype = baixar(url, limite=MAX_MB * 1024 * 1024)
        if len(dados) > MAX_MB * 1024 * 1024:
            return "Arquivo grande demais (mais de %d MB). Mande um video mais curto." % MAX_MB
        ext = os.path.splitext(urllib.parse.unquote(video).split("?")[0])[1].lower()
        mime = MIME.get(ext) or (ctype.split(";")[0] if ctype and "/" in ctype and "html" not in ctype else "video/mp4")
        partes = [{"inline_data": {"mime_type": mime, "data": base64.b64encode(dados).decode()}},
                  {"text": PEDIDO.format(obs=obs, extra="Link original: " + (link or "-"))}]
        return gemini(partes)
    if re.search(r"(youtube\.com|youtu\.be)", link or "", re.I):
        return gemini([{"file_data": {"file_uri": link}}, {"text": PEDIDO.format(obs=obs, extra="")}])
    texto, midia = meta_da_pagina(link)
    arq = baixar_video(link)
    if not arq and midia.get("video"):
        try:
            dados, _ = baixar(midia["video"], limite=MAX_MB * 1024 * 1024)
            if len(dados) <= MAX_MB * 1024 * 1024:
                arq = os.path.join(AQUI, "_video_tmp.mp4")
                open(arq, "wb").write(dados)
                log("Video baixado pelo link publico da pagina:", link)
        except Exception as e:
            log("Nao consegui baixar o video da pagina:", str(e)[:120])
    if arq:
        dados = open(arq, "rb").read()
        ext = os.path.splitext(arq)[1].lower()
        partes = [{"inline_data": {"mime_type": MIME.get(ext, "video/mp4"), "data": base64.b64encode(dados).decode()}},
                  {"text": PEDIDO.format(obs=obs, extra="Link original: " + link + ("\nLegenda publica: " + texto if texto else ""))}]
        return gemini(partes)
    partes = []
    if midia.get("imagem"):
        try:
            dados, ctype = baixar(midia["imagem"], limite=8 * 1024 * 1024)
            if dados and "image" in (ctype or "image/jpeg"):
                partes.append({"inline_data": {"mime_type": (ctype or "image/jpeg").split(";")[0], "data": base64.b64encode(dados).decode()}})
        except Exception as e:
            log("Nao consegui baixar a imagem:", str(e)[:120])
    if not texto and not partes:
        return ("Nao consegui ler nada publico deste link (rede bloqueou o acesso sem login). "
                "Claude: listar no resumo de domingo para decidir o plano B.")
    extra = ("Texto publico encontrado no post:\n" + texto) if texto else "Sem legenda publica; analise a imagem do post."
    return gemini(partes + [{"text": PEDIDO.format(obs=obs, extra=extra)}])


def main():
    if not KEY:
        return
    agora = dt.datetime.now(TZ)
    if not (8 <= agora.hour <= 22):
        return
    try:
        d, _ = baixar(PLANILHA)
        txt = d.decode("utf-8-sig", "replace")
    except Exception as e:
        log("Nao consegui ler a planilha de inspiracoes:", str(e)[:150]); return
    if txt.lstrip().startswith("<"):
        log("Planilha de inspiracoes nao esta compartilhada como 'Qualquer pessoa com o link: Leitor'."); return
    estado = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {"feitos": []}
    feitos = set(estado["feitos"])
    novos = []
    for l in csv.DictReader(io.StringIO(txt)):
        l = {(k or "").strip().lower(): (v or "").strip() for k, v in l.items()}
        link, video = l.get("link", ""), l.get("video", "")
        texto = l.get("legenda_ou_texto", "")
        if not (link or video or texto):
            continue
        chave = hashlib.md5(("v2|" + link + "|" + video + "|" + texto).encode()).hexdigest()[:12]
        if chave not in feitos:
            novos.append((chave, l))
    if not novos:
        return
    blocos = []
    for chave, l in novos[:POR_RODADA]:
        link, video, obs, texto = l.get("link", ""), l.get("video", ""), l.get("observacao", ""), l.get("legenda_ou_texto", "")
        try:
            if texto and not video and not link:
                analise = gemini([{"text": PEDIDO.format(obs=obs or "(nenhuma)", extra="Texto enviado pelo Kalebe:\n" + texto)}])
            else:
                analise = analisar(link, video, obs)
                if texto:
                    analise += "\n\n**Texto colado pelo Kalebe:** " + texto[:500]
        except Exception as e:
            msg = str(e)
            if any(c in msg for c in ("429", "503", "500", "timed out")):
                log("Gemini indisponivel agora, tento na proxima rodada:", msg[:100]); break
            analise = "Falhou ao analisar: " + msg[:200]
        feitos.add(chave)
        blocos.append(f"## {l.get('data', '') or agora.strftime('%d/%m/%Y')} | {link or video or 'texto'}\n{analise}\n")
        log("Lida:", link or video or "texto")
    if blocos:
        antigo = open(SAIDA, encoding="utf-8").read() if os.path.exists(SAIDA) else ""
        cabecalho = "# Inspiracoes lidas pelo Gemini (mais novas primeiro)\n\n"
        corpo = antigo.replace(cabecalho, "")
        refeitos = {b.split("\n", 1)[0].split(" | ", 1)[-1] for b in blocos}
        corpo = "\n".join(x for x in re.split(r"(?m)^(?=## )", corpo)
                          if x.strip() and x.split("\n", 1)[0].split(" | ", 1)[-1] not in refeitos)
        corpo = ("\n".join(blocos) + "\n" + corpo)[:60000]
        open(SAIDA, "w", encoding="utf-8").write(cabecalho + corpo.strip() + "\n")
    estado["feitos"] = sorted(feitos)[-2000:]
    json.dump(estado, open(ESTADO, "w"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Erro geral (o robo principal nao e afetado):", str(e)[:200])
