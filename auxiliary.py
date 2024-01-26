from PIL import Image, ImageDraw, ImageFont
from typing import Iterable, Sequence
import numpy as np


gamma_correction = np.vectorize(lambda br: br * 12.92 if br < 0.0031308 else 1.055 * br**(1.0/2.4) - 0.055)

def faintestMag2exposure(faintestMag, br_limit):
    return br_limit * 10**(0.4*faintestMag)

def exposure2faintestMag(exposure, br_limit):
    return 2.5 * np.log10(exposure/br_limit)

def create_img(list_of_mags: Iterable, columns: Sequence, col_size: int, col_zero: int,
               row_size: int, row_zero: int, path: str, white_background: bool, scale: int):
    """ A Pillow image initialization """
    col_num = len(columns)
    w = col_zero + col_size*col_num*2
    w = w + scale - w % scale
    h = row_zero + row_size * (len(list_of_mags) + 1)
    h = h + scale - h % scale
    img = Image.new('RGB', (w, h), 'white' if white_background else 'black')
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(f'{path}/NotoSans-DisplayCondensedSemiBold', 40)
    for i, column in enumerate(columns):
        draw.text((col_zero + (2*i+1)*col_size, row_zero), column, 'gray', font, anchor='mt')
    for i, star_mag in enumerate(list_of_mags):
        hight = row_zero + row_size * (i+1)
        draw.text((col_zero/2, hight), f'm = {star_mag}', 'gray', font, anchor='mm')
    return img

def scale_array(arr: np.ndarray, times: int):
    """ Applies tha same effect as the nearest interpolation to an array """
    return np.repeat(np.repeat(arr, times, axis=0), times, axis=1)

def img2array(img: Image.Image):
    """
    Converting a Pillow image to a numpy array
    1.5-2.5 times faster than np.array() and np.asarray()
    Based on https://habr.com/ru/articles/545850/
    """
    img.load()
    e = Image._getencoder(img.mode, 'raw', img.mode)
    e.setimage(img.im)
    shape, typestr = Image._conv_type_shape(img)
    data = np.empty(shape, dtype=np.dtype(typestr))
    mem = data.data.cast('B', (data.data.nbytes,))
    bufsize, s, offset = 65536, 0, 0
    while not s:
        l, s, d = e.encode(bufsize)
        mem[offset:offset + len(d)] = d
        offset += len(d)
    if s < 0:
        raise RuntimeError(f'encoder error {s} in tobytes')
    return data

def draw_corners(arr: np.ndarray, center: tuple[int, int], half_sq: int):
    hight, width, channels = arr.shape
    if 0 < (i := center[0]-half_sq) < width and 0 < (j := center[1]-half_sq) < hight:
        arr[j, i, 0] = arr[j, i+1, 0] = arr[j+1, i, 0] = 1.
    if 0 < (i := center[0]-half_sq) < width and 0 < (j := center[1]+half_sq) < hight:
        arr[j, i, 0] = arr[j, i+1, 0] = arr[j-1, i, 0] = 1.
    if 0 < (i := center[0]+half_sq) < width and 0 < (j := center[1]-half_sq) < hight:
        arr[j, i, 0] = arr[j, i-1, 0] = arr[j+1, i, 0] = 1.
    if 0 < (i := center[0]+half_sq) < width and 0 < (j := center[1]+half_sq) < hight:
        arr[j, i, 0] = arr[j, i-1, 0] = arr[j-1, i, 0] = 1.
    return arr