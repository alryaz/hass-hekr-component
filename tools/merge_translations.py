#!/usr/bin/env python3
"""
Merge English originals into translation files.

Whenever a new translation key is added, this script must be run to display
at least an English translation with unsupported languages.

This is a workaround until further notice.
"""

import collections.abc
from copy import deepcopy
from json import load, dump
from os.path import isfile

base_path = '../custom_components/hekr/translations'
all_languages = {'af', 'ar', 'bg', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'fi',
                 'fr', 'fy', 'gl', 'gsw', 'he', 'hi', 'hr', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'ko', 'lb', 'lt', 'lv',
                 'nb', 'nl', 'nn', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'ur',
                 'vi', 'zh'}

base_language = 'en'

overwrite_key = '_remove_me_after_making_translations_or_everything_will_be_replaced'

def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def replace_values(d, c):
    for k, v in d.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = replace_values(v, c)
        else:
            d[k] = c(v)
    return d


with open(base_path + '/' + base_language + '.json', 'r', encoding='utf-8') as fp:
    base_json = load(fp)
    base = replace_values(base_json, lambda v: '%s' % v)

for language in all_languages:
    path = base_path + '/' + language + '.json'
    result = deepcopy(base)
    if isfile(path):
        with open(path, 'r', encoding='utf-8') as fp:
            head = load(fp)
            if head.get(overwrite_key):
                result[overwrite_key] = True
            else:
                update(result, head)
    else:
        result[overwrite_key] = True

    with open(path, 'w', encoding='utf-8') as fp:
        dump(result, fp, ensure_ascii=False, indent=4, sort_keys=True)
