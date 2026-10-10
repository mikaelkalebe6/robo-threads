# -*- coding: utf-8 -*-
"""
Artes dos carrosseis: desenha cada slide (1080x1350) e hospeda no repositorio publico de imagens (MIDIA_REPO).
- O texto vem pronto da fila (carrosseis/fila/car-*.json); *palavras entre asteriscos* saem na cor de destaque.
- Hospedagem: API do GitHub com o Secret MIDIA_PAT (variavel MIDIA_TOKEN), token so do repositorio de imagens, que nunca aparece em log.
- Qualquer falha vira excecao curta; quem chama decide (o robo nunca para por causa daqui).
"""
import os, io, json, base64, subprocess, sys, urllib.request, urllib.error

W, H = 1080, 1350
# temas sorteados por carrossel (aleatoriedade ate acharmos o melhor visual): fundo, texto, destaque, cinza
TEMAS = {
    "e": ((17, 17, 19), (245, 245, 240), (245, 165, 36), (140, 140, 140)),   # escuro com ambar
    "c": ((246, 244, 238), (22, 22, 24), (214, 90, 30), (120, 120, 120)),    # claro com laranja
    "a": ((245, 165, 36), (20, 20, 20), (255, 255, 255), (60, 50, 30)),      # ambar com branco
    "v": ((16, 38, 30), (240, 240, 232), (120, 220, 150), (130, 150, 140)),  # verde escuro
}
# foto do produto: m = so nos slides marcados com_foto, c = so na capa, n = nenhuma (so texto)
MODOS_FOTO = ("m", "c", "n")
FUNDO, TEXTO, DESTAQUE, CINZA = TEMAS["e"]
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


def baixar_foto(url):
    """Foto do produto (bytes) para colocar dentro do slide."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def desenhar(texto, n, total, rotulo="", foto=None, tema="e"):
    """PNG (bytes) de um slide. n=1 e a capa (fonte maior e 'arrasta'). foto = bytes da imagem do produto
    (fica num cartao claro na parte de cima e o texto desce)."""
    Image, ImageDraw, ImageFont = _pil()
    FUNDO, TEXTO, DESTAQUE, CINZA = TEMAS.get(tema, TEMAS["e"])
    capa = n == 1
    im = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(im)
    tam = 92 if capa else 64
    f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
    pequena = _fonte(ImageFont, "InterDisplay-Bold.otf", 32)
    m = 96
    topo = 0
    if foto:
        tam = 80 if capa else 56
        f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
        img = Image.open(io.BytesIO(foto)).convert("RGB")
        caixa = (W - 2 * m, 600)
        img.thumbnail((caixa[0] - 60, caixa[1] - 60))
        d.rounded_rectangle([m, 90, W - m, 90 + caixa[1]], radius=36, fill=(250, 250, 248))
        im.paste(img, (m + (caixa[0] - img.width) // 2, 90 + (caixa[1] - img.height) // 2))
        topo = 90 + caixa[1]
    linhas = _quebrar(d, texto, f, W - 2 * m)
    altura = int(tam * 1.22)
    if foto:
        y = topo + 150
    else:
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
        raise RuntimeError("Carrossel sem hospedagem (falta o Secret MIDIA_PAT com acesso ao repositorio de imagens)")
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


def sortear_visual(car):
    """Visual do carrossel: 'tema+modo' (ex.: 'em'). O JSON pode fixar com "visual"; senao sorteia."""
    import random
    v = str(car.get("visual") or "")
    if len(v) == 2 and v[0] in TEMAS and v[1] in MODOS_FOTO:
        return v
    return random.choice(list(TEMAS)) + random.choice(MODOS_FOTO)


def preparar(car, prod):
    """Completa o url de cada slide: arte desenhada e hospedada, ou a foto do produto.
    Devolve (lista de urls, visual sorteado)."""
    slides = car.get("slides") or []
    visual = sortear_visual(car)
    tema, modo = visual[0], visual[1]
    urls = []
    for i, sl in enumerate(slides, 1):
        if sl.get("url"):
            urls.append(sl["url"])
        elif sl.get("foto_produto"):
            if not prod.get("imageUrl"):
                raise RuntimeError("slide de foto sem imagem do produto")
            urls.append(prod["imageUrl"])
        else:
            foto = None
            quer_foto = (modo == "m" and sl.get("com_foto")) or (modo == "c" and i == 1)
            if quer_foto and prod.get("imageUrl"):
                try:
                    foto = baixar_foto(prod["imageUrl"])
                except Exception:
                    foto = None  # sem foto o slide sai so com texto
            png = desenhar(sl.get("texto", ""), i, len(slides), sl.get("rotulo", ""), foto, tema)
            urls.append(hospedar(f"car/{car['id']}-{visual}-s{i}.png", png))
    return urls, visual
