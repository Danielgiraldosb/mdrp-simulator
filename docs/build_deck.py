"""
Build the offline deck: inject the embedded @font-face blocks (extracted from
docs/ore-hauling-offline (2).html into _fonts_extracted.css) into the .src.html.

  python docs/build_deck.py            -> docs/mdrp-jerarquia-objetivos.html
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'mdrp-jerarquia-objetivos.src.html')
FONTS = os.path.join(HERE, '_fonts_extracted.css')
OUT = os.path.join(HERE, 'mdrp-jerarquia-objetivos.html')

def main():
    src = open(SRC, encoding='utf8').read()
    if not os.path.exists(FONTS):
        ore = os.path.join(HERE, 'ore-hauling-offline (2).html')
        s = open(ore, encoding='utf8').read()
        blocks = re.findall(r'(?:/\*[^*]*\*/\s*)?@font-face\s*\{[^}]*\}', s)
        open(FONTS, 'w', encoding='utf8').write('\n'.join(blocks))
    fonts = open(FONTS, encoding='utf8').read()
    assert '/*__FONTS__*/' in src, 'placeholder missing'
    out = src.replace('/*__FONTS__*/', fonts, 1)
    open(OUT, 'w', encoding='utf8').write(out)
    print(f'wrote {OUT}  ({len(out)/1024:.0f} KB; fonts {len(fonts)/1024:.0f} KB)')

if __name__ == '__main__':
    sys.exit(main())
