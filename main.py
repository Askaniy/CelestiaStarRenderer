from pathlib import Path
from PIL import Image
import numpy as np
import algorithms
import auxiliary

# Path of the working directory
path = Path(__file__).parent.resolve()


# Settings

# Angular scale factor
# Default is 0.05. Can be higher, but lower values are less realistic in the central brightness peak
degree_per_px = 0.05 # variable

# Exposure, measured in brightness of Vega
# Exposure of 1 means that Vega occupies a single pixel with no glow, and 5 means that
# this is true for a star 5 times dimmer than Vega, while Vega itself get a noticeable glow.
exposure = 1. # variable

# Data to be shown
# Magnitudes of stars to be rendered and their color
list_of_mags = range(1, -7, -1)
star_color = np.array([0.417, 0.612, 1.0]) # Vega without gamma correction

# Rendering mode
# The render area without gamma correction is much smaller (resulting in faster rendering), but not realistic.
# White background can show the effective render area, while red corners can show calculated boundaries.
gamma_correction = True # variable
white_background = False # variable
corners = False # variable

# The linear brightness limit after which a star color converted to 8-bit will be zero.
if gamma_correction:
    br_limit = 1 / (255 * 12.92) # gamma correction implementation of sRGB
else:
    br_limit = 1 / 255

# Reinforced concrete limitation on square size for the "Bounded" algorithm,
# and the brightness that the star would have with this square size, scaled by 2/pi as preparation for arctan().
max_square_size = 512 # px
max_br = (degree_per_px * max_square_size / algorithms.a)**2 / (2*np.pi)

# Chart properties
columns = {
    'Original': algorithms.draw_Original,
    'Optimized': algorithms.draw_Optimized,
    'Simplified': algorithms.draw_Simplified,
    'Bounded': algorithms.draw_Bounded
}
col_size = 100 # px
col_zero = 175 # px
row_size = 100 # px
row_zero = 50 # px

# Render scaling factor relative to the image, low-resolution render is needed to check the details
scale = 3

# Creating templates
img = auxiliary.create_img(
    list_of_mags, tuple(columns.keys()), col_size, col_zero, row_size, row_zero, str(path), white_background, scale
)
w, h = img.size
arr = np.zeros((h//scale, w//scale, 3))


# The stars rendering cycle

for i, algorithm in enumerate(columns.values()):
    x_shift = col_zero + (2*i+1) * col_size
    for j, star_mag in enumerate(list_of_mags):
        linear_br = 10**(-0.4 * star_mag) * exposure # scaled brightness measured in Vegas
        if linear_br < br_limit:
            print(f'\tStar {j} with mag={star_mag} is too dim to be displayed')
            continue
        coords = (x_shift // scale, (row_zero + row_size * (j+1)) // scale)
        arr = algorithm(arr, linear_br, star_color, coords, degree_per_px, corners, max_br)


# Applying gamma correction as the last step
if gamma_correction:
    arr = auxiliary.gamma_correction(arr)
arr = np.round(255 * arr).clip(0, 255).astype('uint8')
arr = auxiliary.scale_array(arr, scale)

# Adding numpy star renders to the image
if white_background:
    img = Image.fromarray(np.where(np.dstack([np.sum(arr, 2)]*3) != 0, arr, auxiliary.img2array(img)))
else:
    img = Image.fromarray(arr + auxiliary.img2array(img))
img.save(f'{path}/CSR_render.png')
