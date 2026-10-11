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


def _cobrir(Image, img, w, h, subir=3):
    """Recorta a imagem para preencher w x h sem distorcer (corte no centro, um pouco para cima)."""
    iw, ih = img.size
    esc = max(w / iw, h / ih)
    img = img.resize((max(w, int(iw * esc + 0.5)), max(h, int(ih * esc + 0.5))))
    x = (img.width - w) // 2
    y = max(0, (img.height - h) // subir)
    return img.crop((x, y, x + w, y + h))


def _texto_destacado(d, linhas, f, x0, y, altura, cor, destaque, sombra=None):
    ligado = False  # o destaque continua na linha seguinte quando o *trecho* quebra de linha
    for linha in linhas:
        x = x0
        partes = linha.split("*")
        for k, parte in enumerate(partes):
            if parte:
                if sombra:
                    d.text((x + 3, y + 3), parte, font=f, fill=sombra)
                d.text((x, y), parte, font=f, fill=destaque if ligado else cor)
                x += d.textlength(parte, font=f)
            if k < len(partes) - 1:  # so troca onde existe um * de verdade
                ligado = not ligado
        y += altura
    return y


def _selo(d, ImageFont, texto, x, y, fundo, cor):
    """Etiqueta curta (preco, nota, vendidos) em formato de pilula."""
    f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf", 40)
    larg = int(d.textlength(texto, font=f)) + 56
    d.rounded_rectangle([x, y, x + larg, y + 72], radius=36, fill=fundo)
    d.text((x + 28, y + 12), texto, font=f, fill=cor)


def _rodape(d, ImageFont, n, total, capa, cinza, destaque, sobre_foto=False):
    m = 96
    pequena = _fonte(ImageFont, "InterDisplay-Bold.otf", 32)
    cor = (235, 235, 230) if sobre_foto else cinza
    d.rectangle([m, H - 150, m + 90, H - 142], fill=destaque)
    d.text((m, H - 120), PERFIL, font=pequena, fill=cor)
    cont = f"{n}/{total}"
    d.text((W - m - d.textlength(cont, font=pequena), H - 120), cont, font=pequena, fill=cor)
    if capa:
        d.text((W - m - d.textlength("arrasta  >", font=pequena), H - 190), "arrasta  >", font=pequena, fill=destaque)


ACENTO_MANCHETE = (232, 58, 36)  # vermelho-laranja das referencias de 10/10 (marca-texto atras das palavras)


def _manchete(Image, ImageDraw, ImageFont, texto, n, total, rotulo, img, sub, tom, contem, selo, inteira=False, texto_pos="baixo"):
    """Estilo "manchete condensada" (referencias de 10/10: letras enormes condensadas em caixa alta,
    rotulo pequeno em cima, *palavra* em marca-texto colorido, foto ou produto embaixo, fundo claro ou escuro)."""
    inteira = inteira and img is not None
    claro = tom == "claro" and not inteira
    fundo = (244, 241, 234) if claro else (14, 14, 16)
    cor = (18, 18, 18) if claro else (247, 245, 238)
    cinza = (110, 108, 102) if claro else (170, 170, 170)
    if inteira:  # foto no slide inteiro (capa de cinema), degradê escuro embaixo e manchete por cima
        im = _cobrir(Image, img, W, H)
        sombra = Image.new("L", (1, H))
        topo_txt = texto_pos == "topo"
        for yy in range(H):  # escurece so a faixa do texto; o resto da foto (a cena que vende) fica limpo
            yv = (H - yy) if topo_txt else yy
            v = int(max(0, min(1, (yv - H * 0.52) / (H * 0.36))) ** 1.2 * 225)
            if topo_txt:
                v = max(v, int(max(0, min(1, (yy - (H - 200)) / 160)) * 170))  # rodape legivel
            sombra.putpixel((0, yy), v)
        im = Image.composite(Image.new("RGB", (W, H), (6, 6, 8)), im, sombra.resize((W, H)))
        img = None
    else:
        im = Image.new("RGB", (W, H), fundo)
    d = ImageDraw.Draw(im)
    m, capa = 80, n == 1
    area_txt = int(H * ((0.44 if contem else 0.56) if img is not None else 0.80))  # produto: foto grande, ela e a prova
    if inteira:
        area_txt = int(H * 0.36) + 120  # capa de cinema: o texto ocupa no maximo ~1/3 e nao come a cena
    y0 = 120
    if rotulo and not inteira and img is not None:
        d.text((m, y0), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 30), fill=ACENTO_MANCHETE)
        y0 += 62
    elif rotulo and not inteira:
        y0 += 62  # o rotulo e desenhado depois, junto com o bloco centralizado
    texto_up = texto.upper()
    tam = (118 if inteira else 150) if capa else 124
    while tam > 60:
        f = _fonte(ImageFont, "Anton-Regular.ttf", tam)
        linhas = _quebrar(d, texto_up, f, W - 2 * m - 20)
        altura = int(tam * 1.16)
        if y0 + altura * len(linhas) <= area_txt - (70 if sub else 0):
            break
        tam -= 6
    if img is None and not inteira:  # sem foto: bloco de texto centralizado na altura (nada de metade vazia)
        bloco = altura * len(linhas) + (62 if rotulo else 0) + (46 * min(3, len(_quebrar(d, sub, _fonte(ImageFont, "InterDisplay-Bold.otf", 36), W - 2 * m))) + 18 if sub else 0)
        y0 = max(120, (H - 150 - bloco) // 2) + (62 if rotulo else 0)
        if rotulo:
            d.text((m, y0 - 62), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 30), fill=ACENTO_MANCHETE)
    if inteira and texto_pos == "topo":
        y0 = 120 + (62 if rotulo else 0)
    elif inteira:  # texto colado embaixo
        y0 = H - 170 - (70 if sub else 0) - altura * len(linhas)
        if rotulo:
            d.text((m, y0 - 62), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 30), fill=ACENTO_MANCHETE)
    # 2 passadas: primeiro todas as faixas do marca-texto, depois todo o texto (a faixa da linha de baixo
    # nao pode cobrir a cedilha da linha de cima: "PESCOCO" em 11/10)
    for passada in (0, 1):
        y = y0
        ligado = False
        for linha in linhas:
            x = m
            partes = linha.split("*")
            for k, parte in enumerate(partes):
                if parte:
                    larg = d.textlength(parte, font=f)
                    if passada == 0 and ligado:
                        bx = d.textbbox((x, y), parte, font=f)
                        ref = d.textbbox((x, y), "HÁ", font=f)  # altura fixa: Ç e acento nao esticam a faixa
                        d.rectangle([bx[0] - 10, ref[1] - 8, bx[2] + 10, ref[3] + 8], fill=ACENTO_MANCHETE)
                    if passada == 1:
                        d.text((x, y), parte, font=f, fill=(255, 255, 255) if ligado else cor)
                    x += larg
                if k < len(partes) - 1:
                    ligado = not ligado
            y += altura
    if sub:
        fs = _fonte(ImageFont, "InterDisplay-Bold.otf", 36)
        for ls in _quebrar(d, sub, fs, W - 2 * m)[:3]:
            d.text((m, y + 18), ls.replace("*", ""), font=fs, fill=cinza)
            y += 46
    if img is not None:
        topo = max(y + 50, area_txt)
        alt = H - 150 - topo
        if contem:
            caixa = Image.new("RGB", (W - 2 * m, alt), (255, 255, 255))
            foto = img.copy()
            esc = min((W - 2 * m - 30) / foto.width, (alt - 30) / foto.height)  # amplia ou reduz para encher a caixa
            foto = foto.resize((max(1, int(foto.width * esc)), max(1, int(foto.height * esc))))
            caixa.paste(foto, ((caixa.width - foto.width) // 2, (alt - foto.height) // 2))
            im.paste(caixa, (m, topo))
        else:
            im.paste(_cobrir(Image, img, W - 2 * m, alt), (m, topo))
        if selo:
            _selo(d, ImageFont, selo, m + 24, topo + 24, ACENTO_MANCHETE, (255, 255, 255))
    elif selo:
        _selo(d, ImageFont, selo, m, H - 260, ACENTO_MANCHETE, (255, 255, 255))
    pequena = _fonte(ImageFont, "InterDisplay-Bold.otf", 28)
    d.text((m, H - 100), PERFIL, font=pequena, fill=cinza)
    num = f"{n}/{total}"
    d.text((W - m - d.textlength(num, font=pequena), H - 100), num, font=pequena, fill=cinza)
    if capa:
        d.text((W - m - d.textlength("arrasta >", font=pequena) - 90, H - 100), "arrasta >", font=pequena, fill=ACENTO_MANCHETE)
    return im


def _meme(Image, ImageDraw, ImageFont, texto, n, total, img):
    """Estilo "meme de reacao" (referencias de 10/10): foto inteira, legenda curta em minusculas,
    branca e centralizada no terco de baixo, com degradê para ler."""
    im = _cobrir(Image, img, W, H)
    sombra = Image.new("L", (1, H))
    for yy in range(H):
        sombra.putpixel((0, yy), int(max(0, min(1, (yy - H * 0.45) / (H * 0.45))) * 215))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, sombra.resize((W, H)))
    d = ImageDraw.Draw(im)
    f = _fonte(ImageFont, "InterDisplay-Bold.otf", 58)
    linhas = _quebrar(d, texto, f, W - 200)
    altura = 72
    y = H - 210 - altura * len(linhas)
    for linha in linhas:
        limpa = linha.replace("*", "")
        x = (W - d.textlength(limpa, font=f)) // 2
        d.text((x + 2, y + 2), limpa, font=f, fill=(0, 0, 0))
        d.text((x, y), limpa, font=f, fill=(255, 255, 255))
        y += altura
    pequena = _fonte(ImageFont, "InterDisplay-Bold.otf", 26)
    d.text((70, 60), PERFIL, font=pequena, fill=(235, 235, 235))
    num = f"{n}/{total}"
    d.text((W - 70 - d.textlength(num, font=pequena), 60), num, font=pequena, fill=(235, 235, 235))
    return im


def desenhar(texto, n, total, rotulo="", foto=None, tema="e", layout="", imagem=None, selo="", texto_pos="baixo",
             sub="", tom="", contem=False, inteira=False):
    """PNG (bytes) de um slide 1080x1350. n=1 e a capa (fonte maior e 'arrasta').
    layout (escolhido pelo Claude no JSON; vazio = cartao antigo):
      - "fundo":   imagem ocupando o slide inteiro, degradê escuro embaixo e o texto por cima (para o dedo).
      - "split":   imagem grande na metade de cima (sangrando nas bordas) e texto embaixo.
      - "produto": foto do produto grande e limpa, como vitrine, com titulo curto em cima e selo (preco/nota).
      - "" ou "card": foto pequena num cartao claro (visual de 10/10) ou so texto.
    imagem = bytes da cena (IA ou foto do produto); foto = bytes da foto do produto no layout antigo."""
    Image, ImageDraw, ImageFont = _pil()
    FUNDO, TEXTO, DESTAQUE, CINZA = TEMAS.get(tema, TEMAS["e"])
    capa = n == 1
    m = 96
    img = None
    if imagem:
        try:
            img = Image.open(io.BytesIO(imagem)).convert("RGB")
        except Exception:
            img = None
    if layout in ("fundo", "split", "produto", "meme") and img is None:
        layout = "manchete" if layout == "meme" else ""  # sem imagem: meme vira manchete; o resto cai no cartao antigo

    if layout in ("manchete", "meme"):
        im = (_meme(Image, ImageDraw, ImageFont, texto, n, total, img) if layout == "meme" else
              _manchete(Image, ImageDraw, ImageFont, texto, n, total, rotulo, img, sub,
                        tom or ("claro" if tema in ("c", "a") else "escuro"), contem, selo, inteira, texto_pos))
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue()

    if layout == "fundo":
        # texto_pos (escolhido por slide no JSON): "baixo" (padrao) ou "topo", conforme onde a foto tem espaco livre
        topo_txt = texto_pos == "topo"
        im = _cobrir(Image, img, W, H)
        sombra = Image.new("L", (1, H))
        for yy in range(H):  # degradê escuro so do lado do texto
            yv = (H - yy) if topo_txt else yy
            v = int(max(0, min(1, (yv - H * 0.30) / (H * 0.55))) ** 1.3 * 235)
            if topo_txt:  # faixa escura leve no rodape para o @ e o "arrasta" continuarem legiveis
                v = max(v, int(max(0, min(1, (yy - (H - 300)) / 220)) * 190))
            sombra.putpixel((0, yy), v)
        preto = Image.new("RGB", (W, H), (8, 8, 10))
        im = Image.composite(preto, im, sombra.resize((W, H)))
        d = ImageDraw.Draw(im)
        tam = 88 if capa else 62
        f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
        linhas = _quebrar(d, texto, f, W - 2 * m)
        altura = int(tam * 1.18)
        y = (170 if rotulo else 110) if topo_txt else H - 230 - altura * len(linhas)
        if rotulo:
            d.text((m, y - 70), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 34), fill=DESTAQUE)
        _texto_destacado(d, linhas, f, m, y, altura, (250, 250, 246), DESTAQUE, sombra=(0, 0, 0))
        if selo:
            _selo(d, ImageFont, selo, m, H - 330 if topo_txt else 90, DESTAQUE, (15, 15, 15))
        _rodape(d, ImageFont, n, total, capa, CINZA, DESTAQUE, sobre_foto=True)
    elif layout == "split":
        im = Image.new("RGB", (W, H), FUNDO)
        alto = 760
        im.paste(_cobrir(Image, img, W, alto), (0, 0))
        d = ImageDraw.Draw(im)
        tam = 76 if capa else 56
        f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
        linhas = _quebrar(d, texto, f, W - 2 * m)
        altura = int(tam * 1.2)
        y = alto + 70
        if rotulo:
            d.text((m, y), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 32), fill=DESTAQUE)
            y += 60
        _texto_destacado(d, linhas, f, m, y, altura, TEXTO, DESTAQUE)
        if selo:
            _selo(d, ImageFont, selo, m, alto - 110, DESTAQUE, (15, 15, 15))
        _rodape(d, ImageFont, n, total, capa, CINZA, DESTAQUE)
    elif layout == "produto":
        im = Image.new("RGB", (W, H), (255, 255, 255))  # branco: funde com o fundo das fotos da Shopee
        d = ImageDraw.Draw(im)
        tam = 70 if capa else 58
        f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf", tam)
        linhas = _quebrar(d, texto, f, W - 2 * m)[:3]
        altura = int(tam * 1.18)
        y = 110
        if rotulo:
            d.text((m, y), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 32), fill=DESTAQUE if tema != "c" else (214, 90, 30))
            y += 58
        y = _texto_destacado(d, linhas, f, m, y, altura, (22, 22, 24), (214, 90, 30) if tema in ("c", "a") else DESTAQUE)
        caixa_topo = y + 40
        caixa_alt = H - 220 - caixa_topo
        foto = img.copy()
        foto.thumbnail((W - 2 * m, caixa_alt))
        d.ellipse([W // 2 - 380, caixa_topo + caixa_alt - 70, W // 2 + 380, caixa_topo + caixa_alt + 10], fill=(238, 238, 234))
        im.paste(foto, ((W - foto.width) // 2, caixa_topo + (caixa_alt - foto.height) // 2))
        if selo:
            _selo(d, ImageFont, selo, W - m - 20 - int(d.textlength(selo, font=_fonte(ImageFont, "InterDisplay-ExtraBold.otf", 40))) - 56,
                  caixa_topo + 10, DESTAQUE if tema != "c" else (214, 90, 30), (15, 15, 15) if tema != "c" else (255, 255, 255))
        _rodape(d, ImageFont, n, total, capa, (120, 120, 120), DESTAQUE if tema != "c" else (214, 90, 30))
    else:
        im = Image.new("RGB", (W, H), FUNDO)
        d = ImageDraw.Draw(im)
        tam = 92 if capa else 64
        f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
        topo = 0
        if foto is None and img is not None:
            foto_img = img
        elif foto:
            foto_img = Image.open(io.BytesIO(foto)).convert("RGB")
        else:
            foto_img = None
        if foto_img is not None:
            tam = 80 if capa else 56
            f = _fonte(ImageFont, "InterDisplay-ExtraBold.otf" if capa else "InterDisplay-Bold.otf", tam)
            caixa = (W - 2 * m, 600)
            foto_img.thumbnail((caixa[0] - 60, caixa[1] - 60))
            d.rounded_rectangle([m, 90, W - m, 90 + caixa[1]], radius=36, fill=(250, 250, 248))
            im.paste(foto_img, (m + (caixa[0] - foto_img.width) // 2, 90 + (caixa[1] - foto_img.height) // 2))
            topo = 90 + caixa[1]
        linhas = _quebrar(d, texto, f, W - 2 * m)
        altura = int(tam * 1.22)
        y = topo + 150 if foto_img is not None else (H - altura * len(linhas)) // 2 - (40 if capa else 0)
        if rotulo:
            d.text((m, y - 110), rotulo.upper(), font=_fonte(ImageFont, "InterDisplay-Bold.otf", 34), fill=DESTAQUE)
        _texto_destacado(d, linhas, f, m, y, altura, TEXTO, DESTAQUE)
        _rodape(d, ImageFont, n, total, capa, CINZA, DESTAQUE)
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


def pronto(car, agora_ts=None):
    """Carrossel com imagem de IA pedida ("imagem_ia") so sai depois que o workflow Artes IA tentou gerar,
    ou se ja passou 1 dia do "criado" (aí sai com a foto do produto no lugar). Nunca trava a fila."""
    import time as _t
    falta = [s for s in car.get("slides") or [] if s.get("imagem_ia") and not s.get("imagem")]
    if not falta or car.get("ia_tentado"):
        return True
    try:
        criado = _t.mktime(_t.strptime(str(car.get("criado", ""))[:10], "%Y-%m-%d"))
    except Exception:
        return True
    return (agora_ts or _t.time()) - criado > 36 * 3600


def _imagem_do_slide(sl, prod):
    """Bytes da imagem do slide: link proprio ("imagem"), "produto" (foto da Shopee) ou nenhuma."""
    ref = sl.get("imagem") or ("produto" if sl.get("imagem_ia") else "")
    url = prod.get("imageUrl") if ref == "produto" else ref
    if not url:
        return None
    try:
        return baixar_foto(url)
    except Exception:
        if ref != "produto" and prod.get("imageUrl"):
            try:
                return baixar_foto(prod["imageUrl"])
            except Exception:
                return None
        return None


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
        elif sl.get("layout") in ("fundo", "split", "produto", "manchete", "meme"):
            img = _imagem_do_slide(sl, prod)
            png = desenhar(sl.get("texto", ""), i, len(slides), sl.get("rotulo", ""), None, tema,
                           layout=sl["layout"], imagem=img, selo=sl.get("selo", ""),
                           texto_pos=sl.get("texto_pos", "baixo"), sub=sl.get("sub", ""), tom=sl.get("tom", ""),
                           contem=sl.get("imagem") == "produto", inteira=bool(sl.get("foto_inteira")))
            urls.append(hospedar(f"car/{car['id']}-{visual}-s{i}.png", png))
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
