import numpy as np
import numpy.typing as npt
from math import floor, ceil
from PIL import Image


class RenderEngine:

    def __init__(self,
            width: int,
            height: int,
            channels: int = 3,
            optimization: int | float = 0.1,
            max_peak_radiance: int | float = 10_000,
            point_radius_px: int | float = 1.5,
            is_cylindrical: bool = False
        ) -> None:
        self.W = width
        self.H = height
        x_range = np.arange(self.W)
        y_range = np.arange(self.H)
        if is_cylindrical:
            assert self.W == self.H * 2
            self.rad_per_px = np.pi / self.H
            x_range = (x_range + 0.5) * self.rad_per_px
            y_range = 0.5 * np.pi - (y_range + 0.5) * self.rad_per_px
        self.xx, self.yy = np.meshgrid(x_range, y_range)
        self.canvas_template = np.zeros(shape=(self.H, self.W, channels))
        self.is_cylindrical = is_cylindrical
        self.color_saturation_limit = color_saturation_limit # The ratio of the minimum color component to the maximum
        # Point mode parameters
        self.point_radius_px = point_radius_px # 1.5 -> box size = 3x3 px
        self.inv_max_offset = 1 / (point_radius_px * np.sqrt(2.)) # [1/px]
        # Eye PSF mode parameters
        k = 3 # ratio of the point radius to the PSF overexposure radius at the moment of transition
        # as the starting point, it also affects the speed of bloom size growth
        self.a = optimization / point_radius_px # inverted PSF outer radius at the moment of transition [1/px]
        self.b = 1 / (k / point_radius_px - self.a) # constant [px]
        self.max_peak_radiance = max_peak_radiance # variable, upper brightness limit
        self.min_peak_radiance = 1 / (255 * 12.92) # from gamma correction implementation of sRGB color space

    def render_point(self, px_dist: npt.NDArray):
        """ Simple linear brightness distribution. """
        return np.clip(1. - px_dist * self.inv_max_offset, 0, None)

    def render_eye_PSF(self, px_dist: npt.NDArray, br: float, max_theta: float):
        """ Approximation of the human eye's point source function by Greg Spencer et al. (1995) """
        arr = np.zeros_like(px_dist)
        render_mask = px_dist < max_theta
        arr[render_mask] = ((br**0.4 / px_dist[render_mask] - self.a) * self.b)**2.5
        return np.clip(arr, 0, br)

    def draw_source(self,
            coordinates: tuple[float, float],
            peak_radiance: float,
            color: npt.ArrayLike,
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
        else:
            # Checking the input
            assert canvas.shape == self.canvas_template.shape

        # Normalization of the source's color by the green value,
        # since the brightness is often given for the V filter
        color = green_normalization(color)

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

        # === Point mode ===
        if peak_radiance > self.min_peak_radiance:
            # Calculating right place(s) to render
            boxes = self.find_box_boundaries(
                source_x, source_y,
                r_x = self.point_radius_px * x_scale_factor,
                r_y = self.point_radius_px
            )
            for box in boxes:
                # Rendering
                px_dist_arr = self.find_distances(coords, box)
                source_render = self.render_point(px_dist_arr) * min(peak_radiance, 1)
                canvas[box] += source_render[..., np.newaxis] * color

        # === Eye PSF mode ===
        if peak_radiance > 1:
            # Preventing large size of the bloom
            # (optional, is regulated by `max_peak_radiance`)
            peak_radiance = self.brightness_rescaler(peak_radiance)
            # Calculating bloom radius
            if self.a != 0:
                eye_PSF_radius = peak_radiance**0.4 / self.a
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
                source_render = self.render_eye_PSF(px_dist_arr, peak_radiance, eye_PSF_radius)
                canvas[box] += source_render[..., np.newaxis] * color

        return canvas

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

    def find_distances(self, coords, box):
        """ Calculates array of distances to the center within the box. """
        x, y = coords
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

    def brightness_rescaler(self, br: float):
        """ Prevents bloom from spreading indefinitely. """
        return (1. - 1. / (br / self.max_peak_radiance + 1.)) * self.max_peak_radiance



class OriginalPSF:

    def __init__(self,
            width: int,
            height: int,
            channels: int = 3,
            deg_per_px: float = 0.05,
            is_cylindrical: bool = False
        ) -> None:
        self.W = width
        self.H = height
        x_range = np.arange(self.W)
        y_range = np.arange(self.H)
        if is_cylindrical:
            assert self.W == self.H * 2
            self.rad_per_px = np.pi / self.H
            x_range = (x_range + 0.5) * self.rad_per_px
            y_range = 0.5 * np.pi - (y_range + 0.5) * self.rad_per_px
        self.xx, self.yy = np.meshgrid(x_range, y_range)
        self.canvas_template = np.zeros(shape=(self.H, self.W, channels))
        self.deg_per_px = deg_per_px
        self.is_cylindrical = is_cylindrical

    def draw_source(self,
            coordinates: tuple[float, float],
            peak_radiance: float,
            color: npt.ArrayLike,
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
        else:
            # Checking the input
            assert canvas.shape == self.canvas_template.shape
        # Normalization of the source's color by the green value,
        # since the brightness is often given for the V filter
        color = green_normalization(color)
        # Setting the coordinates
        if self.is_cylindrical:
            source_lon, source_lat = coordinates
            source_x = source_lon / self.rad_per_px - 0.5
            source_y = (0.5 * np.pi - source_lat) / self.rad_per_px - 0.5
            # Spherical trigonometry:
            # θ = arccos(sin(φ1) * sin(φ2) + cos(φ1) * cos(φ2) * cos(Δλ))
            theta_arr = np.arccos(
                np.sin(source_lat) * np.sin(self.yy) +
                np.cos(source_lat) * np.cos(self.yy) * np.cos(self.xx - source_lon)
            )
            px_dist_arr = theta_arr / self.rad_per_px
        else:
            source_x = coordinates[0] - 0.5
            source_y = coordinates[1] - 0.5
            # Array of distances to the center
            px_dist_arr = np.sqrt((self.xx - source_x)**2 + (self.yy - source_y)**2)
        # Rendering
        source_render = self.normalized_PSF(px_dist_arr * self.deg_per_px) * peak_radiance
        canvas += source_render[..., np.newaxis] * color
        return canvas

    def original_PSF(self, theta: float | npt.NDArray):
        """ Unmodified photopic point source function from the research by Greg Spencer et al. (1995) """
        f0 = 2.61e6 * np.exp(-(50*theta)**2)
        f1 = 20.91 / (theta + 0.02)**3
        f2 = 72.37 / (theta + 0.02)**2
        return 0.384 * f0 + 0.478 * f1 + 0.138 * f2

    def normalized_PSF(self, theta: float | npt.NDArray):
        return self.original_PSF(theta) / self.original_PSF(0)


color_saturation_limit = 0.1

def green_normalization(color: npt.ArrayLike) -> npt.NDArray:
    """
    Normalizes the color by its green value and corrects extreme saturation.
    Brightness is often given for the V filter.
    """
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
    e.setimage(img.im)
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
