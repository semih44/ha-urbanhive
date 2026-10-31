import sys
def sprout(x, y, s, leaf):
    return (f'<path d="M{x} {y} v{-9*s}" stroke="{leaf}" stroke-width="{2.4*s}" stroke-linecap="round"/>'
            f'<path d="M{x} {y-6*s} c{-7*s} {-1*s} {-10*s} {-7*s} {-9*s} {-11*s} c{5*s} 0 {9*s} {4*s} {9*s} {11*s}z" fill="{leaf}"/>'
            f'<path d="M{x} {y-8*s} c{7*s} {-1*s} {10*s} {-7*s} {9*s} {-11*s} c{-5*s} 0 {-9*s} {4*s} {-9*s} {11*s}z" fill="{leaf}"/>')
def svg(y0, bg1, bg2, tray, tray_edge, leaf):
    t = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">',
         f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient></defs>',
         '<rect x="8" y="8" width="240" height="240" rx="52" fill="url(#g)"/>']
    keime = {0: (2, 4), 1: (0, 2), 2: (0, 1, 2, 3, 4)}  # fünf Plätze je Schale
    for i in range(3):
        y = y0 + 56 * i
        t.append(f'<path d="M50 {y-22} H206 L198 {y} Q196 {y+8} 188 {y+8} H68 Q60 {y+8} 58 {y} Z" fill="{tray}" stroke="{tray_edge}" stroke-width="3" stroke-linejoin="round"/>')
        for k in keime[i]:
            t.append(sprout(65.6 + k * 31.2, y - 24, 1.25, leaf))
    t.append('</svg>')
    return "\n".join(t)
y0 = float(sys.argv[1])
open("icon.svg", "w").write(svg(y0, "#3f8f4f", "#1f5a33", "#f4f1e8", "#d9d3c2", "#9be36d"))
open("dark_icon.svg", "w").write(svg(y0, "#2c6b39", "#123a21", "#e9e5d8", "#bdb6a2", "#86d65a"))
