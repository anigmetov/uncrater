import ctypes
import os
import numpy as np
from typing import Union, Tuple
from icecream import ic

lib_path = os.path.join(os.environ['CORELOOP_DIR'],'build','libcl_utils.so')
lib = ctypes.CDLL(lib_path)

lib.encode_10plus6.argtypes = [ctypes.c_int32]
lib.encode_10plus6.restype = ctypes.c_uint16

lib.decode_10plus6.argtypes = [ctypes.c_uint16]
lib.decode_10plus6.restype = ctypes.c_int32

lib.encode_4_into_5.argtypes = [ ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_uint16), ]
lib.encode_4_into_5.restype = None

lib.decode_5_into_4.argtypes = [ ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_int32), ]
lib.decode_5_into_4.restype = None

lib.fft_precompute_tables.argtypes = []
lib.fft_precompute_tables.restype = None

lib.fft_int.argtypes = [ ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ]
lib.fft_int.restype = None

lib.fft_int_in_place.argtypes = [ ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ]
lib.fft_int_in_place.restype = None

lib.fft_float.argtypes = [ ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32),
                           ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),]
lib.fft_float.restype = None


def encode_10plus6(x: Union[int, np.array]) -> Union[int, np.array]:
    if isinstance(x, int):
        return lib.encode_10plus6(x)
    else:
        assert(x.dtype == np.int32)
        return np.array([lib.encode_10plus6(y) for y in x], dtype=np.uint16)


def decode_10plus6(x: Union[int, np.array]) -> Union[int, np.array]:
    if isinstance(x, int):
        return lib.decode_10plus6(x)
    else:
        assert(x.dtype == np.uint16)
        return np.array([lib.decode_10plus6(y) for y in x], dtype=np.int32)


def decode_5_into_4_helper(compressed_data: np.ndarray):
    array_size = compressed_data.shape[0] - 1
    assert array_size == 4
    decompressed_array = np.zeros(array_size, dtype=np.int32)
    decompressed_array = np.ascontiguousarray(decompressed_array, dtype=np.int32)

    lib.decode_5_into_4(
        compressed_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),
        decompressed_array.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
    )

    return decompressed_array


def decode_5_into_4(compressed_data: np.ndarray) -> np.ndarray:
    assert compressed_data.size % 5 == 0, "Input array length must be a multiple of 5"
    num_chunks = compressed_data.size // 5
    decompressed_data = np.zeros(num_chunks * 4, dtype=np.int32)
    for i in range(num_chunks):
        chunk = compressed_data[i * 5:(i + 1) * 5]
        decompressed_data[i * 4:(i + 1) * 4] = decode_5_into_4_helper(chunk)
    return decompressed_data


def single_fft(in_real: np.ndarray, in_imag: np.ndarray, func_name = "fft_int_in_place") -> Tuple[np.ndarray, np.ndarray]:
    lib.fft_precompute_tables()
    assert in_real.size == in_imag.size == 64
    in_real_copy = np.ascontiguousarray(in_real.copy(), dtype=np.int32)
    in_imag_copy = np.ascontiguousarray(in_imag.copy(), dtype=np.int32)
    ic(in_real_copy)
    if func_name == "fft_int_in_place":
        ic(in_real_copy, in_real_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                             in_imag_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)))
        lib.fft_int_in_place(in_real_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                             in_imag_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)))
        return in_real_copy, in_imag_copy
    elif func_name == "fft_float":
        out_real = np.ascontiguousarray(np.zeros(64, dtype=np.float32), dtype=np.float32)
        out_imag = np.ascontiguousarray(np.zeros(64, dtype=np.float32), dtype=np.float32)
        lib.fft_float(in_real_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                             in_imag_copy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                             out_real.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                             out_imag.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                             )
        return out_real, out_imag
    else:
        raise RuntimeError("Unknown func_name")
