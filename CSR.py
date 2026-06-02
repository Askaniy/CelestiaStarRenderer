import numpy as np
import numpy.typing as npt
from functools import lru_cache
from math import floor, ceil
from PIL import Image



# === Rendering functions ===

def render_point(px_dist: npt.NDArray, point_radius: int | float):
    """ Simple linear brightness distribution. """
    return np.clip(1. - px_dist / point_radius, 0, None)

def render_eye_PSF(px_dist: npt.NDArray, br: float, max_theta: float, a: float, b: float):
    """ Approximation of the human eye's point source function by Greg Spencer et al. (1995) """
    arr = np.zeros_like(px_dist)
    render_mask = px_dist < max_theta
    arr[render_mask] = ((br**0.4 / px_dist[render_mask] - a) * b)**2.5
    return np.clip(arr, 0, br)

@lru_cache(maxsize=32)
def get_eye_PSF_params(optimization: float, point_radius: int | float):
    """ Returns parameters for the eye PSF based on the engine settings """
    # Inverted outer radius of the PSF at the moment of transition [1/px]
    a = optimization / point_radius
    # Bloom scale factor
    b = 1 / (np.pi / point_radius - a) # constant [px]
    # Why π? It was chosen based on experience; yields the best results. I don't know the rationale behind it.
    # It's the ratio of the point radius to the PSF overexposure radius at the moment of transition
    # As the starting point, it also affects the speed of bloom size growth
    return a, b

def original_PSF(theta: float | npt.NDArray):
    """ Unmodified photopic point source function from the research by Greg Spencer et al. (1995) """
    f0 = 2.61e6 * np.exp(-(50*theta)**2)
    f1 = 20.91 / (theta + 0.02)**3
    f2 = 72.37 / (theta + 0.02)**2
    return 0.384 * f0 + 0.478 * f1 + 0.138 * f2

def render_original_PSF(theta: float | npt.NDArray):
    """ Normalized original photopic PSF by Greg Spencer et al. (1995) """
    return original_PSF(theta) / original_PSF(0)



min_peak_radiances = (
    1 / 255, # linear mode
    1 / (255 * 12.92) # sRGB mode (with gamma correction at the end)
)



class RenderEngine:

    def __init__(self,
            width: int,
            height: int,
            channels: int = 3,
            point_radius: int | float = 2.0,
            optimization: int | float | None = 0.1,
            max_irradiance: int | float | None = None,
            color_saturation_limit: float = 0.1,
            gamma_correction: bool = True,
            is_cylindrical: bool = False
        ) -> None:
        self.W = width
        self.H = height
        self.C = channels
        self.point_radius = point_radius
        self.optimization = optimization
        self.max_irradiance = max_irradiance # variable, upper brightness limit
        self.color_saturation_limit = color_saturation_limit # the ratio of the minimum color component to the maximum
        self.gamma_correction = gamma_correction
        self.is_cylindrical = is_cylindrical
        # Creating the coordinate grid and the canvas template
        x_range = np.arange(self.W)
        y_range = np.arange(self.H)
        if self.is_cylindrical:
            assert self.W == self.H * 2
            self.rad_per_px = np.pi / self.H
            x_range = (x_range + 0.5) * self.rad_per_px
            y_range = 0.5 * np.pi - (y_range + 0.5) * self.rad_per_px
        self.xx, self.yy = np.meshgrid(x_range, y_range)
        self.canvas_template = np.zeros(shape=(self.H, self.W, self.C))

    def draw_source(self,
            coordinates: tuple[float, float],
            irradiance: float,
            color: npt.ArrayLike | None = None,
            canvas: npt.NDArray | None = None
        ):
        """
        Performs rendering of the source, adding it to the existing numpy array.
        For a cylindrical map, `source_coords` are longitude and latitude,
        while for a regular flat image these are X and Y coordinates in pixels.
        Using a pre-created canvas increases the rendering speed by several times.
        """

        if canvas is None:
            # Creating a black canvas if there's no one
            canvas = np.copy(self.canvas_template)
        elif canvas.shape != self.canvas_template.shape:
            # Checking the input
            raise ValueError(
                f'''Shape of the given canvas {canvas.shape} does not match
                the shape of the engine's canvas template {self.canvas_template.shape}'''
            )

        # Normalization of the source's color by the green value,
        # since the brightness is often given for the V filter
        color = green_normalization(color, self.color_saturation_limit)

        # Setting the coordinates
        if self.is_cylindrical:
            source_lon, source_lat = coordinates
            source_x = source_lon / self.rad_per_px - 0.5
            source_y = (0.5 * np.pi - source_lat) / self.rad_per_px - 0.5
            coords = (source_lon, source_lat)
            x_scale_factor = 1 / np.cos(source_lat)
        else:
            source_x = coordinates[0] - 0.5
            source_y = coordinates[1] - 0.5
            coords = (source_x, source_y)
            x_scale_factor = 1

        # Calculating the peak radiance
        irradiance = self.soft_clip(irradiance)
        peak_radiance = self.irradiance_to_peak_radiance(irradiance)
        min_peak_radiance = min_peak_radiances[bool(self.gamma_correction)]

        if self.optimization is None:

            # === Original PSF mode ===
            # For this mode, the radius of the point is effective:
            # use 0.03 to match appearance, or 0.035 to conserve flux
            deg_per_px = 0.03 / self.point_radius
            px_dist_arr = self.find_distances(coords, box=None)
            source_render = render_original_PSF(px_dist_arr * deg_per_px) * peak_radiance
            canvas += source_render[..., np.newaxis] * color

        else:

            # === Point mode ===
            if peak_radiance > min_peak_radiance:
                # Calculating right place(s) to render
                boxes = self.find_box_boundaries(
                    source_x, source_y,
                    r_x = self.point_radius * x_scale_factor,
                    r_y = self.point_radius
                )
                for box in boxes:
                    # Rendering
                    px_dist_arr = self.find_distances(coords, box)
                    source_render = render_point(px_dist_arr, self.point_radius) * min(peak_radiance, 1)
                    canvas[box] += source_render[..., np.newaxis] * color

            # === Eye PSF mode ===
            if peak_radiance > 1:
                # Calculating bloom radius
                a, b = get_eye_PSF_params(self.optimization, self.point_radius)
                if a != 0:
                    eye_PSF_radius = peak_radiance**0.4 / a
                else:
                    eye_PSF_radius = np.inf
                # Calculating right place(s) to render
                if eye_PSF_radius != np.inf:
                    boxes = self.find_box_boundaries(
                        source_x, source_y,
                        r_x = eye_PSF_radius * x_scale_factor,
                        r_y = eye_PSF_radius
                    )
                else:
                    boxes = ((slice(None, None), slice(None, None)),)
                for box in boxes:
                    # Rendering
                    px_dist_arr = self.find_distances(coords, box)
                    source_render = render_eye_PSF(px_dist_arr, peak_radiance, eye_PSF_radius, a, b)
                    canvas[box] += source_render[..., np.newaxis] * color

        return canvas

    def irradiance_to_peak_radiance(self, irradiance):
        """
        Converts total brightness of the light source (dimensionally W/m²)
        to brightness distributed across the pixels (dimensionally W/(m² sr)).
        """
        return irradiance * 3 / (np.pi * self.point_radius**2)

    def find_box_boundaries(self, x, y, r_x, r_y):
        """
        From coordinates of the source and radii in pixels
        calculates boundaries of the boxes on the canvas.
        If the canvas is a cylindrical map, there may be two
        places to render the source.
        """
        # Calculating the source boundaries
        x_min_0 = floor(x - r_x)
        x_max_0 = ceil(x + r_x) + 1
        y_min = floor(y - r_y)
        y_max = ceil(y + r_y) + 1
        # Processing edge sources
        is_on_edge = False
        is_polar = False
        # Processing of polar sources
        if y_min < 0:
            y_min = 0
            is_polar = True
        if y_max > self.H:
            y_max = self.H
            is_polar = True
        x_slice_1 = None
        if self.is_cylindrical:
            if is_polar:
                x_min_0 = 0
                x_max_0 = self.W
            else:
                # Virtual extension of the map0 to the right (map1)
                x_min_1 = x_max_1 = None
                if x_min_0 < 0:
                    x_min_0 += self.W
                    x_max_1 = x_max_0
                    is_on_edge = True
                if x_max_0 > self.W:
                    x_max_1 = x_max_0 - self.W
                    is_on_edge = True
                if is_on_edge:
                    x_max_0 = self.W
                    x_min_1 = 0
                    x_slice_1 = slice(x_min_1, x_max_1)
        else:
            x_min_0 = max(x_min_0, 0)
            x_max_0 = min(x_max_0, self.W)
        x_slice_0 = slice(x_min_0, x_max_0)
        y_slice = slice(y_min, y_max)
        boxes = [(y_slice, x_slice_0)]
        if x_slice_1 is not None:
            # Handling map cyclicity: the source is rendered twice
            boxes.append((y_slice, x_slice_1))
        return boxes

    def find_distances(self, coords, box: tuple[slice, slice] | None = None):
        """ Calculates array of distances to the center within the box. """
        x, y = coords
        if box is None:
            box = slice(None, None), slice(None, None)
        if self.is_cylindrical:
            # Spherical trigonometry:
            # θ = arccos(sin(φ1) * sin(φ2) + cos(φ1) * cos(φ2) * cos(Δλ))
            theta_arr = np.arccos(
                np.sin(y) * np.sin(self.yy[box]) +
                np.cos(y) * np.cos(self.yy[box]) * np.cos(self.xx[box] - x)
            )
            px_dist_arr = theta_arr / self.rad_per_px
        else:
            # Array of distances to the center
            px_dist_arr = np.sqrt((self.xx[box] - x)**2 + (self.yy[box] - y)**2)
        return px_dist_arr

    def soft_clip(self, irradiance: float):
        """ Prevents bloom from spreading indefinitely. """
        if self.max_irradiance is None:
            return irradiance
        else:
            return (1. - 1. / (irradiance / self.max_irradiance + 1.)) * self.max_irradiance



def green_normalization(color: npt.ArrayLike | None, color_saturation_limit: float = 0.1) -> int | npt.NDArray:
    """
    Normalizes the color by its green value and corrects extreme saturation.
    Brightness is often given for the V filter.
    """
    if color is None:
        return 1
    else:
        color_arr = np.array(color)
        color_arr /= color_arr.max()
        delta = color_saturation_limit - color_arr.min()
        if delta > 0:
            color_arr += delta * (1 - color_arr)**2 # desaturating to the saturation limit
        return color_arr / color_arr[1]

def gamma_correction(arr0: npt.NDArray) -> npt.NDArray:
    """ Applies gamma correction in sRGB implementation to the array """
    arr1 = np.copy(arr0)
    mask = arr0 < 0.0031308
    arr1[mask] *= 12.92
    arr1[~mask] = 1.055 * np.power(arr1[~mask], 1./2.4) - 0.055
    return arr1

def img2array(img: Image.Image):
    """
    Converting a Pillow image to a numpy array
    1.5-2.5 times faster than np.array() and np.asarray()
    Based on https://habr.com/ru/articles/545850/
    """
    img.load()
    e = Image._getencoder(img.mode, 'raw', img.mode)
    e.setimage(img.im, None)
    shape, typestr = Image._conv_type_shape(img)
    data = np.empty(shape, dtype=np.dtype(typestr))
    mem = data.data.cast('B', (data.data.nbytes,))
    bufsize, s, offset = 65536, 0, 0
    while not s:
        _, s, d = e.encode(bufsize)
        mem[offset:offset + len(d)] = d
        offset += len(d)
    if s < 0:
        raise RuntimeError(f'encoder error {s} in tobytes')
    return data
