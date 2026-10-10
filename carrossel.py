# -*- coding: utf-8 -*-
"""
Artes dos carrosseis: desenha cada slide (1080x1350) e hospeda no repositorio publico de imagens (MIDIA_REPO).
- O texto vem pronto da fila (carrosseis/fila/car-*.json); *palavras entre asteriscos* saem na cor de destaque.
- Hospedagem: API do GitHub com o Secret GH_PAT (variavel MIDIA_TOKEN), que nunca aparece em log.
- Qualquer falha vira excecao curta; quem chama decide (o robo nunca para por causa daqui).
"""
import os, io, json, base64, subprocess, sys, urllib.request, urllib.error

W, H = 1080, 1350
FUNDO, TEXTO, DESTAQUE, CINZA = (17, 17, 19), (245, 245, 240), (245, 165, 36), (140, 140, 140)
PASTA_FONTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fontes")
MIDIA_REPO = os.environ.get("MIDIA_REPO", "").strip() or "mikaelkalebe6/robo-midia"
TOKEN = os.environ.get("MIDIA_TOKEN", "").strip()
PERFIL = os.environ.get("CARROSSEL_ASSINATURA", "").strip() or "@lorenafleck_"


def configurado():
    return bool(TOKEN)


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # o servidor do GitHub nao traz o Pillow: instala so quando precisa
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "pillow"], check=True, timeout=90)
        import site
        if site.getusersitepackages() not in sys.path:
            sys.path.append(site.getusersitepackages())
        from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


def _fonte(ImageFont, nome, tam):
    try:
        return ImageFont.truetype(os.path.join(PASTA_FONTES, nome), tam)
    except Exception:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", tam)


def _quebrar(d, texto, f, largura):
    linhas = []
    for par in texto.split("\n"):
        atual = ""
        for w in par.split():
            t = (atual + " " + w).strip()
            if d.textlength(t.replace("*", ""), font=f) <= largura:
                atual = t
            else:
                linhas.append(atual)
                atual = w
        linhas.append(atual)
    return linhas


def desenhar(texto, n, total, rotulo=""):
    """PNG (bytes) de um slide. n=1 e a capa (fonte maior e 'arrasta')."""
    Image, ImageDraw, ImageFont = _pil()
    capa = n == 1
    im = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(im)
    tam = 92 if capa else 64
    f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
    pequena = _fonte(ImageFont, "InterDisplay-Bold.otf", 32)
    m = 96
    linhas = _quebrar(d, texto, f, W - 2 * m)
    altura = int(tam * 1.22)
    y = (H - altura * len(linhas)) // 2 - (40 if capa else 0)
    if rotulo:
        d.text((m, y - 110), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 34), fill=DESTAQUE)
    for linha in linhas:
        x, ligado = m, False
        for parte in linha.split("*"):
            if parte:
                d.text((x, y), parte, font=f, fill=DESTAQUE if ligado else TEXTO)
                x += d.textlength(parte, font=f)
            ligado = not ligado
        y += altura
    d.rectangle([m, H - 150, m + 90, H - 142], fill=DESTAQUE)
    d.text((m, H - 120), PERFIL, font=pequena, fill=CINZA)
    cont = f"{n}/{total}"
    d.text((W - m - d.textlength(cont, font=pequena), H - 120), cont, font=pequena, fill=CINZA)
    if capa:
        d.text((W - m - d.textlength("arrasta  >", font=pequena), H - 190), "arrasta  >", font=pequena, fill=DESTAQUE)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def hospedar(caminho, png):
    """Sobe o PNG no repositorio publico de imagens e devolve o link direto (raw)."""
    if not TOKEN:
        raise RuntimeError("Carrossel sem hospedagem (falta o Secret GH_PAT com acesso ao repositorio de imagens)")
    url = f"https://api.github.com/repos/{MIDIA_REPO}/contents/{caminho}"
    corpo = json.dumps({"message": f"arte {caminho}", "content": base64.b64encode(png).decode()}).encode()
    req = urllib.request.Request(url, data=corpo, method="PUT", headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        if e.code != 422:  # 422 = arquivo ja existe (rodada repetida): usa o mesmo link
            raise RuntimeError(f"GitHub recusou a arte ({e.code})")
    except Exception as e:
        raise RuntimeError(f"Hospedagem da arte falhou: {str(e)[:150]}")
    return f"https://raw.githubusercontent.com/{MIDIA_REPO}/main/{caminho}"


def preparar(car, prod):
    """Completa o url de cada slide: arte desenhada e hospedada, ou a foto do produto. Devolve a lista de urls."""
    slides = car.get("slides") or []
    urls = []
    for i, sl in enumerate(slides, 1):
        if sl.get("url"):
            urls.append(sl["url"])
        elif sl.get("foto_produto"):
            if not prod.get("imageUrl"):
                raise RuntimeError("slide de foto sem imagem do produto")
            urls.append(prod["imageUrl"])
        else:
            png = desenhar(sl.get("texto", ""), i, len(slides), sl.get("rotulo", ""))
            urls.append(hospedar(f"car/{car['id']}-s{i}.png", png))
    return urls
