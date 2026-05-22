# Celestia Star Renderer

Realistic star rendering method developed for the [Celestia Project](https://github.com/CelestiaProject) to assist with the transition to gamma corrected (sRGB) rendering. It relies on the photopic point source function (PSF) by [Spencer et al. 1995](https://dl.acm.org/doi/10.1145/218380.218466). In its original form, it could be used for convolution at each frame, which is slow, or it could be cropped, which would result in jagged edges. An approximating function has been found that does not alter the appearance, but is simple and spatially bounded. 

The function type is specialized depending on the brightness:
1. *Point mode*: a circular linear distribution with a diameter of several pixels.
2. *Eye PSF mode*: an approximation of the actual PSF with pre-calculated exact size.

A reference implementation in Python is provided here. The interface is accessible via the class `RenderEngine`, which is located in [`CSR.py`](CSR.py). Draw a light source on a NumPy array using the `draw_source()` method. Check out the comments in the code for details. On other programming languages, the method can be implemented in two separate shaders.

The main input of `draw_source()` is irradiance (dimensionally W/m²), a brightness of the light source. The output is radiance (dimensionally W/(m² sr)), brightness distributed across the pixels. Gamma correction should be applied at the end.


## Examples

### [Animation](example_animation.py)

Vega's color is used as an example. The values were calculated from the spectrum using [TrueColorTools](https://github.com/Askaniy).

The radiance increases logarithmically.

<img src="examples/example_animation_orbiting.gif" width="256" />


### [Chart](example_chart.py)

The model depends on two parameters: "optimization" and the radius of the point mode. With zero optimization, the model, like the original PSF, is not size-constrained.

The transition peak radiance of 1 is represented by 0 magnitude.

<img src="examples/example_chart.png" width="512" />


### [Cylindrical map](example_cylindrical_map.py)

10,000 random light sources render in less than a second on any device (except for potatoes).

<img src="examples/example_cylindrical_map.png" width="1024" />


## Installation

Python version 3.11 or higher is required. Works on Windows/macOS/Linux.

1. Clone the repository or download the archive using the GitHub web interface;
2. Open the console in the project root folder;
3. Create a virtual environment with `python3 -m venv .venv`;
4. Install the dependencies with `.venv/bin/pip install -r requirements.txt`;
5. Execute an example script with `.venv/bin/python example_animation.py`.


## Magnitudes to irradiances

If you have apparent magnitude, $\text{irradiance} = 10^{-0.4 \, \text{magnitude}}$ in the "Vega normalized" system. Multiply it by $3.712 \cdot 10^{-11}$ W/m² to get SI units. The coefficient was obtained using the [CALSPEC](https://www.stsci.edu/hst/instrumentation/reference-data-for-calibration-and-tools/astronomical-catalogs/calspec) spectrum of Vega convolved with the [Generic/Bessel.V](https://svo2.cab.inta-csic.es/svo/theory/fps3/index.php?id=Generic/Bessell.V&&mode=browse&gname=Generic&gname2=Bessell#filter) filter in [AstroColor](https://github.com/Askaniy/AstroColor) and its apparent magnitude of [0.026 mag](https://iopscience.iop.org/article/10.1086/420715).


## History

In Celestia, as in many other programs, the rendering of stars was implemented approximately, without checks for physical accuracy. Recently implemented gamma correction enhances the effect, making the star field appear flat.
The problem was already noticed and described by Chris Layrel, 2010 forum discussion is [here](https://celestiaproject.space/forum/viewtopic.php?f=10&t=16031) and led to [this branch](https://github.com/CelestiaProject/Celestia/tree/new-stars-v2). But it was "buggy and slow", with squares around bright stars.
To address these issues, I [proposed](https://github.com/CelestiaProject/Celestia/issues/1948) the initial approaches in 2023-2024 (see [`legacy_algorithms.py`](legacy_algorithms.py)). The repository and the method were redesigned in 2026.

Not vibe coded!
