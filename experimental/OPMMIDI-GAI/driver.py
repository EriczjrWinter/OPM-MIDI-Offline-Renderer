# driver.py
from __future__ import annotations
import math
from pcm_core import PcmCore
from dataclasses import dataclass
from core import ChipCore
from voice import OpmVoice

# 文件行顺序 M1,C1,M2,C2 → 物理 slot 0,2,1,3
VOPM_OP_REG = [0, 2, 1, 3]

RHY_MAP = {
    35: 'BD', 36: 'BD',          # 底鼓
    38: 'SD', 40: 'SD', 39: 'SD',# 军鼓 / 拍手
    37: 'RIM',                   # 边击
    41: 'TOM', 43: 'TOM', 45: 'TOM', 47: 'TOM', 48: 'TOM', 50: 'TOM', # 各种桶鼓
    42: 'HH', 44: 'HH', 46: 'HH',# 闭镲 / 开镲
    49: 'TOP', 51: 'TOP', 52: 'TOP', 55: 'TOP', 57: 'TOP', 59: 'TOP', # 吊镲 / 叮叮镲
    # 如果有需要，可以继续加其他的，比如 56 (Cowbell) 映射到 RIM 之类的
}

DRUM_BANK = {
    # Note 35:
    35: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 17, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 17, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 17, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 17, 'sl': 0, 'rr': 8},
        ]
    },
    # Note 36:
    36: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 37:
    37: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 0, 'mul': 2, 'tl': 4, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
        ]
    },
    # Note 38:
    38: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 24, 'sr': 17, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 24, 'sr': 17, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 24, 'sr': 17, 'sl': 0, 'rr': 8},
        ]
    },
    # Note 39:
    39: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 1, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 2, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 3, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
        ]
    },
    # Note 40:
    40: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 19, 'sl': 0, 'rr': 9},
        ]
    },
    # Note 41:
    41: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 42:
    42: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 2, 'tl': 14, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
        ]
    },
    # Note 43:
    43: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 44:
    44: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 2, 'tl': 14, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
        ]
    },
    # Note 45:
    45: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 46:
    46: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 2, 'tl': 14, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 13, 'sl': 0, 'rr': 6},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
        ]
    },
    # Note 47:
    47: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 48:
    48: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 49: Crash (Animatics)
    49: {
        'alg': 0, 'fb': 2,
        'operators': [
            {'dt': 7, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 11, 'sr': 0, 'sl': 4, 'rr': 0},
            {'dt': 1, 'mul': 3, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 11, 'sr': 0, 'sl': 15, 'rr': 6},
            {'dt': 7, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 22, 'sr': 7, 'sl': 3, 'rr': 4},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 2, 'ar': 31, 'dr': 27, 'sr': 7, 'sl': 10, 'rr': 6},
        ]
    },
    # Note 50:
    50: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 15, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 51: RideCymbell1
    51: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 12, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 13, 'sr': 0, 'sl': 1, 'rr': 0},
            {'dt': 0, 'mul': 3, 'tl': 12, 'ks': 0, 'ar': 24, 'dr': 21, 'sr': 7, 'sl': 4, 'rr': 4},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 52: Chinese Crash (Animatics)
    52: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 7, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 7, 'sr': 0, 'sl': 5, 'rr': 2},
            {'dt': 1, 'mul': 3, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 12, 'sr': 4, 'sl': 8, 'rr': 4},
            {'dt': 7, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 21, 'sr': 6, 'sl': 3, 'rr': 3},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 2, 'ar': 31, 'dr': 25, 'sr': 6, 'sl': 10, 'rr': 3},
        ]
    },
    # Note 53: Ride Bell
    53: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 13, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 7, 'sr': 7, 'sl': 14, 'rr': 1},
            {'dt': 0, 'mul': 13, 'tl': 17, 'ks': 0, 'ar': 31, 'dr': 10, 'sr': 18, 'sl': 14, 'rr': 5},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 54:
    54: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 2, 'tl': 14, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 16, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 15},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 31, 'sl': 0, 'rr': 7},
        ]
    },
    # Note 55: Splash Crash (Animatics)
    55: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 7, 'mul': 15, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 5, 'sr': 6, 'sl': 5, 'rr': 0},
            {'dt': 1, 'mul': 3, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 11, 'sr': 4, 'sl': 8, 'rr': 5},
            {'dt': 7, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 21, 'sr': 6, 'sl': 3, 'rr': 3},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 2, 'ar': 31, 'dr': 26, 'sr': 6, 'sl': 10, 'rr': 5},
        ]
    },
    # Note 56:
    56: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 26, 'ks': 0, 'ar': 31, 'dr': 19, 'sr': 19, 'sl': 0, 'rr': 11},
            {'dt': 0, 'mul': 2, 'tl': 4, 'ks': 0, 'ar': 31, 'dr': 12, 'sr': 16, 'sl': 0, 'rr': 8},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 31, 'sr': 24, 'sl': 0, 'rr': 3},
            {'dt': 0, 'mul': 1, 'tl': 127, 'ks': 0, 'ar': 31, 'dr': 20, 'sr': 12, 'sl': 4, 'rr': 15},
        ]
    },
    # Note 57:
    57: {
        'alg': 0, 'fb': 6,
        'operators': [
            {'dt': 0, 'mul': 8, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 20, 'sr': 11, 'sl': 1, 'rr': 5},
            {'dt': 0, 'mul': 3, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 20, 'sr': 11, 'sl': 2, 'rr': 5},
            {'dt': 0, 'mul': 5, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 20, 'sr': 11, 'sl': 3, 'rr': 5},
        ]
    },
    # Note 58: VibeSlap
    58: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 0, 'tl': 8, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 10, 'sr': 0, 'sl': 15, 'rr': 5},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 5, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 21, 'ks': 0, 'ar': 31, 'dr': 10, 'sr': 0, 'sl': 15, 'rr': 5},
        ]
    },
    # Note 59: RideCymbell2
    59: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 12, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 12, 'sr': 0, 'sl': 1, 'rr': 0},
            {'dt': 0, 'mul': 3, 'tl': 11, 'ks': 0, 'ar': 24, 'dr': 20, 'sr': 8, 'sl': 4, 'rr': 4},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 60: HiBo
    60: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 5, 'ks': 2, 'ar': 28, 'dr': 15, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 2, 'ar': 28, 'dr': 20, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 7, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 23, 'dr': 18, 'sr': 10, 'sl': 15, 'rr': 9},
            {'dt': 3, 'mul': 3, 'tl': 4, 'ks': 0, 'ar': 18, 'dr': 18, 'sr': 10, 'sl': 15, 'rr': 9},
        ]
    },
    # Note 61: LoBo
    61: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 5, 'ks': 2, 'ar': 28, 'dr': 15, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 2, 'ar': 28, 'dr': 20, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 7, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 23, 'dr': 18, 'sr': 10, 'sl': 15, 'rr': 9},
            {'dt': 3, 'mul': 3, 'tl': 4, 'ks': 0, 'ar': 18, 'dr': 18, 'sr': 10, 'sl': 15, 'rr': 9},
        ]
    },
    # Note 62: MuHiCo
    62: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 7, 'ks': 2, 'ar': 31, 'dr': 15, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 0, 'mul': 1, 'tl': 0, 'ks': 2, 'ar': 31, 'dr': 18, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 7, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 30, 'dr': 18, 'sr': 10, 'sl': 15, 'rr': 9},
            {'dt': 1, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 18, 'dr': 22, 'sr': 10, 'sl': 15, 'rr': 10},
        ]
    },
    # Note 63: OpHiCo
    63: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 5, 'ks': 2, 'ar': 28, 'dr': 15, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 2, 'ar': 28, 'dr': 23, 'sr': 0, 'sl': 15, 'rr': 10},
            {'dt': 7, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 23, 'dr': 20, 'sr': 12, 'sl': 15, 'rr': 11},
            {'dt': 1, 'mul': 1, 'tl': 0, 'ks': 0, 'ar': 18, 'dr': 16, 'sr': 12, 'sl': 15, 'rr': 8},
        ]
    },
    # Note 64: LowCo
    64: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 5, 'ks': 2, 'ar': 28, 'dr': 15, 'sr': 0, 'sl': 15, 'rr': 9},
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 2, 'ar': 28, 'dr': 22, 'sr': 0, 'sl': 15, 'rr': 10},
            {'dt': 7, 'mul': 2, 'tl': 13, 'ks': 0, 'ar': 23, 'dr': 20, 'sr': 10, 'sl': 15, 'rr': 9},
            {'dt': 3, 'mul': 1, 'tl': 6, 'ks': 0, 'ar': 18, 'dr': 15, 'sr': 10, 'sl': 15, 'rr': 8},
        ]
    },
    # Note 65: immons
    65: {
        'alg': 5, 'fb': 0,
        'operators': [
            {'dt': 1, 'mul': 3, 'tl': 8, 'ks': 2, 'ar': 31, 'dr': 25, 'sr': 8, 'sl': 12, 'rr': 10},
            {'dt': 3, 'mul': 6, 'tl': 5, 'ks': 1, 'ar': 31, 'dr': 25, 'sr': 6, 'sl': 10, 'rr': 12},
            {'dt': 0, 'mul': 0, 'tl': 13, 'ks': 1, 'ar': 31, 'dr': 19, 'sr': 5, 'sl': 11, 'rr': 12},
            {'dt': 0, 'mul': 2, 'tl': 6, 'ks': 1, 'ar': 31, 'dr': 15, 'sr': 17, 'sl': 8, 'rr': 12},
        ]
    },
    # Note 66: immons
    66: {
        'alg': 5, 'fb': 0,
        'operators': [
            {'dt': 1, 'mul': 3, 'tl': 8, 'ks': 2, 'ar': 31, 'dr': 25, 'sr': 8, 'sl': 12, 'rr': 10},
            {'dt': 3, 'mul': 6, 'tl': 5, 'ks': 1, 'ar': 31, 'dr': 25, 'sr': 6, 'sl': 10, 'rr': 12},
            {'dt': 0, 'mul': 0, 'tl': 13, 'ks': 1, 'ar': 31, 'dr': 19, 'sr': 5, 'sl': 11, 'rr': 12},
            {'dt': 0, 'mul': 2, 'tl': 6, 'ks': 1, 'ar': 31, 'dr': 15, 'sr': 17, 'sl': 8, 'rr': 12},
        ]
    },
    # Note 67: HiAgogo
    67: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 3, 'mul': 14, 'tl': 23, 'ks': 2, 'ar': 31, 'dr': 9, 'sr': 9, 'sl': 8, 'rr': 6},
            {'dt': 3, 'mul': 4, 'tl': 0, 'ks': 1, 'ar': 20, 'dr': 16, 'sr': 17, 'sl': 10, 'rr': 8},
            {'dt': 0, 'mul': 14, 'tl': 24, 'ks': 2, 'ar': 31, 'dr': 9, 'sr': 9, 'sl': 8, 'rr': 6},
            {'dt': 0, 'mul': 4, 'tl': 0, 'ks': 1, 'ar': 20, 'dr': 16, 'sr': 17, 'sl': 10, 'rr': 8},
        ]
    },
    # Note 68: LoAgogo
    68: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 3, 'mul': 14, 'tl': 26, 'ks': 2, 'ar': 31, 'dr': 9, 'sr': 9, 'sl': 8, 'rr': 6},
            {'dt': 3, 'mul': 4, 'tl': 0, 'ks': 1, 'ar': 23, 'dr': 16, 'sr': 17, 'sl': 10, 'rr': 8},
            {'dt': 0, 'mul': 14, 'tl': 24, 'ks': 2, 'ar': 31, 'dr': 9, 'sr': 9, 'sl': 8, 'rr': 6},
            {'dt': 0, 'mul': 4, 'tl': 0, 'ks': 0, 'ar': 21, 'dr': 16, 'sr': 17, 'sl': 10, 'rr': 8},
        ]
    },
    # Note 69: Cabasa
    69: {
        'alg': 5, 'fb': 6,
        'operators': [
            {'dt': 2, 'mul': 15, 'tl': 6, 'ks': 1, 'ar': 31, 'dr': 5, 'sr': 2, 'sl': 8, 'rr': 1},
            {'dt': 0, 'mul': 15, 'tl': 1, 'ks': 2, 'ar': 31, 'dr': 5, 'sr': 2, 'sl': 5, 'rr': 3},
            {'dt': 7, 'mul': 13, 'tl': 2, 'ks': 2, 'ar': 25, 'dr': 5, 'sr': 2, 'sl': 7, 'rr': 1},
            {'dt': 3, 'mul': 3, 'tl': 0, 'ks': 2, 'ar': 13, 'dr': 17, 'sr': 11, 'sl': 10, 'rr': 9},
        ]
    },
    # Note 70: Maracas
    70: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 15, 'tl': 0, 'ks': 1, 'ar': 24, 'dr': 14, 'sr': 24, 'sl': 4, 'rr': 9},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 2, 'ar': 14, 'dr': 22, 'sr': 25, 'sl': 8, 'rr': 13},
            {'dt': 0, 'mul': 15, 'tl': 0, 'ks': 3, 'ar': 24, 'dr': 16, 'sr': 18, 'sl': 4, 'rr': 9},
            {'dt': 0, 'mul': 15, 'tl': 31, 'ks': 0, 'ar': 18, 'dr': 18, 'sr': 18, 'sl': 6, 'rr': 9},
        ]
    },
    # Note 71: ShortWhistle
    71: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 0, 'tl': 37, 'ks': 0, 'ar': 18, 'dr': 10, 'sr': 0, 'sl': 0, 'rr': 11},
            {'dt': 0, 'mul': 14, 'tl': 0, 'ks': 0, 'ar': 18, 'dr': 11, 'sr': 22, 'sl': 2, 'rr': 11},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 15, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 15, 'rr': 0},
        ]
    },
    # Note 72: LongWhistle
    72: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 0, 'tl': 37, 'ks': 0, 'ar': 18, 'dr': 10, 'sr': 0, 'sl': 0, 'rr': 11},
            {'dt': 0, 'mul': 14, 'tl': 0, 'ks': 0, 'ar': 18, 'dr': 8, 'sr': 22, 'sl': 2, 'rr': 11},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 15, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 15, 'rr': 0},
        ]
    },
    # Note 73: Short Guiro
    73: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 11, 'sr': 10, 'sl': 0, 'rr': 6},
            {'dt': 0, 'mul': 0, 'tl': 2, 'ks': 0, 'ar': 15, 'dr': 14, 'sr': 16, 'sl': 1, 'rr': 8},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 74: Long Guiro
    74: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 0, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 9, 'sr': 9, 'sl': 0, 'rr': 6},
            {'dt': 0, 'mul': 0, 'tl': 7, 'ks': 0, 'ar': 12, 'dr': 14, 'sr': 16, 'sl': 1, 'rr': 8},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 75:
    75: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 5, 'tl': 22, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 5, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
        ]
    },
    # Note 76:
    76: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 5, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 5, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
        ]
    },
    # Note 77:
    77: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 5, 'tl': 24, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 5, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
            {'dt': 0, 'mul': 7, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 21, 'sl': 0, 'rr': 10},
        ]
    },
    # Note 78: Mute Cuika
    78: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 7, 'mul': 2, 'tl': 39, 'ks': 0, 'ar': 12, 'dr': 15, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 7, 'mul': 8, 'tl': 0, 'ks': 1, 'ar': 14, 'dr': 6, 'sr': 17, 'sl': 0, 'rr': 6},
            {'dt': 0, 'mul': 1, 'tl': 27, 'ks': 0, 'ar': 12, 'dr': 15, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 8, 'tl': 0, 'ks': 2, 'ar': 14, 'dr': 6, 'sr': 17, 'sl': 0, 'rr': 6},
        ]
    },
    # Note 79: Open Cuika
    79: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 1, 'tl': 38, 'ks': 0, 'ar': 12, 'dr': 15, 'sr': 15, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 4, 'tl': 0, 'ks': 0, 'ar': 14, 'dr': 6, 'sr': 17, 'sl': 0, 'rr': 6},
            {'dt': 0, 'mul': 1, 'tl': 30, 'ks': 0, 'ar': 12, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 7},
            {'dt': 0, 'mul': 1, 'tl': 23, 'ks': 0, 'ar': 14, 'dr': 15, 'sr': 14, 'sl': 11, 'rr': 6},
        ]
    },
    # Note 80: MuteTriangle
    80: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 26, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 8, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 15, 'sr': 13, 'sl': 8, 'rr': 11},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
    # Note 81: OpenTriangle
    81: {
        'alg': 0, 'fb': 0,
        'operators': [
            {'dt': 0, 'mul': 3, 'tl': 26, 'ks': 0, 'ar': 31, 'dr': 0, 'sr': 0, 'sl': 8, 'rr': 0},
            {'dt': 0, 'mul': 2, 'tl': 0, 'ks': 0, 'ar': 31, 'dr': 8, 'sr': 8, 'sl': 8, 'rr': 5},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
            {'dt': 0, 'mul': 0, 'tl': 127, 'ks': 0, 'ar': 0, 'dr': 0, 'sr': 0, 'sl': 0, 'rr': 0},
        ]
    },
}

# 正确的 OPM 硬件音阶表
KTBL = [1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 15]

# 修正后的载波表（对应 ops 顺序 M1, C1, M2, C2）
CARRIER_MASK = {
    0: (0, 0, 0, 1),   # C2
    1: (0, 0, 0, 1),   # C2
    2: (0, 0, 0, 1),   # C2
    3: (0, 0, 1, 1),   # M2, C2
    4: (0, 1, 0, 1),   # C1, C2
    5: (0, 1, 1, 1),   # C1, M2, C2
    6: (0, 1, 1, 1),   # C1, M2, C2
    7: (1, 1, 1, 1),   # 全载波
}

TL_DB_PER_STEP = 0.75

# 硬编码的 FM 硬件鼓音色 (GM 映射)
# 格式: (KC, FL_CON, MUL_DT1, TL, AR_KS, DR, SR_DT2, SL_RR, 是否开启噪声, 噪声频率)
FM_DRUMS = {
    # 35/36 底鼓 (Kick): 不需要噪声，纯 M1 低频发威
    # M1_TL=0 (最响), C2_TL=127 (静音), FL_CON=0x3F (算法7,反馈满), M1_MUL=0 (0.5倍频产生极低频)
    35: (0x00, 0x7F, 0x3F, 0x00, 0x1F, 0x14, 0x00, 0x0F, False, 0),
    36: (0x00, 0x7F, 0x3F, 0x00, 0x1F, 0x14, 0x00, 0x0F, False, 0),

    # 38/40 军鼓 (Snare): M1 提供军鼓的“腔体震动”，C2 提供响弦的“沙沙声”
    # M1_TL=8, C2_TL=12 (两者混合), M1_MUL=5 (增加音调金属感), C2 开启噪声
    38: (0x08, 0x0C, 0x07, 0x05, 0x1F, 0x14, 0x10, 0x1F, True, 0x18),
    40: (0x08, 0x0C, 0x07, 0x05, 0x1F, 0x14, 0x10, 0x1F, True, 0x18),

    # 42/46 踩镲 (Hi-Hat): 几乎纯噪声，极快衰减
    # M1_TL=127 (静音), C2_TL=0 (最响), C2_DR=0x1F (极速衰减)
    42: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x1F, 0x0F, True, 0x1F),
    46: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x1F, 0x0F, True, 0x1F),

    # 49/51 吊镲 (Cymbal): 纯噪声，但需要更长一点的衰减余音
    # C2_DR=0x12 (稍慢衰减), SL_RR=0x1F (释放也快)
    49: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x12, 0x1F, True, 0x1C),
    51: (0x7F, 0x00, 0x07, 0x01, 0x1F, 0x00, 0x12, 0x1F, True, 0x1C),
}

PCM_RHY_PRIORITY = {35, 36, 38, 39, 40, 42, 44, 46}

def _pan_bits(pan: int) -> int:
    if pan < 32:
        return 0x40
    if pan > 96:
        return 0x80
    return 0xC0


@dataclass
class Slot:
    midi_ch: int = 0
    note: int = 0
    program: int = 0
    velocity: int = 0
    active: bool = False
    released: bool = False
    pending_off: bool = False
    start_time: float = 0.0
    release_time: float = 0.0
    serial: int = 0


class OpmSystem:
    def __init__(self, core: ChipCore, n_ch: int = 8, bend_range: int = 2):
        self.core = core
        self.n_ch = n_ch
        self.bend_range = bend_range
        self.slots = [Slot() for _ in range(n_ch)]
        self.loaded_program = [-1] * n_ch
        self.voices: list[OpmVoice] = []
        self.programs = [0] * 16
        self.bend14 = [8192] * 16
        
        self.sustain = [False] * 16
        self.ch_vol = [127] * 16
        self.ch_expr = [127] * 16
        self.ch_brightness = [64] * 16 
        
        # 专属鼓通道（物理通道 7）
        self.drum_ch = self.n_ch - 1
        
        self.serial = 0
        self.time = 0.0
        self.pcm = PcmCore(core.sample_rate()) 
        self.vgm_log = []      # 新增：记录 VGM 日志
        self.trace_vgm = False # 新增：录制开关
        self._init_hardware()

    def _w(self, reg: int, val: int) -> None:
        self.core.write(reg, val)
        
        if self.trace_vgm:
            # 【关键修改】：给 VGM 导出的 TL（音量）寄存器加一个安全偏置
            out_val = val & 0xFF
            if 0x60 <= (reg & 0xFF) <= 0x7F:
                # 强制增加 8（相当于衰减 6dB），防止 VGM 播放器爆音
                out_val = min(127, out_val + 8)
            self.vgm_log.append((self.time, reg & 0xFF, out_val))

    def _init_hardware(self):
        for ch in range(self.n_ch):
            self._w(0x08, ch)
        self._w(0x0F, 0x00) # 关闭 Noise

    def load_bank(self, voices: list[OpmVoice]) -> None:
        self.voices = list(voices)

    def _load_voice(self, ch: int, v: OpmVoice) -> None:
        lfo = list(v.lfo) + [0] * (5 - len(v.lfo))
        self._w(0x18, lfo[0] & 0xFF)
        self._w(0x19, 0x80 | (lfo[2] & 0x7F)) # PMD
        self._w(0x19, lfo[1] & 0x7F)          # AMD
        self._w(0x1B, (lfo[3] & 0x03) | ((lfo[4] & 0x1F) << 3))

        pan, fl, con, ams, pms = v.ch[0], v.ch[1], v.ch[2], v.ch[3], v.ch[4]
        self._w(0x20 + ch, _pan_bits(pan) | ((fl & 7) << 3) | (con & 7))
        self._w(0x38 + ch, ((pms & 7) << 4) | (ams & 3))

        for i, op in enumerate(v.ops):
            base = VOPM_OP_REG[i] * 8 + ch
            self._w(0x40 + base, ((op["dt1"] & 7) << 4) | (op["mul"] & 0x0F))
            self._w(0x60 + base, op["tl"] & 0x7F)
            self._w(0x80 + base, ((op["ks"] & 3) << 6) | (op["ar"] & 0x1F))
            self._w(0xA0 + base, ((op.get("ame", 0) & 1) << 7) | (op["dr"] & 0x1F))
            self._w(0xC0 + base, ((op["dt2"] & 3) << 6) | (op["sr"] & 0x1F))
            self._w(0xE0 + base, ((op["sl"] & 0x0F) << 4) | (op["rr"] & 0x0F))

    def _update_tl(self, ch: int, v: OpmVoice, velocity: int) -> None:
        midi_ch = self.slots[ch].midi_ch
        con = v.ch[2] & 7
        carriers = CARRIER_MASK.get(con, (0, 0, 0, 1))

        vel = max(0, min(127, velocity))
        vol = self.ch_vol[midi_ch]
        expr = self.ch_expr[midi_ch]

        total_db = 0.0
        if vel == 0:
            total_db += 96.0
        else:
            total_db += -20.0 * math.log10(vel / 127.0)
        if vol == 0 or expr == 0:
            total_db += 96.0
        else:
            total_db += -20.0 * math.log10((vol * expr) / (127.0 * 127.0))

        atten_carrier = int(round(total_db / TL_DB_PER_STEP))
        atten_carrier = max(0, min(127, atten_carrier))

        bright = self.ch_brightness[midi_ch] 
        atten_mod = int((64 - bright) * 0.75) 

        for i, op in enumerate(v.ops):
            tl = op["tl"] & 0x7F
            if carriers[i]:
                tl = min(127, tl + atten_carrier)
            else:
                tl = min(127, tl + atten_mod)
            self._w(0x60 + VOPM_OP_REG[i] * 8 + ch, tl)

    def _set_pitch(self, ch: int, pitch: float) -> None:
        base = int(math.floor(pitch))
        frac = pitch - base
        note = max(0, min(127, base))

        octave = (note // 12) - 1
        octave = max(0, min(7, octave)) 
        key = KTBL[note % 12]
        kc = (octave << 4) | key
        
        kf = int(round(frac * 64)) & 0x3F
        self._w(0x28 + ch, kc & 0x7F)
        self._w(0x30 + ch, kf << 2)

    def _pitch_with_bend(self, midi_ch: int, note: int) -> float:
        bend = (self.bend14[midi_ch & 0x0F] - 8192) / 8192.0
        return note + bend * self.bend_range

    def _find(self, midi_ch: int, note: int) -> int:
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch and s.note == note:
                return i
        return -1

    def _allocate(self, midi_ch: int, note: int) -> int:
        # 【修改】物理通道 7 已经解放，现在 0~7 共 8 个通道全部参与大逃杀！
        max_slots = self.n_ch 
        
        # 1. 优先找同 MIDI 通道、空闲的槽
        for i in range(max_slots):
            s = self.slots[i]
            if not s.active and not s.pending_off and s.midi_ch == midi_ch:
                return i

        # 2. 找任何完全空闲的槽
        found = -1
        for i in range(max_slots):
            s = self.slots[i]
            if not s.active and not s.pending_off:
                found = i
                break
                
        if found < 0:
            for i in range(max_slots):
                s = self.slots[i]
                if not s.active and not s.pending_off and s.midi_ch != midi_ch:
                    found = i
                    break

        if found < 0:
            best_midi = -1
            best_serial = 2**31
            for i in range(max_slots):
                s = self.slots[i]
                if s.midi_ch > best_midi:
                    best_midi = s.midi_ch
                    found = i
                    best_serial = s.serial
                elif s.midi_ch == best_midi and s.serial < best_serial:
                    found = i
                    best_serial = s.serial
                    
            if found < 0:
                return -1
            if self.slots[found].midi_ch < midi_ch:
                return -1

        s = self.slots[found]
        if s.active:
            self._w(0x08, found) 
            s.active = False
            
        return found

    def _real_note_off(self, ch: int) -> None:
        self._w(0x08, ch)
        s = self.slots[ch]
        s.active = False
        s.released = True
        s.pending_off = False
        s.release_time = self.time

    def _play_drum(self, note: int, velocity: int) -> None:
        """混合打击乐：核心高频鼓交给PCM，特色鼓还给FM (Ch7)"""
        
        # 1. 检查是否属于高频核心鼓，且我们有对应的 PCM 采样
        if note in PCM_RHY_PRIORITY and hasattr(self, 'pcm'):
            rhy_name = RHY_MAP.get(note)
            if rhy_name and rhy_name in self.pcm.samples:
                # 路线 A：交给虚拟 PCM 芯片（解决复音吞音）
                self.pcm.play(rhy_name, velocity)
                return  # 直接返回，完全不碰 FM 通道
                
        # 2. 剩下的（通鼓、镲片、木鱼、甚至 PCM 没采样的）全部交给 FM (Ch7)
        if note not in DRUM_BANK:
            return  # 字典里也没有，只能丢弃
            
        ch = self.drum_ch
        drum_data = DRUM_BANK[note]
        
        if isinstance(drum_data, tuple):
            alg, fb, op0, op1, op2, op3 = drum_data
            operators = [op0, op1, op2, op3]
        else:
            alg = drum_data['alg']
            fb = drum_data['fb']
            operators = drum_data['operators']
            
        self._w(0x08, ch)
        
        # 限制反馈防爆音
        safe_fb = min(fb, 6) 
        self._w(0x20 + ch, 0xC0 | (safe_fb << 3) | (alg & 7))
        
        vel_atten = (127 - velocity) >> 2
        
        for i, op in enumerate(operators):
            base = VOPM_OP_REG[i] * 8 + ch
            
            if isinstance(op, tuple):
                dt1, mul, tl, ks, ar, dr, sr, sl, rr = op
            else:
                dt1 = op.get('dt1', op.get('dt', 0))
                mul, tl, ks, ar, dr, sr, sl, rr = op['mul'], op['tl'], op['ks'], op['ar'], op['dr'], op['sr'], op['sl'], op['rr']
            
            op_tl = min(127, tl + vel_atten)
            
            self._w(0x40 + base, ((dt1 & 7) << 4) | (mul & 0x0F))
            self._w(0x60 + base, op_tl & 0x7F)
            self._w(0x80 + base, ((ks & 3) << 6) | (ar & 0x1F))
            
            # 鼓包络不翻译，保持干脆
            self._w(0xA0 + base, dr & 0x1F) 
            self._w(0xC0 + base, sr & 0x1F) 
            self._w(0xE0 + base, ((sl & 0x0F) << 4) | (rr & 0x0F))
            
        # 降 1 个八度，保留鼓的腔体感
        octave = (note // 12) - 1 
        octave = max(0, min(7, octave)) 
        kc = (octave << 4) | KTBL[note % 12]
        self._w(0x28 + ch, kc & 0x7F)
        self._w(0x30 + ch, 0x00)
        self._w(0x08, 0x78 | ch)

        # 记录状态
        s = self.slots[ch]
        s.midi_ch, s.note, s.velocity = 9, note, velocity
        s.active, s.released, s.pending_off = True, False, False
        s.start_time = self.time

    def note_on(self, midi_ch: int, note: int, velocity: int) -> None:
        midi_ch &= 0x0F
        
        # 拦截 MIDI 通道 10 的鼓点
        if midi_ch == 9:
            if velocity > 0:
                self._play_drum(note, velocity)
            return
            
        if velocity == 0:
            return self.note_off(midi_ch, note)
        if self._find(midi_ch, note) >= 0:
            return

        ch = self._allocate(midi_ch, note)
        if ch < 0:
            return
            
        prog = self.programs[midi_ch] % max(1, len(self.voices))
        v = self.voices[prog]

        if self.loaded_program[ch] != prog:
            self._load_voice(ch, v)
            self.loaded_program[ch] = prog

        s = self.slots[ch]
        s.midi_ch, s.note, s.program, s.velocity = midi_ch, note, prog, velocity
        s.active, s.released, s.pending_off = True, False, False
        s.start_time = self.time
        self.serial += 1
        s.serial = self.serial

        self._update_tl(ch, v, velocity)
        self._set_pitch(ch, self._pitch_with_bend(midi_ch, note))

        self._w(0x08, 0x78 | ch)

    def note_off(self, midi_ch: int, note: int) -> None:
        midi_ch &= 0x0F
        
        # 鼓通常不需要 Note Off（硬件自身极速衰减），直接忽略通道 10 的 Note Off
        if midi_ch == 9:
            return
            
        ch = self._find(midi_ch, note)
        if ch < 0:
            return
        if self.sustain[midi_ch]:
            self.slots[ch].pending_off = True
        else:
            self._real_note_off(ch)

    def program_change(self, midi_ch: int, prog: int) -> None:
        self.programs[midi_ch & 0x0F] = prog & 0x7F

    def pitch_bend(self, midi_ch: int, lsb: int, msb: int) -> None:
        midi_ch &= 0x0F
        if midi_ch == 9:
            return
        self.bend14[midi_ch] = ((msb & 0x7F) << 7) | (lsb & 0x7F)
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch and i != self.drum_ch:
                self._set_pitch(i, self._pitch_with_bend(midi_ch, s.note))

    def control_change(self, midi_ch: int, cc: int, value: int) -> None:
        midi_ch &= 0x0F
        if midi_ch == 9:
            return
        
        if cc == 0x07:
            self.ch_vol[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x0B:
            self.ch_expr[midi_ch] = value
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x4A:
            self.ch_brightness[midi_ch] = min(64, value)
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x40:
            if value >= 64:
                self.sustain[midi_ch] = True
            else:
                self.sustain[midi_ch] = False
                for i, s in enumerate(self.slots):
                    if s.midi_ch == midi_ch and s.pending_off:
                        self._real_note_off(i)
        elif cc == 0x78:
            for i, s in enumerate(self.slots):
                if s.active and s.midi_ch == midi_ch:
                    self._w(0x08, i)
                    s.active = s.pending_off = False
                    s.released = True
                    s.release_time = self.time
        elif cc == 0x79:
            self.bend14[midi_ch] = 8192
            self.ch_vol[midi_ch] = 127
            self.ch_expr[midi_ch] = 127
            self.ch_brightness[midi_ch] = 64
            self.sustain[midi_ch] = False
            for i, s in enumerate(self.slots):
                if s.midi_ch == midi_ch and s.pending_off:
                    self._real_note_off(i)
            self._refresh_channel_tl(midi_ch)
        elif cc == 0x7B:
            for i, s in enumerate(self.slots):
                if s.active and s.midi_ch == midi_ch:
                    self._real_note_off(i)

    def _refresh_channel_tl(self, midi_ch: int) -> None:
        for i, s in enumerate(self.slots):
            if s.active and s.midi_ch == midi_ch and i != self.drum_ch:
                v = self.voices[s.program % max(1, len(self.voices))]
                self._update_tl(i, v, s.velocity)

    def advance_time(self, seconds: float) -> None:
        self.time += seconds