import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from CSR import RenderEngine, gamma_correction, img2array


# Settings

# Exposure time in seconds
# Exposure of 1 means that Vega occupies a single pixel with no bloom effect, and 5 means that
# this is true for a source 5 times dimmer than Vega, while Vega itself get a noticeable bloom.
exposure = 1. # variable

# Size of the source in the point rendering mode
# 2 works for the most cases. However, you can increase it for high DPI screens.
point_radius = 2. # variable

# Data to be shown
# Magnitudes of sources to be rendered and their color
list_of_mags = range(2, -7, -1)
source_color = np.array([0.314, 0.561, 1.0]) # color of Vega without gamma correction

# Rendering mode
# The render area without gamma correction is much smaller (resulting in faster rendering), but not realistic.
# White background can show the effective render area.
gamma_correction_flag = True # variable
white_background_flag = False # variable

# Render scaling factor relative to the image, low-resolution render is needed to check the details
scale_factor = 3

# Chart properties
columns = [
    'Original',
    'Opt. = 0.0',
    'Opt. = 0.1',
    'Opt. = 1.0',
]
col_size = 100 # px
col_zero = 175 # px
row_size = 100 # px
row_zero = 50 # px

# Creating the chart
col_num = len(columns)
row_num = len(list_of_mags)
w = col_zero + 2 * col_size * col_num
w = w + scale_factor - w % scale_factor
h = row_zero + row_size * (row_num + 1)
h = h + scale_factor - h % scale_factor
img = Image.new('RGB', (w, h), 'white' if white_background_flag else 'black')
draw = ImageDraw.Draw(img)
font = ImageFont.truetype('fonts/NotoSans-DisplayCondensedSemiBold.ttf', 40)
for i, column in enumerate(columns):
    draw.text((col_zero + (2*i+1)*col_size, row_zero), column, 'gray', font, anchor='mt')
for i, star_mag in enumerate(list_of_mags):
    height = row_zero + row_size * (i+1)
    draw.text((col_zero/2, height), f'm = {star_mag}', 'gray', font, anchor='mm')

# Creating the canvas
W, H = img.size
w = W // scale_factor
h = H // scale_factor
arr = np.zeros((h, w, 3))

engines = [
    RenderEngine(w, h, point_radius=point_radius, optimization=None),
    RenderEngine(w, h, point_radius=point_radius, optimization=0.0),
    RenderEngine(w, h, point_radius=point_radius, optimization=0.1),
    RenderEngine(w, h, point_radius=point_radius, optimization=1.0),
]

# The sources rendering cycle
for i, engine in enumerate(engines):
    x_shift = col_zero + (2*i+1) * col_size
    start = time.time()
    for j, star_mag in enumerate(list_of_mags):
        irradiance = 10**(-0.4 * star_mag) * exposure # in the "Vega normalized" system
        coords = (x_shift // scale_factor, (row_zero + row_size * (j+1)) // scale_factor)
        arr = engine.draw_source(coords, irradiance, source_color, canvas=arr)
    end = time.time()
    dt = end - start
    print(f'Engine {i+1}: rendered {row_num} stars in {1000 * dt:.3f} ms')

# Post processing
arr = np.clip(arr, 0, 1)
if gamma_correction:
    arr = gamma_correction(arr)
arr = np.round(arr * 255).astype('uint8')
arr = np.repeat(np.repeat(arr, scale_factor, axis=0), scale_factor, axis=1)

# Adding numpy renders to the chart
if white_background_flag:
    img = Image.fromarray(np.where(np.dstack([np.sum(arr, 2)]*3) != 0, arr, img2array(img)))
else:
    img = Image.fromarray(arr + img2array(img))

# Export
file_name = 'examples/example_chart.png'
print(f'The chart is saved as "{file_name}"')
img.save(file_name)
