# -*- coding: utf-8 -*-
import io
from PIL import Image, ImageOps
import pytesseract, config
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_EXE

with open(r"trouble_images\0003157620_001_20180711110906175.jpg", "rb") as f:
    pil = Image.open(io.BytesIO(f.read())).convert("RGB")
w, h = pil.size

def toks(g, lang, psm):
    cfg = f"--oem 1 --psm {psm} --tessdata-dir {config.TESSDATA_DIR}"
    d = pytesseract.image_to_data(g, lang=lang, config=cfg,
                                  output_type=pytesseract.Output.DICT)
    return [(t.strip(), int(c)) for t, c in zip(d["text"], d["conf"])
            if t.strip() and float(c) >= 30]

box = (0.58, 0.85, 1.00, 1.00)
crop = pil.crop((int(w*box[0]), int(h*box[1]), int(w*box[2]), int(h*box[3])))
cw, ch = crop.size
for zoom in (3, 5, 7):
    big = crop.resize((cw*zoom, ch*zoom), Image.LANCZOS)
    g = ImageOps.autocontrast(ImageOps.grayscale(big), cutoff=2)
    for lang in ("eng", "kor+eng"):
        for psm in (7, 6, 11):
            t = toks(g, lang, psm)
            if t:
                print(f"zoom{zoom} {lang:7s} psm{psm}: {t[:8]}")
