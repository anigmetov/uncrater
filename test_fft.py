#!/bin/env python3

import numpy as np
import numpy.fft
from matplotlib import pyplot as plt
import os
import os.path

from icecream import ic

build_path = os.path.join(os.environ['CORELOOP_DIR'],'build')
current_dir = os.getcwd()
os.chdir(build_path)
os.system('make -j')
os.chdir(current_dir)

import uncrater.c_utils as cl_fft

C = 1_000_000
n = 64

xs = np.linspace(0, 2 * np.pi, n, endpoint=False)

# re_ys = C *(np.sin(xs))
# im_ys = np.zeros(n, dtype=np.int32)
re_ys = C *(np.sin(xs) + np.cos(4 * xs) + 8 * np.cos(19 * xs) - 4 *np.sin(25 * xs))
im_ys = C *(-2 * np.sin(xs) + 3 * np.cos(2 * xs) + 2 * np.cos(9 * xs) - 7 *np.sin(5 * xs))
# im_ys = np.zeros(n, dtype=np.int32)

re_ys_int = re_ys.astype(np.int32)
im_ys_int = im_ys.astype(np.int32)

re_ys_double = re_ys.astype(np.float64)
im_ys_double = im_ys.astype(np.float64)
comp_ys = np.vectorize(complex)(re_ys_double, im_ys_double)
ic(comp_ys)
true_fft = np.fft.fft(np.vectorize(complex)(re_ys_double, im_ys_double))
true_fft = np.fft.fft(comp_ys)
ic(true_fft)
true_fft_re, true_fft_im = np.real(true_fft), np.imag(true_fft)
ic(true_fft_re, np.min(true_fft_re), np.max(true_fft_re))
ic(true_fft_im, np.min(true_fft_im), np.max(true_fft_im))

func_name = "fft_float"

# cl_fft_re_in_place, cl_fft_im_in_place = cl_fft.single_fft(re_ys_int, im_ys_int, func_name="fft_int_in_place")
cl_fft_re_in_place, cl_fft_im_in_place = cl_fft.single_fft(re_ys_int, im_ys_int, func_name=func_name)

fig, (ax_f, re_cl_fft_ax, re_true_fft_ax,  im_cl_fft_ax, im_true_fft_ax) = plt.subplots(1, 5)
fig.set_size_inches(5 * 12, 12)

ax_f.plot(xs, re_ys, "b", label="Re f")
ax_f.plot(xs, im_ys, "r", label="Im f")

re_cl_fft_ax.plot(xs, cl_fft_re_in_place, "r^", label="f1", alpha=0.5)
re_cl_fft_ax.legend()
re_cl_fft_ax.set_title(f"Ours: {func_name} Re")

im_cl_fft_ax.plot(xs, cl_fft_im_in_place, "r^", label="f1", alpha=0.5)
im_cl_fft_ax.legend()
im_cl_fft_ax.set_title(f"Ours: {func_name} Im")

re_true_fft_ax.plot(xs, true_fft_re, "bs", label="f1", alpha=0.5)
re_true_fft_ax.legend()
re_true_fft_ax.set_title("True Re")

im_true_fft_ax.plot(xs, true_fft_im, "bs", label="f1", alpha=0.5)
im_true_fft_ax.legend()
im_true_fft_ax.set_title("True Im")

fig.tight_layout()

plt.savefig("fft.pdf")
