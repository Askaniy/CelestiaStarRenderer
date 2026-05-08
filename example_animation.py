import time
import numpy as np
from PIL import Image

from CSR import RenderEngine, gamma_correction


# === Timeline ===

n = 100 # number of frames
peak_br = np.logspace(-2, 4, n)
source_color = np.array([0.314, 0.561, 1.0]) # color of Vega without gamma correction

is_orbiting = True
radius = 12.5 # px
period = 10 # sec
duration = 1 * period # sec
fps = n / duration
dt_s = duration / n
dt_ms = 1000 * dt_s


# === Image canvas ===

W = 64
H = W
scale_factor = 10
engine = RenderEngine(W, H)


# === Rendering ===

start = time.time()

frames = []

for t in range(n):
    if is_orbiting:
        phase = - t * dt_s / period * 2 * np.pi
        source_coords = (W/2 + radius * np.cos(phase), H/2 + radius * np.sin(phase))
    else:
        source_coords = (W/2, H/2)
    frame = engine.draw_source(source_coords, peak_br[t], source_color)
    frames.append(frame)

end = time.time()
print(f'Processed {n} frames in {end - start:.3f} seconds')

# Post processing
arr = np.clip(frames, 0, 1)
arr = gamma_correction(arr)
arr = np.round(arr * 255).astype('uint8')
arr = np.repeat(np.repeat(arr, scale_factor, axis=1), scale_factor, axis=2)

# Export
file_name = 'examples/example_animation'
if is_orbiting:
    file_name += '_orbiting'
else:
    file_name += '_static'

# Saving to GIF
frames_to_save = [Image.fromarray(frame) for frame in arr]
frames_to_save[0].save(file_name+'.gif', save_all=True, append_images=frames_to_save[1:], duration=dt_ms, loop=0)
print(f'The animation is saved as "{file_name}.gif"')

# Saving to MP4
#import imageio
#imageio.mimsave(file_name+'.mp4', arr, fps=fps)
#print(f'The animation is saved as "{file_name}.mp4"')
