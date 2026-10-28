"""Draw the proposed-method flow diagram (report section 3) as a PNG with Malgun Gothic. Usage: python tools/method_diagram.py docs/figures/method_overview.png"""
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H = 1800, 1500
img = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(img)
F = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 34)
FB = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 34)
FS = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 28)
INK = (40, 40, 40)
FILL = {'in': (235, 235, 235), 'llm': (222, 235, 247), 'num': (255, 255, 255), 'cond': (253, 236, 214), 'eval': (226, 240, 217), 'dict': (245, 245, 245)}
BW, BH = 520, 96
boxes = {}

def box(key, cx, cy, text, kind, w=BW, bold=False):
    x0, y0, x1, y1 = cx - w // 2, cy - BH // 2, cx + w // 2, cy + BH // 2
    d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=FILL[kind], outline=INK, width=3)
    font = FB if bold else F
    tw = d.textlength(text, font=font)
    d.text((cx - tw / 2, cy - 24), text, font=font, fill=INK)
    boxes[key] = (x0, y0, x1, y1)

def arrow(points):
    d.line(points, fill=INK, width=4, joint='curve')
    (xa, ya), (xb, yb) = points[-2], points[-1]
    import math
    ang = math.atan2(yb - ya, xb - xa)
    s = 20
    left = (xb - s * math.cos(ang) + s * 0.55 * math.sin(ang), yb - s * math.sin(ang) - s * 0.55 * math.cos(ang))
    right = (xb - s * math.cos(ang) - s * 0.55 * math.sin(ang), yb - s * math.sin(ang) + s * 0.55 * math.cos(ang))
    d.polygon([(xb, yb), left, right], fill=INK)

XA, XM, XC = 300, 900, 1500
box('in', XM, 90, '이미지 + 요청', 'in', bold=True)
box('pose', XM, 270, 'LLM 초기 자세 추정', 'llm')
box('fit', XM, 430, '실루엣 정합', 'num')
box('plan', XM, 590, 'LLM 키프레임 계획', 'llm')
box('dict', XC, 590, '고정 행동 사전', 'dict', w=420)
box('anim', XM, 750, '고정 길이 애니메이션·렌더링', 'num')
box('review', XC, 930, '렌더 검토·최대 1회 수정', 'llm')
box('A', XA, 1150, '조건 A: 직접 I2V', 'cond', w=440, bold=True)
box('B', XM, 1150, '조건 B: 최초 레퍼런스 R2V', 'cond', bold=True)
box('C', XC, 1150, '조건 C: 검증 레퍼런스 R2V', 'cond', bold=True)
box('eval', XM, 1390, '익명 사람 평가', 'eval', bold=True)

bot = lambda k: boxes[k][3]
top = lambda k: boxes[k][1]
arrow([(XM, bot('in')), (XM, top('pose'))])
arrow([(XM, bot('pose')), (XM, top('fit'))])
arrow([(XM, bot('fit')), (XM, top('plan'))])
arrow([(boxes['dict'][0], 590), (boxes['plan'][2], 590)])
arrow([(XM, bot('plan')), (XM, top('anim'))])
arrow([(XM, bot('anim')), (XM, top('B'))])
arrow([(boxes['anim'][2], 750), (XC, 750), (XC, top('review'))])
arrow([(XC, bot('review')), (XC, top('C'))])
arrow([(boxes['in'][0], 90), (XA, 90), (XA, top('A'))])
arrow([(XA, bot('A')), (XA, 1390), (boxes['eval'][0], 1390)])
arrow([(XM, bot('B')), (XM, top('eval'))])
arrow([(XC, bot('C')), (XC, 1390), (boxes['eval'][2], 1390)])
note = '최초 레퍼런스'
d.text((XM + 18, 930 - 18), note, font=FS, fill=(90, 90, 90))
img.save(OUT)
