import cupy as cp
print("CUDA Runtime Version:", cp.cuda.runtime.getVersion())
print("Jumlah device:", cp.cuda.runtime.getDeviceCount())
