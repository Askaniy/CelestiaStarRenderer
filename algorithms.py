from math import floor
import numpy as np
import auxiliary


# Original PSF algorithm

def PSF_Original(theta: float):
    """ Unmodified photopic point source function from the research by Greg Spencer et al. """
    f0 = 2.61e6 * np.exp(-(50*theta)**2)
    f1 = 20.91 / (theta + 0.02)**3
    f2 = 72.37 / (theta + 0.02)**2
    return 0.384 * f0 + 0.478 * f1 + 0.138 * f2
PSF_Original_0deg = PSF_Original(0)

def draw_Original(arr: np.ndarray, br0: float, color0: np.ndarray, center: tuple[int, int],
                  degree_per_px: float = None, corners: bool = None, max_br: float = None):
    """
    Adds a star to the numpy array using the unmodified photopic PSF from the research by Greg Spencer et al.
    - br0 is the brightness of the star
    - theta is the angle in degrees from the pixel center to the star center
    """
    hight, width, length = arr.shape
    scaled_color = auxiliary.green_normalization(color0) * br0
    x = np.arange(width) - center[0]
    y = np.arange(hight) - center[1]
    xx, yy = np.meshgrid(x, y)
    theta = np.sqrt(xx*xx + yy*yy) * degree_per_px # array of distances to the center
    glow = PSF_Original(theta) / PSF_Original_0deg
    return arr + scaled_color * np.repeat(np.expand_dims(glow, axis=2), 3, axis=2)



# Optimized PSF algorithm

def PSF_Optimized(theta: float, min_theta: float, max_theta: float, h: float, k: float, b: float):
    """
    Human eye's point source function from the research by Greg Spencer et al., optimized to fit a square.
    Lower limit on brightness and angular size: 1 Vega and 0.05 degrees per pixel. No upper limits.
    """
    if theta < min_theta:
        return 1 # overexposed
    elif theta < max_theta:
        brackets = b / (theta - h) - 1
        return brackets * brackets / k
    else:
        return 0. # after max_theta function starts to grow again
PSF_Optimized = np.vectorize(PSF_Optimized)

def draw_Optimized(arr: np.ndarray, br0: float, color0: np.ndarray, center: tuple[int, int],
                   degree_per_px: float, corners: bool, max_br: float = None):
    """
    Adds a star to the numpy array using the "Optimized" photopic PSF from the research by Greg Spencer et al.
    Please note: subpixel render will not work well, star is assumed to be in the center.
    - br0 is the brightness of the star
    - theta is the angle in degrees from the pixel center to the star center
    """
    color = auxiliary.green_normalization(color0)
    scaled_color = color * br0
    if np.all(scaled_color < 1):
        # Option 1: single pixel render
        arr[center[1], center[0]] += scaled_color
    else:
        # Option 2: glow square render
        hight, width, length = arr.shape
        max_theta = 0.33435822702992773 * np.sqrt(br0) # glow radius
        h = 0.0082234880783653 * max_theta**0.7369983254906639 # h, k, b - common constants, depending originally on star brightness
        k = 38581.577272697796 * max_theta**2.368787717957141  # precision in decimal places can be reduced if necessary
        b = max_theta - h
        min_theta = h + b / (np.sqrt(k) + 1)
        half_sq = floor(max_theta / degree_per_px - 0.5)
        # -1/2 because we have +1/2 from central pixel, and -2/2 from side pixels where PSF=0
        if corners:
            arr = auxiliary.draw_corners(arr, center, half_sq)
        x_min = -min(half_sq, center[0])
        x_max = min(half_sq+1, width-center[0])
        y_min = -min(half_sq, center[1])
        y_max = min(half_sq+1, hight-center[1])
        x = np.arange(x_min, x_max)
        y = np.arange(y_min, y_max)
        xx, yy = np.meshgrid(x, y)
        theta = np.sqrt(xx*xx + yy*yy) * degree_per_px # array of distances to the center
        glow_bw = PSF_Optimized(theta, min_theta, max_theta, h, k, b) # in the [0, 1] range, like in Celestia
        glow_colored = scaled_color * np.repeat(np.expand_dims(glow_bw, axis=2), 3, axis=2)
        arr[center[1]+y_min:center[1]+y_max, center[0]+x_min:center[0]+x_max] += glow_colored
    return arr



# Simplified PSF algorithm

def PSF_Simplified(theta: float, min_theta: float, max_theta: float, k: float):
    """
    Human eye's point source function from the research by Greg Spencer et al., optimized to fit a square.
    Lower limit on brightness and angular size: 1 Vega and 0.05 degrees per pixel. No upper limits.
    """
    if theta < min_theta:
        return 1 # overexposed
    elif theta < max_theta:
        brackets = max_theta / theta - 1
        return k * brackets * brackets
    else:
        return 0. # after max_theta function starts to grow again
PSF_Simplified = np.vectorize(PSF_Simplified)

def draw_Simplified(arr: np.ndarray, br0: float, color0: np.ndarray, center: tuple[int, int],
                    degree_per_px: float, corners: bool, max_br: float = None):
    """
    Adds a star to the numpy array using the "Simplified" photopic PSF from the research by Greg Spencer et al.
    Please note: subpixel render will not work well, star is assumed to be in the center.
    - br0 is the brightness of the star
    - theta is the angle in degrees from the pixel center to the star center
    """
    color = auxiliary.green_normalization(color0)
    scaled_color = color * br0
    if np.all(scaled_color < 1):
        # Option 1: single pixel render
        arr[center[1], center[0]] += scaled_color
    else:
        # Option 2: glow square render
        hight, width, length = arr.shape
        max_theta = 0.2 * np.sqrt(br0) # glow radius
        k = 3.3e-5 * max_theta**-2.5 # common constant, depending originally on star brightness
        min_theta = max_theta / (k**-0.5 + 1)
        half_sq = floor(max_theta / degree_per_px - 0.5)
        # -1/2 because we have +1/2 from central pixel, and -2/2 from side pixels where PSF=0
        if corners:
            arr = auxiliary.draw_corners(arr, center, half_sq)
        x_min = -min(half_sq, center[0])
        x_max = min(half_sq+1, width-center[0])
        y_min = -min(half_sq, center[1])
        y_max = min(half_sq+1, hight-center[1])
        x = np.arange(x_min, x_max)
        y = np.arange(y_min, y_max)
        xx, yy = np.meshgrid(x, y)
        theta = np.sqrt(xx*xx + yy*yy) * degree_per_px # array of distances to the center
        glow_bw = PSF_Simplified(theta, min_theta, max_theta, k) # in the [0, 1] range, like in Celestia
        glow_colored = scaled_color * np.repeat(np.expand_dims(glow_bw, axis=2), 3, axis=2)
        arr[center[1]+y_min:center[1]+y_max, center[0]+x_min:center[0]+x_max] += glow_colored
    return arr



# Bounded PSF algorithm

# empirical constants
a = 0.123
k = 0.0016

def PSF_Bounded(theta: float, max_theta: float, br_center: float):
    """
    Human eye's point source function from the research by Greg Spencer et al., optimized to fit a square.
    Lower limit on brightness and angular size: 1 Vega and 0.05 degrees per pixel. No upper limits.
    """
    if theta == 0:
        return br_center
    elif theta < max_theta:
        brackets = max_theta / theta - 1
        return k * brackets * brackets
    else:
        return 0. # after max_theta function starts to grow again
PSF_Bounded = np.vectorize(PSF_Bounded)

def draw_Bounded(arr: np.ndarray, br0: float, color0: np.ndarray, center: tuple[int, int],
                    degree_per_px: float, corners: bool, max_br: float):
    """
    Adds a star to the numpy array using the "Bounded" photopic PSF from the research by Greg Spencer et al.,
    but ensures that the glow size does not exceed a pre-specified square.
    Please note: subpixel render will not work well, star is assumed to be in the center.
    - br0 is the brightness of the star
    - theta is the angle in degrees from the pixel center to the star center
    """
    color = auxiliary.green_normalization(color0)
    scaled_color = color * br0
    if np.all(scaled_color < 1):
        # Option 1: single pixel render
        arr[center[1], center[0]] += scaled_color
    else:
        # Option 2: glow square render
        hight, width, length = arr.shape
        br = np.arctan(br0 / max_br) * max_br # dimmed brightness
        max_theta = a * np.sqrt(br) # glow radius
        half_sq = floor(max_theta / degree_per_px - 0.5)
        # -1/2 because we have +1/2 from central pixel, and -2/2 from side pixels where PSF=0
        if corners:
            arr = auxiliary.draw_corners(arr, center, half_sq)
        x_min = -min(half_sq, center[0])
        x_max = min(half_sq+1, width-center[0])
        y_min = -min(half_sq, center[1])
        y_max = min(half_sq+1, hight-center[1])
        x = np.arange(x_min, x_max)
        y = np.arange(y_min, y_max)
        xx, yy = np.meshgrid(x, y)
        theta = np.sqrt(xx*xx + yy*yy) * degree_per_px # array of distances to the center
        glow_bw = PSF_Bounded(theta, max_theta, br) # in the [0, 1] range, like in Celestia
        glow_colored = color * np.repeat(np.expand_dims(glow_bw, axis=2), 3, axis=2) # scaling
        arr[center[1]+y_min:center[1]+y_max, center[0]+x_min:center[0]+x_max] += glow_colored
    return arr



# Full-screen PSF algorithm

def PSF_fullscreen(theta2: float, min_theta2: float):
    """
    Human eye's point source function, optimized to be a full-screen shader.
    The price to pay for simplification is a brightness reduction compared to the original PSF.
    """
    if theta2 < min_theta2:
        return 1 # overexposed
    else:
        return 4.43366571e-6 / theta2
