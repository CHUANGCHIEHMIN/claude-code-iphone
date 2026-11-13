"""Photographic finishing: soft bloom, gentle S-curve, vignette, fine grain."""
import sys
import numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src)
a = np.asarray(im).astype(np.float32)
a = a / (65535.0 if a.max() > 255 else 255.0)
a = a[..., :3]
h, w = a.shape[:2]
# bloom from highlights
lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
hi = np.clip((lum - 0.80) / 0.20, 0, 1)[..., None] * a
hi8 = Image.fromarray((np.clip(hi, 0, 1) * 255).astype(np.uint8))
b1 = np.asarray(hi8.filter(ImageFilter.GaussianBlur(w / 160))).astype(np.float32) / 255
b2 = np.asarray(hi8.filter(ImageFilter.GaussianBlur(w / 40))).astype(np.float32) / 255
a = a + 0.22 * b1 + 0.18 * b2
# gentle S-curve around mid grey
a = np.clip(a, 0, 1)
a = a + 0.06 * np.sin((a - 0.5) * np.pi) * (a * (1 - a)) * 4 / 4
# vignette
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
a = a * (1 - 0.18 * r ** 2.2)[..., None]
# fine luminance grain
rng = np.random.default_rng(3)
a = a + rng.normal(0, 0.006, (h, w, 1)).astype(np.float32)
Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst, quality=94)
print('post ->', dst)
