import os
from ..utils import utils
from ..utils.make_datamodule import OSSStorer
from typing import List

log = utils.get_logger(__name__)


def char_idx_to_token(char_idx, offset_mapping):
    """
    将char级别的idx 转换为token级别的idx
    例如:
    text = '我是中国人'
    tokens = ['我', '是', '中国', '人']
    '国'的字符下标为3, token级别的下标为2
    """
    for index, span in enumerate(offset_mapping):
        if span[0] <= char_idx < span[1]:
            return index
    return -1


def prepare_data_from_oss(dataset: str,
                          plm: str,
                          dataset_dir: str ='./datasets/',
                          plm_dir: str = './plms/') -> None:
        '''
        下载数据集.这个方法只会在一个GPU上执行一次.
        '''
        oss = OSSStorer()
        dataset_path = os.path.join(dataset_dir, dataset)
        plm_path = os.path.join(plm_dir, plm)
        # 检测数据
        log.info('Checking all data ...' )
        if os.path.exists(dataset_path):
            log.info(f'{dataset_path} already exists.')
        else:
            log.info('not exists dataset in {}'.format(dataset_path))
            log.info('start downloading dataset from oss')
            oss.download_dataset(dataset, dataset_dir)
            log.info('finish downloading dataset from oss')
        if os.path.exists(plm_path):
            log.info(f'{plm_path} already exists.') 
        else : 
            log.info('not exists plm in {}'.format(plm_path))
            log.info('start downloading plm from oss')
            oss.download_plm(plm, plm_dir)
            log.info('finish downloading plm from oss')
        log.info('all data are ready')
        
        
        
FH_SPACE = FHS = ((u"　", u" "),)
FH_NUM = FHN = (
    (u"０", u"0"), (u"１", u"1"), (u"２", u"2"), (u"３", u"3"), (u"４", u"4"),
    (u"５", u"5"), (u"６", u"6"), (u"７", u"7"), (u"８", u"8"), (u"９", u"9"),
)
FH_ALPHA = FHA = (
    (u"ａ", u"a"), (u"ｂ", u"b"), (u"ｃ", u"c"), (u"ｄ", u"d"), (u"ｅ", u"e"),
    (u"ｆ", u"f"), (u"ｇ", u"g"), (u"ｈ", u"h"), (u"ｉ", u"i"), (u"ｊ", u"j"),
    (u"ｋ", u"k"), (u"ｌ", u"l"), (u"ｍ", u"m"), (u"ｎ", u"n"), (u"ｏ", u"o"),
    (u"ｐ", u"p"), (u"ｑ", u"q"), (u"ｒ", u"r"), (u"ｓ", u"s"), (u"ｔ", u"t"),
    (u"ｕ", u"u"), (u"ｖ", u"v"), (u"ｗ", u"w"), (u"ｘ", u"x"), (u"ｙ", u"y"), (u"ｚ", u"z"),
    (u"Ａ", u"A"), (u"Ｂ", u"B"), (u"Ｃ", u"C"), (u"Ｄ", u"D"), (u"Ｅ", u"E"),
    (u"Ｆ", u"F"), (u"Ｇ", u"G"), (u"Ｈ", u"H"), (u"Ｉ", u"I"), (u"Ｊ", u"J"),
    (u"Ｋ", u"K"), (u"Ｌ", u"L"), (u"Ｍ", u"M"), (u"Ｎ", u"N"), (u"Ｏ", u"O"),
    (u"Ｐ", u"P"), (u"Ｑ", u"Q"), (u"Ｒ", u"R"), (u"Ｓ", u"S"), (u"Ｔ", u"T"),
    (u"Ｕ", u"U"), (u"Ｖ", u"V"), (u"Ｗ", u"W"), (u"Ｘ", u"X"), (u"Ｙ", u"Y"), (u"Ｚ", u"Z"),
)
FH_PUNCTUATION = FHP = (
    (u"．", u"."), (u"，", u","), (u"！", u"!"), (u"？", u"?"), (u"”", u'"'),
    (u"’", u"'"), (u"‘", u"`"), (u"＠", u"@"), (u"＿", u"_"), (u"：", u":"),
    (u"；", u";"), (u"＃", u"#"), (u"＄", u"$"), (u"％", u"%"), (u"＆", u"&"),
    (u"（", u"("), (u"）", u")"), (u"‐", u"-"), (u"＝", u"="), (u"＊", u"*"),
    (u"＋", u"+"), (u"－", u"-"), (u"／", u"/"), (u"＜", u"<"), (u"＞", u">"),
    (u"［", u"["), (u"￥", u"\\"), (u"］", u"]"), (u"＾", u"^"), (u"｛", u"{"),
    (u"｜", u"|"), (u"｝", u"}"), (u"～", u"~"), (u'“', u'"'), (u'。', u'.'),
)
FH_ASCII = HAC = lambda: ((fr, to) for m in (FH_ALPHA, FH_NUM, FH_PUNCTUATION) for fr, to in m)
HF_SPACE = HFS = ((u" ", u"　"),)
HF_NUM = HFN = lambda: ((h, z) for z, h in FH_NUM)
HF_ALPHA = HFA = lambda: ((h, z) for z, h in FH_ALPHA)
HF_PUNCTUATION = HFP = lambda: ((h, z) for z, h in FH_PUNCTUATION)
HF_ASCII = ZAC = lambda: ((h, z) for z, h in FH_ASCII())


def convert_FH(text, *maps, **ops):
    """ 全角/半角转换
    args:
        text: unicode string need to convert
        maps: conversion maps
        skip: skip out of character. In a tuple or string
        return: converted unicode string
    """
    if "skip" in ops:
        skip = ops["skip"]
        if isinstance(skip, str):
            skip = tuple(skip)
        def replace(text, fr, to):
            return text if fr in skip else text.replace(fr, to)
    else:
        def replace(text, fr, to):
            return text.replace(fr, to)
    for m in maps:
        if callable(m):
            m = m()
        elif isinstance(m, dict):
            m = m.items()
        for fr, to in m:
            text = replace(text, fr, to)

    return text
        
        
        
def fine_grade_tokenize(raw_text:str, tokenizer, convert_fh:bool =False) -> List[str]:
    """
    - 全角转半角
    - 序列标注任务 BERT 分词器可能会导致标注偏移，
    - 用 char-level 来 tokenize

    """
    tokens = []
    # 进行全角转半角预处理
    if convert_fh:
        raw_text = convert_FH(raw_text, FH_ASCII)  

    for _ch in raw_text:
        if _ch in [' ', '\t', '\n']:
            tokens.append('[BLANK]')
        else:
            if not len(tokenizer.tokenize(_ch)):
                tokens.append('[INV]')
            else:
                tokens.append(_ch)
    return tokens