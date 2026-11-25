"""Animated 'time machine' strip shown under each year card (Manim, transparent PNG frames).
Render: python timeline.py  -> build/tl/<idx>/frame_*.png"""
import os, sys, glob, shutil
from manim import *
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, '..', 'build', 'tl')
CREAM, DIM, RED = ManimColor('#F0EBDF'), ManimColor('#9FA8A0'), ManimColor('#D0312D')
MONO, SERIF = 'FreeMono', 'Caladea'
Y = -2.35
def xpos(year):   # BCE negative; broken axis
    if year < 0: return -6.2 + (year + 1200) / 60 * 5.0          # 1200..1140 BCE -> -6.2..-1.2
    return 1.2 + (year - 1870) / 150 * 5.0                        # 1870..2020 CE -> 1.2..6.2
MARKS = [(-1186, '1186 BCE', 'KING CROWNED'), (-1158, 'YR 29', 'STRIKE'), (-1155, '1155 BCE', 'MURDER'),
         (1881, '1881', 'CACHE FOUND'), (1886, '1886', 'UNWRAPPED'), (2012, '2012', 'CT SCAN')]

def make(idx):
    class TL(Scene):
        def construct(self):
            axisL = Line([xpos(-1200), Y, 0], [xpos(-1140), Y, 0], color=DIM, stroke_width=3)
            axisR = Line([xpos(1870), Y, 0], [xpos(2020), Y, 0], color=DIM, stroke_width=3)
            gap = VGroup(*[Line([-1.0 + .4*i, Y - .12, 0], [-.8 + .4*i, Y + .12, 0], color=DIM, stroke_width=3) for i in range(5)])
            gl = Text('~3,000 YEARS', font=MONO, color=DIM, weight=BOLD).scale(.28).next_to(gap, DOWN, buff=.18)
            ticks, labels = VGroup(), VGroup()
            for j, (yr, a, b) in enumerate(MARKS):
                x = xpos(yr); up = j % 2 == 0 if yr < 0 else j % 2 == 1
                done = j <= idx
                d = Dot([x, Y, 0], radius=.07 if done else .05, color=CREAM if done else DIM)
                t1 = Text(a, font=MONO, weight=BOLD, color=CREAM if j == idx else DIM).scale(.27)
                t2 = Text(b, font=MONO, weight=BOLD, color=RED if j == idx else DIM).scale(.24)
                g = VGroup(t1, t2).arrange(DOWN, buff=.07)
                g.move_to([x, Y + (.55 if up else -.55), 0])
                ticks.add(d); labels.add(g)
            strip = VGroup(axisL, axisR, gap, gl, ticks, labels)
            x0 = xpos(MARKS[idx - 1][0]) if idx else xpos(-1200)
            head = VGroup(Line([0, .2, 0], [0, -.2, 0], color=RED, stroke_width=5), Triangle(color=RED, fill_opacity=1, stroke_width=0).scale(.09))
            head.arrange(DOWN, buff=.02).move_to([x0, Y - .07, 0])
            self.play(FadeIn(strip, shift=UP*.15), FadeIn(head), run_time=.35)
            self.play(head.animate.move_to([xpos(MARKS[idx][0]), Y - .07, 0]), run_time=1.3 if idx and (MARKS[idx][0] > 0) != (MARKS[idx-1][0] > 0) else .9, rate_func=rate_functions.ease_in_out_cubic)
            ring = Circle(radius=.16, color=RED, stroke_width=4).move_to([xpos(MARKS[idx][0]), Y, 0])
            self.play(Create(ring), labels[idx].animate.scale(1.25), run_time=.35)
            self.wait(1.0)
            self.play(FadeOut(VGroup(strip, head, ring)), run_time=.3)
    return TL

if __name__ == '__main__':
    for idx in range(len(MARKS)):
        d = os.path.join(OUT, str(idx)); shutil.rmtree(d, ignore_errors=True)
        with tempconfig({'pixel_width': 1920, 'pixel_height': 1080, 'frame_rate': 30, 'transparent': True,
                         'media_dir': os.path.join(OUT, 'media'), 'disable_caching': True, 'verbosity': 'ERROR', 'progress_bar': 'none'}):
            make(idx)().render()
        mov = max(glob.glob(os.path.join(OUT, 'media', 'videos', '**', '*.mov'), recursive=True), key=os.path.getmtime)
        os.makedirs(d); os.system(f'ffmpeg -v error -i "{mov}" "{d}/f%04d.png"')
        print(idx, len(os.listdir(d)), flush=True)
