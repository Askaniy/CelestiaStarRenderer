import time
import numpy as np
import pandas as pd
from PIL import Image

from CSR import RenderEngine, gamma_correction


# === Data generation ===

n = 10000 # number of light sources

np.random.seed(42)
df = pd.DataFrame({
    'RA': np.random.uniform(0, 2*np.pi, n),
    'Dec': np.arcsin(np.random.uniform(-1, 1, n)),
    'V': np.random.pareto(1, n) / 100,
    'R': np.random.uniform(0, 1, n),
    'G': np.random.uniform(0, 1, n),
    'B': np.random.uniform(0, 1, n)
})

# Coordinates and color of light sources
source_lon = 2*np.pi - df['RA'].to_numpy() # inverse RA direction
source_lat = df['Dec'].to_numpy()
source_colors = df[['R','G','B']].to_numpy()  # (N,3)
source_radiances = df['V'].to_numpy()


# === Cylindrical map canvas ===

W = 2048
H = round(W / 2)
channels = 3
arr = np.zeros(shape=(H, W, channels))
engine = RenderEngine(W, H, channels, is_cylindrical=True)


# === Rendering ===

start = time.time()

for i in range(len(df)):
    source_coords = (source_lon[i], source_lat[i])
    source_color = source_colors[i]
    source_radiance = source_radiances[i]
    arr = engine.draw_source(source_coords, source_radiance, source_color, canvas=arr)

end = time.time()
print(f'Processed {n} light sources in {end - start:.3f} seconds')


# Post processing
arr = np.clip(arr, 0, 1)
arr = gamma_correction(arr)
img = Image.fromarray(np.round(arr * 255).astype('uint8'))

# Export
file_name = 'examples/example_cylindrical_map.png'
img.save(file_name)

print(f'The map is saved as "{file_name}"')
