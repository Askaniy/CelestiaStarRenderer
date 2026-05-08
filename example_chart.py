import numpy as np
from PIL import Image, ImageDraw, ImageFont

from CSR import RenderEngine, OriginalPSF, gamma_correction, img2array


# Settings

# Exposure time in seconds
# Exposure of 1 means that Vega occupies a single pixel with no bloom effect, and 5 means that
# this is true for a source 5 times dimmer than Vega, while Vega itself get a noticeable bloom.
exposure = 1. # variable

# Size of the source in the point rendering mode
# 1.5 works for the most cases. However, you can increase it for high DPI screens.
point_radius_px = 1.5

# Data to be shown
# Magnitudes of sources to be rendered and their color
list_of_mags = range(3, -6, -1)
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
w = col_zero + 2 * col_size * col_num
w = w + scale_factor - w % scale_factor
h = row_zero + row_size * (len(list_of_mags) + 1)
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
    OriginalPSF(w, h, deg_per_px=0.027 / point_radius_px),
    RenderEngine(w, h, optimization=0.0, point_radius_px=point_radius_px),
    RenderEngine(w, h, optimization=0.1, point_radius_px=point_radius_px),
    RenderEngine(w, h, optimization=1.0, point_radius_px=point_radius_px),
]

# The sources rendering cycle
for i, engine in enumerate(engines):
    x_shift = col_zero + (2*i+1) * col_size
    for j, star_mag in enumerate(list_of_mags):
        peak_radiance = 10**(-0.4 * star_mag) * exposure # scaled radiance measured in Vegas
        coords = (x_shift // scale_factor, (row_zero + row_size * (j+1)) // scale_factor)
        arr = engine.draw_source(coords, peak_radiance, source_color, canvas=arr)

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
