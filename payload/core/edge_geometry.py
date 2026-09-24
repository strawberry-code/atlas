"""Geometria pura degli archi del canvas: nessun import da render_*, si scrive
e si prova senza browser, ed e' l'unico modo di sapere che un arco non e'
sparito dalla mappa.

Porta due sorgenti di Nodavia (~/cristiano/10-projects/16-llm-apps/nodavia):
`getSmoothStepPath` di @xyflow/react per l'arco in avanti (smooth_step_path,
ortogonale con raccordo agli angoli) e `loopPath.ts` per il back-edge (loop_path,
corsia laterale). Il canvas usa sempre la stessa coppia di posizioni (sorgente
sul bordo basso, bersaglio sul bordo alto: vedi FlowStepEdge.tsx e LoopEdge.tsx
in Nodavia), quindi qui non serve la posizione come parametro: e' fissa.

In Atlas un back-edge ha un significato preciso: nel layout a rank di C08, un
blockedBy verso un nodo di rango uguale o maggiore e' il sintomo che 'atlas
doctor' segnala altrove. Qui si decide solo come disegnarlo: corsia laterale
come Nodavia (LANE), piu' un tratteggio (LOOP_DASH) che lo distingue a colpo
d'occhio da un arco sano quando A03 lo innestera' sulla mappa.
"""
from __future__ import annotations

import math

CORNER = 10          # raccordo degli angoli, condiviso da arco in avanti e di ritorno
OFFSET = 20          # tratto dritto fuori dall'handle prima di piegare (getSmoothStepPath)
STEP_POSITION = 0.5  # frazione del segmento centrale dove cade la piega
# meta' larghezza della card (render_svg.W/2 = 130, issue #34 l'ha allargata
# da 230 a 260) piu' lo stesso margine di OFFSET: la corsia cade nel corridoio
# fra due colonne, mai dentro una card. Nessun import da render_svg (vedi il
# docstring del modulo): il numero si aggiorna a mano insieme a W, come gia'
# faceva prima con la card piu' stretta (115 + 20 = 135).
LANE = 150
DROP = 26            # tratto verticale sotto la sorgente prima di scartare di lato
LOOP_DASH = "5 5"    # il tratto che distingue un arco di ritorno da uno sano (decisione A01)

Point = tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _bend(a: Point, b: Point, c: Point, size: float) -> str:
    """Un angolo raccordato fra due segmenti ortogonali (porta di getBend).
    A differenza di rounded_path qui non si normalizza per lunghezza: il raggio
    e' un minimo fra le due meta'-segmento e `size`, mai una divisione, quindi
    un segmento di lunghezza nulla riduce il raccordo a zero invece di generare
    NaN. E' la ragione per cui questa funzione non ha bisogno di scartare punti
    coincidenti a monte.
    """
    bend = min(_dist(a, b) / 2, _dist(b, c) / 2, size)
    x, y = b
    if (a[0] == x == c[0]) or (a[1] == y == c[1]):
        return f"L{x} {y}"  # nessun angolo reale: i tre punti sono allineati
    if a[1] == y:  # primo segmento orizzontale, il secondo e' verticale
        x_dir = -1 if a[0] < c[0] else 1
        y_dir = 1 if a[1] < c[1] else -1
        return f"L {x + bend * x_dir},{y}Q {x},{y} {x},{y + bend * y_dir}"
    x_dir = 1 if a[0] < c[0] else -1  # primo segmento verticale, il secondo e' orizzontale
    y_dir = -1 if a[1] < c[1] else 1
    return f"L {x},{y + bend * y_dir}Q {x},{y} {x + bend * x_dir},{y}"


def smooth_step_path(
    source_x: float, source_y: float, target_x: float, target_y: float,
    *, offset: float = OFFSET, corner: float = CORNER, step_position: float = STEP_POSITION,
) -> str:
    """Arco in avanti ortogonale: sorgente sul bordo basso, bersaglio sul bordo
    alto. Porta getSmoothStepPath ristretto a questa coppia fissa di posizioni:
    il ramo speculare (bersaglio sopra la sorgente) e' quello che in Nodavia
    userebbe un back-edge, che qui passa da loop_path e non da questa funzione.
    Resta gestito lo stesso per robustezza, senza mai dividere per una lunghezza
    che puo' essere nulla.
    """
    source_gapped = (source_x, source_y + offset)
    target_gapped = (target_x, target_y - offset)
    downward = source_gapped[1] < target_gapped[1]
    center_x = (source_gapped[0] + target_gapped[0]) / 2
    center_y = source_gapped[1] + (target_gapped[1] - source_gapped[1]) * step_position
    if downward:
        mid = [(source_gapped[0], center_y), (target_gapped[0], center_y)]
    else:
        mid = [(center_x, source_gapped[1]), (center_x, target_gapped[1])]

    points = [(source_x, source_y)]
    if source_gapped != mid[0]:
        points.append(source_gapped)
    points.extend(mid)
    if target_gapped != mid[-1]:
        points.append(target_gapped)
    points.append((target_x, target_y))

    d = f"M{points[0][0]} {points[0][1]}"
    for i in range(1, len(points) - 1):
        d += _bend(points[i - 1], points[i], points[i + 1], corner)
    last = points[-1]
    return d + f"L{last[0]} {last[1]}"


def rounded_path(points: list[Point], corner: float = CORNER) -> str:
    """Polilinea -> path SVG con gli angoli raccordati (porta di roundedPath).
    I punti coincidenti si scartano prima di raccordare: altrimenti il raggio
    divide per una lunghezza nulla e il path esce con un NaN che non da' errore,
    fa solo sparire l'arco dal canvas.
    """
    pts = [
        q for i, q in enumerate(points)
        if i == 0 or abs(q[0] - points[i - 1][0]) > 0.5 or abs(q[1] - points[i - 1][1]) > 0.5
    ]
    if len(pts) < 2:
        return ""
    d = f"M {pts[0][0]},{pts[0][1]}"
    for i in range(1, len(pts) - 1):
        a, c, b = pts[i - 1], pts[i], pts[i + 1]
        la, lb = _dist(a, c), _dist(c, b)
        r = min(corner, la / 2, lb / 2)
        d += f" L {c[0] + (a[0] - c[0]) / la * r},{c[1] + (a[1] - c[1]) / la * r}"
        d += f" Q {c[0]},{c[1]} {c[0] + (b[0] - c[0]) / lb * r},{c[1] + (b[1] - c[1]) / lb * r}"
    last = pts[-1]
    return d + f" L {last[0]},{last[1]}"


def loop_lane(source_x: float, target_x: float) -> float:
    """Corsia verticale del ritorno: dal lato verso cui il ritorno gia' punta,
    cosi' l'arco non attraversa i nodi che stanno in mezzo. In colonna (stessa
    x) la scelta e' arbitraria e va a destra, come Nodavia.
    """
    if source_x >= target_x:
        return max(source_x, target_x) + LANE
    return min(source_x, target_x) - LANE


def loop_path(source_x: float, source_y: float, target_x: float, target_y: float) -> dict:
    """Arco di ritorno: esce dal fondo della sorgente, scavalca le card sulla
    corsia di loop_lane e rientra dall'alto nel bersaglio (porta di loopPath.ts).
    La quota di rientro (rise) cresce con la lunghezza del giro, cosi' piu'
    ritorni che convergono sullo stesso nodo non corrono sulla stessa riga.
    """
    lane = loop_lane(source_x, target_x)
    rise = 26 + min(70, abs(lane - target_x) * 0.12)
    d = rounded_path([
        (source_x, source_y),
        (source_x, source_y + DROP),
        (lane, source_y + DROP),
        (lane, target_y - rise),
        (target_x, target_y - rise),
        (target_x, target_y),
    ])
    return {"d": d, "lane": lane, "label_y": (source_y + DROP + target_y - rise) / 2}
